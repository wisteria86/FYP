# Path: core/conversation_manager.py
import re
import threading
import queue
import concurrent.futures
from typing import Optional
import pysbd
from core.interfaces import IAudioInput, ISTTModel, ILLMModel, ITTSModel, IAudioOutput
from utils.logger import get_logger
from utils.ui import CLI
from utils.hardware import is_safe_for_barge_in

logger = get_logger(__name__)

class ConversationManager:
    """
    Orchestrates the conversation flow. 
    Notice how it depends on Abstractions (Interfaces), NOT concrete implementations.
    """
    def __init__(
        self, 
        audio_in: IAudioInput, 
        stt: ISTTModel, 
        llm: ILLMModel, 
        tts: ITTSModel, 
        audio_out: IAudioOutput
    ):
        self.audio_in = audio_in
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.audio_out = audio_out
        self.barge_in_enabled = is_safe_for_barge_in()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.current_state = "Idle"
        # Pre-generate a short 'hmm' for audio filler
        self.thinking_audio_bytes = b"".join([chunk for chunk in self.tts.synthesize("Hmm.", speed=1.1)])

    def run_turn(self, interrupted_audio: Optional[bytes] = None, proactive_system_note: Optional[str] = None, timeout_tier: int = 0) -> Optional[bytes]:
        """
        Executes a single turn of conversation.
        Returns audio bytes if interrupted, else None.
        """
        try:
            user_text = ""
            if not proactive_system_note:
                if interrupted_audio:
                    user_audio = interrupted_audio
                else:
                    with CLI.status("Listening for user input...", spinner="point"):
                        try:
                            vad_t = 3.0 if self.current_state == "Waiting for Answer" else 1.5
                            if timeout_tier == 0:
                                timeout_sec = 15.0
                            elif timeout_tier == 1:
                                timeout_sec = 45.0
                            else:
                                timeout_sec = 90.0
                            user_audio = self.audio_in.capture_audio(silence_timeout=timeout_sec, vad_threshold=vad_t)
                        except TimeoutError:
                            logger.info(f"Silence timeout triggered (Tier {timeout_tier}).")
                            if timeout_tier == 0:
                                self.current_state = "Waiting for Answer"
                                note = f"[System Note: User silent for 15s. Current State: {self.current_state}. Give a soft nudge, ask if they are still there or need time.]"
                                return self.run_turn(proactive_system_note=note, timeout_tier=1)
                            elif timeout_tier == 1:
                                self.current_state = "Waiting for Answer"
                                note = f"[System Note: User silent for 45s. Current State: {self.current_state}. Bluntly challenge them on why they are quiet.]"
                                return self.run_turn(proactive_system_note=note, timeout_tier=2)
                            else:
                                self.current_state = "Idle"
                                note = f"[System Note: User silent for 90s. Announce you are pausing the session and they can come back when ready.]"
                                return self.run_turn(proactive_system_note=note, timeout_tier=0)
                    
                if not user_audio:
                    return None
                
                with CLI.status("Transcribing audio...", spinner="bouncingBar"):
                    user_text = self.stt.transcribe(user_audio)
                    
                if not user_text.strip():
                    logger.info("No speech detected.")
                    return None

                logger.info(f"[bold green]User:[/bold green] {user_text}")
                
                # Check for goal statements
                lower_text = user_text.lower()
                if "goal" in lower_text or "want to work on" in lower_text or "focus on" in lower_text:
                    self.llm.save_profile(new_summary=None, new_goal=user_text)
                    logger.info("Goal updated in profile.")
                    
                self.current_state = "Explaining"

            
            cancel_event = threading.Event()
            mic_abort_event = threading.Event()
            interruption_future = None
            
            if self.barge_in_enabled:
                interruption_future = self.executor.submit(
                    self.audio_in.capture_audio,
                    on_speech_started=cancel_event.set,
                    abort_event=mic_abort_event
                )
            
            # The streaming architecture
            sentence_queue = queue.Queue()
            audio_queue = queue.Queue()
            
            def llm_producer():
                is_thinking = False
                buffer = ""
                segmenter = pysbd.Segmenter(language="en", clean=False)
                
                if proactive_system_note:
                    token_stream = self.llm.generate_proactive_response(proactive_system_note)
                else:
                    token_stream = self.llm.generate_response(user_text)
                
                for token in token_stream:
                    if cancel_event.is_set():
                        break
                        
                    buffer += token
                    
                    if not is_thinking:
                        if "<think>" in buffer:
                            is_thinking = True
                            parts = buffer.split("<think>")
                            if parts[0].strip():
                                sentence_queue.put(parts[0].strip())
                            buffer = parts[1] if len(parts) > 1 else ""
                            logger.info("[dim]Thinking...[/dim]", extra={"markup": True})
                    
                    if is_thinking:
                        if "</think>" in buffer:
                            is_thinking = False
                            parts = buffer.split("</think>")
                            thought_content = parts[0].strip()
                            if thought_content:
                                logger.info(f"[dim]{thought_content}[/dim]", extra={"markup": True})
                            
                            buffer = parts[1] if len(parts) > 1 else ""
                    
                    if not is_thinking:
                        sentences = segmenter.segment(buffer)
                        if len(sentences) > 1:
                            for sentence in sentences[:-1]:
                                if sentence.strip():
                                    sentence_queue.put(sentence.strip())
                            buffer = sentences[-1]
                
                if not is_thinking and buffer.strip() and not cancel_event.is_set():
                    sentence_queue.put(buffer.strip())
                
                sentence_queue.put(None)
            
            def tts_worker():
                while not cancel_event.is_set():
                    sentence = sentence_queue.get()
                    if sentence is None or cancel_event.is_set():
                        audio_queue.put(None)
                        break
                    
                    try:
                        speed = 1.1 if self.current_state in ["Greeting", "Waiting for Answer"] else 0.95
                        ai_audio_stream = self.tts.synthesize(sentence, speed=speed)
                        audio_queue.put((sentence, ai_audio_stream))
                    except Exception as e:
                        if not cancel_event.is_set():
                            logger.error(f"TTS Error on sentence '{sentence}': {e}")
            
            producer_thread = threading.Thread(target=llm_producer)
            tts_thread = threading.Thread(target=tts_worker)
            
            producer_thread.start()
            tts_thread.start()
            
            first_sentence = True
            status = CLI.status("Generating AI response...", spinner="aesthetic")
            status.start()
            
            # Play thinking filler audio immediately on a daemon thread
            if not proactive_system_note and self.thinking_audio_bytes:
                threading.Thread(target=self.audio_out.play_audio, args=(self.thinking_audio_bytes,), daemon=True).start()
            
            while not cancel_event.is_set():
                item = audio_queue.get()
                if item is None or cancel_event.is_set():
                    break
                
                sentence, ai_audio_stream = item
                
                if first_sentence:
                    first_sentence = False
                    status.stop()
                    logger.info("[bold blue]AI:[/bold blue] (Speaking...)")
                
                if not cancel_event.is_set():
                    logger.info(f"  [cyan]{sentence}[/cyan]", extra={"markup": True})
                    self.audio_out.play_stream(ai_audio_stream, cancel_event=cancel_event)
            
            if first_sentence and not cancel_event.is_set():
                status.stop()
                
            was_interrupted = cancel_event.is_set()
            
            cancel_event.set() # Ensure threads terminate
            producer_thread.join()
            tts_thread.join()
            
            if was_interrupted and interruption_future:
                with CLI.status("Listening to interruption...", spinner="point"):
                    return interruption_future.result()
            elif interruption_future:
                mic_abort_event.set()
                interruption_future.result()
                
            return None
            
        except Exception as e:
            logger.error(f"Error during conversation turn: {e}")
            return None

    def start_loop(self):
        """Runs the conversation in a continuous loop."""
        logger.info("Starting conversation loop. Press Ctrl+C to stop.")
        try:
            self.current_state = "Greeting"
            self.run_turn(proactive_system_note=f"[System Note: The session just started. Current State: {self.current_state}. Greet the user bluntly and ask what they want to work on today. Do not wait for them to speak first.]")
            
            self.current_state = "Idle"
            interrupted_audio = None
            while True:
                interrupted_audio = self.run_turn(interrupted_audio)
        except KeyboardInterrupt:
            logger.info("Closing session...")
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.barge_in_enabled = False
            self.current_state = "Wrapping up"
            self.run_turn(proactive_system_note="[System Note: The session is ending abruptly. Summarize what was covered in 1 sentence, and tell the user one thing to practice.]")
            summary_stream = self.llm.generate_proactive_response("[System: Write a 1 sentence summary of this session for your internal notes. No greetings.]")
            summary = "".join([s for s in summary_stream])
            self.llm.save_profile(summary)
            logger.info("Session ended gracefully.")