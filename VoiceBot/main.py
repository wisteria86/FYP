# Path: main.py
from config import Config
from core.conversation_manager import ConversationManager
from modules.stt_whisper import WhisperSTT
from modules.llm_brain import LLMBrain
from modules.tts_kokoro import KokoroTTS
from io_interfaces.mic_recorder import MicRecorder
from io_interfaces.speaker_player import SpeakerPlayer
from utils.ui import CLI

def main():
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