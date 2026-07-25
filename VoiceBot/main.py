"""
Main Entry Point for the Voice Assistant Application.

This module is responsible for bootstrapping the application. It initializes all
hardware interfaces (microphone, speaker) and machine learning models (STT, LLM, TTS),
then injects them into the central orchestrator (ConversationManager) before
starting the main event loop.
"""
# Path: main.py
from config import Config
from core.conversation_manager import ConversationManager
from modules.stt_whisper import WhisperSTT
from modules.llm_brain import LLMBrain
from modules.tts_kokoro import KokoroTTS
from io_interfaces.mic_recorder import MicRecorder
from io_interfaces.speaker_player import SpeakerPlayer
from utils.ui import CLI

def main() -> None:
    """
    Initializes and starts the voice assistant application.

    This function performs the following steps:
    1. Instantiates concrete implementations of audio interfaces (MicRecorder, SpeakerPlayer).
    2. Loads the necessary AI models (Whisper STT, LLM Brain, Kokoro TTS).
    3. Injects these dependencies into the ConversationManager.
    4. Starts the main conversation loop.
    """
    CLI.print_header("Voice Assistant Initialization")
    
    # 1. Initialize Concrete Implementations (Dependency Construction)
    with CLI.status("Initializing Audio Interfaces..."):
        mic = MicRecorder(sample_rate=Config.SAMPLE_RATE, record_seconds=Config.RECORD_SECONDS)
        speaker = SpeakerPlayer()
    
    with CLI.status("Loading Whisper STT (This may take a moment)..."):
        stt_model = WhisperSTT(model_size=Config.WHISPER_MODEL_SIZE)
        
    with CLI.status("Loading LLM Brain..."):
        llm_model = LLMBrain(api_key=Config.LLM_API_KEY, model_name=Config.LLM_MODEL_NAME, base_url=Config.LLM_BASE_URL)
        
    with CLI.status("Loading Kokoro TTS (This may take a moment)..."):
        tts_model = KokoroTTS()

    # 2. Inject Dependencies into the Orchestrator (Dependency Injection)
    with CLI.status("Wiring up Conversation Manager..."):
        manager = ConversationManager(
            audio_in=mic,
            stt=stt_model,
            llm=llm_model,
            tts=tts_model,
            audio_out=speaker
        )

    # 3. Start the application
    CLI.print_header("System Ready")
    manager.start_loop()

if __name__ == "__main__":
    main()