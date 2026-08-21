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

logger = get_logger(__name__)

class ConversationManager:
    """
    Orchestrates the voice assistant's primary interaction loop.
    
    This manager handles capturing audio, routing it through Speech-to-Text (STT),
    processing the text via a Large Language Model (LLM), and synthesizing the
    response back to audio via Text-to-Speech (TTS). It relies on dependency injection,
    using interface abstractions rather than concrete implementations for modularity.
    """
    def __init__(
        self, 
        audio_in: IAudioInput, 
        stt: ISTTModel, 
        llm: ILLMModel, 
        tts: ITTSModel, 
        audio_out: IAudioOutput
    ):
        """
        Initializes the ConversationManager with required hardware and model interfaces.

        Args:
            audio_in (IAudioInput): Interface for recording user audio.
            stt (ISTTModel): Interface for Speech-to-Text transcription.
            llm (ILLMModel): Interface for generating AI responses.
            tts (ITTSModel): Interface for Text-to-Speech synthesis.
            audio_out (IAudioOutput): Interface for playing audio to the user.
        """
        self.audio_in = audio_in
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.audio_out = audio_out
        self.barge_in_enabled = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.current_state = "Idle"
        self.silence_tier = 0
        # Eager synthesis causes a large ChatTTS inference allocation at startup.
        # Keep the optional filler off by default on memory-constrained machines.
        from config import Config
        self.thinking_audio_bytes = (
            b"".join(self.tts.synthesize("Hmm.", speed=1.1))
            if Config.ENABLE_THINKING_AUDIO
            else b""
        )

    def run_turn(self, interrupted_audio: Optional[bytes] = None, proactive_system_note: Optional[str] = None, timeout_tier: int = 0) -> Optional[bytes]:
        """
        Executes a single conversational turn between the user and the AI.

        This involves listening to the user, transcribing the audio, generating a
        response, and playing it back. It also handles barge-ins (interruptions)
        and proactive system notes when the user is silent.

        Args:
            interrupted_audio (Optional[bytes]): Audio captured during an interruption, if any.
            proactive_system_note (Optional[str]): A system prompt to trigger AI speech without user input.
            timeout_tier (int): Tracks the level of silence timeout (0 = short, 1 = medium, 2 = long).

        Returns:
            None
        """
        try:
            user_text = ""
            if not proactive_system_note:
                timeout_tier = self.silence_tier
                with CLI.status("Listening for user input...", spinner="point"):
                        try:
                            vad_t = 2.0
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
                                proactive_system_note = f"[System Note: User silent for 15s. Current State: {self.current_state}. Give a soft nudge, ask if they are still there or need time.]"
                                self.silence_tier = 1
                            elif timeout_tier == 1:
                                self.current_state = "Waiting for Answer"
                                proactive_system_note = f"[System Note: User silent for 45s. Current State: {self.current_state}. Bluntly challenge them on why they are quiet.]"
                                self.silence_tier = 2
                            else:
                                self.current_state = "Idle"
                                proactive_system_note = f"[System Note: User silent for 90s. Announce you are pausing the session and they can come back when ready.]"
                                self.silence_tier = 0
                            user_audio = None
                if not proactive_system_note:
                    if not user_audio:
                        return None
                
                    with CLI.status("Transcribing audio...", spinner="bouncingBar"):
                        user_text = self.stt.transcribe(user_audio)
                    
                    if not user_text.strip():
                        logger.info("No speech detected.")
                        return None

                    # Explicit console output to show mic code is working
                    print(f"\n---> You said: {user_text}\n")
                    logger.info(f"[bold green]User:[/bold green] {user_text}")
                
                    # Check for goal statements
                    lower_text = user_text.lower()
                    if "goal" in lower_text or "want to work on" in lower_text or "focus on" in lower_text:
                        self.llm.save_profile(new_summary=None, new_goal=user_text)
                        logger.info("Goal updated in profile.")
                    
                    self.current_state = "Explaining"
                    self.silence_tier = 0

            # The streaming architecture
            sentence_queue = queue.Queue(maxsize=4)
            audio_queue = queue.Queue(maxsize=2)
            worker_errors = queue.Queue()
            
            def llm_producer():
                try:
                    is_thinking = False
                    buffer = ""
                    # Covers Latin, Arabic and CJK terminators without assuming English.
                    boundary = re.compile(r"(?<=[.!?؟。！？])\s*")

                    token_stream = (
                        self.llm.generate_proactive_response(proactive_system_note)
                        if proactive_system_note
                        else self.llm.generate_response(user_text)
                    )

                    for token in token_stream:
                        buffer += token
                    
                        if not is_thinking and "<think>" in buffer:
                            is_thinking = True
                            parts = buffer.split("<think>", 1)
                            if parts[0].strip():
                                sentence_queue.put(parts[0].strip())
                            buffer = parts[1] if len(parts) > 1 else ""
                            logger.info("[dim]Thinking...[/dim]", extra={"markup": True})
                    
                        if is_thinking and "</think>" in buffer:
                            is_thinking = False
                            parts = buffer.split("</think>", 1)
                            thought_content = parts[0].strip()
                            if thought_content:
                                logger.info(f"[dim]{thought_content}[/dim]", extra={"markup": True})
                            
                            buffer = parts[1] if len(parts) > 1 else ""
                    
                        if not is_thinking:
                            sentences = boundary.split(buffer)
                            if len(sentences) > 1:
                                for sentence in sentences[:-1]:
                                    if sentence.strip():
                                        sentence_queue.put(sentence.strip())
                                buffer = sentences[-1]
                
                    if not is_thinking and buffer.strip():
                        sentence_queue.put(buffer.strip())
                except Exception as exc:
                    worker_errors.put(exc)
                finally:
                    if is_thinking:
                        logger.error("LLM generation ended while still inside a <think> block! (Hit max_tokens or API timeout)")
                        sentence_queue.put("すまない、考えすぎて頭がフリーズした。もう一度言ってくれ。")
                    sentence_queue.put(None)
            
            def tts_worker():
                while True:
                    sentence = sentence_queue.get()
                    if sentence is None:
                        audio_queue.put(None)
                        break
                    
                    try:
                        speed = 1.1 if self.current_state in ["Greeting", "Waiting for Answer"] else 0.95
                        chunk_queue = queue.Queue(maxsize=8)
                        audio_queue.put((sentence, chunk_queue))
                        for chunk in self.tts.synthesize(sentence, speed=speed):
                            chunk_queue.put(chunk)
                        chunk_queue.put(None)
                    except Exception as e:
                        worker_errors.put(e)
                        if 'chunk_queue' in locals():
                            chunk_queue.put(None)
            
            producer_thread = threading.Thread(target=llm_producer, daemon=True)
            tts_thread = threading.Thread(target=tts_worker, daemon=True)
            
            producer_thread.start()
            tts_thread.start()
            
            first_sentence = True
            status = CLI.status("Generating AI response...", spinner="aesthetic")
            status.start()
            
            # Play thinking filler audio immediately on a daemon thread
            if not proactive_system_note and self.thinking_audio_bytes:
                threading.Thread(target=self.audio_out.play_audio, args=(self.thinking_audio_bytes,), daemon=True).start()
            
            while True:
                try:
                    item = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    if not producer_thread.is_alive() and not tts_thread.is_alive() and audio_queue.empty():
                        break
                    continue
                if item is None:
                    break
                
                sentence, chunk_queue = item
                
                if first_sentence:
                    first_sentence = False
                    status.stop()
                    logger.info("[bold blue]AI:[/bold blue] (Speaking...)")
                
                logger.info(f"  [cyan]{sentence}[/cyan]", extra={"markup": True})
                def queued_audio():
                    while True:
                        chunk = chunk_queue.get()
                        if chunk is None:
                            return
                        yield chunk
                self.audio_out.play_stream(queued_audio())
            
            if first_sentence:
                status.stop()
                
            producer_thread.join(timeout=2)
            tts_thread.join(timeout=2)
            if not worker_errors.empty():
                raise worker_errors.get()
            
            return None
            
        except Exception as e:
            logger.error(f"Error during conversation turn: {e}")
            return None

    def start_loop(self) -> None:
        """
        Starts and maintains the continuous conversation loop.

        This method triggers the initial greeting and then indefinitely calls `run_turn()`
        until a KeyboardInterrupt (Ctrl+C) is caught. On interruption, it safely shuts
        down the thread pool executor, summarizes the session, and exits gracefully.
        """
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
            self.current_state = "Wrapping up"
            self.run_turn(proactive_system_note="[System Note: The session is ending abruptly. Summarize what was covered in 1 sentence, and tell the user one thing to practice.]")
            summary_stream = self.llm.generate_proactive_response("[System: Write a 1 sentence summary of this session for your internal notes. No greetings.]")
            summary = "".join([s for s in summary_stream])
            import re
            summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
            self.llm.save_profile(summary)
            logger.info("Session ended gracefully.")
