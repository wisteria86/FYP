"""
Main Entry Point for the Voice Assistant Application.

This module is responsible for bootstrapping the application. It initializes all
hardware interfaces (microphone, speaker) and machine learning models (STT, LLM, TTS),
then injects them into the central orchestrator (ConversationManager) before
starting the main event loop.

ChatTTS is the active speech engine for every language. Legacy TTS modules are
retained in the project but are not selected at runtime.
"""
# Path: main.py
from config import Config
from core.conversation_manager import ConversationManager
from modules.stt_whisper import WhisperSTT
from modules.llm_brain import LLMBrain
from io_interfaces.mic_recorder import MicRecorder
from io_interfaces.speaker_player import SpeakerPlayer
from utils.ui import CLI
import sys

# Prevent UnicodeEncodeError on Windows terminals without breaking the IDE renderer
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')


def main() -> None:
    """
    Initializes and starts the voice assistant application.

    Steps:
    1. Load STT and LLM models (hardware-agnostic, order-independent).
    2. Load ChatTTS for language-agnostic routing.
    3. Initialize audio I/O at ChatTTS's native sample rate.
    5. Wire everything into ConversationManager and start the loop.
    """
    CLI.print_header("Voice Assistant Initialization")

    # Validate microphone access before allocating memory for ML models.
    with CLI.status("Checking Microphone..."):
        mic = MicRecorder(
            sample_rate=Config.SAMPLE_RATE,
            record_seconds=Config.RECORD_SECONDS,
            device=Config.MIC_DEVICE,
        )

    # ------------------------------------------------------------------ #
    # 1. Speech-to-Text                                                   #
    # ------------------------------------------------------------------ #
    with CLI.status("Loading Whisper STT (This may take a moment)..."):
        stt_model = WhisperSTT(
            model_size=Config.WHISPER_MODEL_SIZE,
            cpu_threads=Config.WHISPER_CPU_THREADS,
            num_workers=Config.WHISPER_WORKERS,
            device=Config.WHISPER_DEVICE,
        )

    # ------------------------------------------------------------------ #
    # 2. LLM Brain                                                        #
    # ------------------------------------------------------------------ #
    with CLI.status("Loading LLM Brain..."):

        llm_model = LLMBrain(
            api_key=Config.LLM_API_KEY,
            model_name=Config.LLM_MODEL_NAME,
            base_url=Config.LLM_BASE_URL
        )

    # ------------------------------------------------------------------ #
    # 3. Text-to-Speech Engine Configuration                             #
    # ------------------------------------------------------------------ #
    with CLI.status(f"Loading TTS Engine ({Config.TTS_ENGINE})..."):
        if Config.TTS_ENGINE == "kokoro":
            from modules.tts_kokoro import KokoroTTS
            tts_model = KokoroTTS(
                lang=Config.KOKORO_LANG,
                voice=Config.KOKORO_VOICE,
            )
        elif Config.TTS_ENGINE == "vits_ja":
            from modules.tts_vits_ja import VitsJaTTS
            tts_model = VitsJaTTS(
                hf_repo_id=Config.VITS_JA_HF_REPO_ID,
                onnx_file=Config.VITS_JA_ONNX_FILE,
                config_file=Config.VITS_JA_CONFIG_FILE,
                hf_revision=Config.VITS_JA_HF_REVISION,
                cache_dir=Config.VITS_JA_CACHE_DIR,
                speaker_id=Config.VITS_JA_SPEAKER_ID,
                quantize=Config.VITS_JA_QUANTIZE,
                intra_threads=Config.ORT_INTRA_THREADS,
                inter_threads=Config.ORT_INTER_THREADS,
            )
        elif Config.TTS_ENGINE == "vits_ar":
            from modules.tts_vits_ar import VitsArTTS
            tts_model = VitsArTTS(
                hf_repo_id=Config.VITS_AR_HF_REPO_ID,
                onnx_file=Config.VITS_AR_ONNX_FILE,
                config_file=Config.VITS_AR_CONFIG_FILE,
                hf_revision=Config.VITS_AR_HF_REVISION,
                cache_dir=Config.VITS_AR_CACHE_DIR,
                speaker_id=Config.VITS_AR_SPEAKER_ID,
                quantize=Config.VITS_AR_QUANTIZE,
                intra_threads=Config.ORT_INTRA_THREADS,
                inter_threads=Config.ORT_INTER_THREADS,
            )
        else:
            from modules.tts_chattts import ChatTTSModel
            tts_model = ChatTTSModel(
                speaker_seed=Config.CHAT_TTS_SPEAKER_SEED,
                device=Config.CHAT_TTS_DEVICE,
                max_new_tokens=Config.CHAT_TTS_MAX_NEW_TOKENS,
                cpu_threads=Config.CHAT_TTS_CPU_THREADS,
                enable_cache=Config.CHAT_TTS_ENABLE_CACHE,
                model_source=Config.CHAT_TTS_MODEL_SOURCE,
                cache_dir=Config.CHAT_TTS_CACHE_DIR,
                stream_batch=Config.CHAT_TTS_STREAM_BATCH,
            )

    tts_sample_rate = tts_model.output_sample_rate

    # ------------------------------------------------------------------ #
    # 4. Audio I/O  — SpeakerPlayer initialized with TTS sample rate     #
    # ------------------------------------------------------------------ #
    with CLI.status("Initializing Audio Interfaces..."):
        # Pass the TTS engine's native rate; SpeakerPlayer uses it for both
        # play_audio() (PCM fallback) and play_stream() (OutputStream samplerate).
        speaker = SpeakerPlayer(sample_rate=tts_sample_rate)

    # ------------------------------------------------------------------ #
    # 5. Wire into ConversationManager and start                          #
    # ------------------------------------------------------------------ #
    with CLI.status("Wiring up Conversation Manager..."):
        manager = ConversationManager(
            audio_in  = mic,
            stt       = stt_model,
            llm       = llm_model,
            tts       = tts_model,
            audio_out = speaker,
        )

    CLI.print_header("System Ready")
    manager.start_loop()


if __name__ == "__main__":
    main()
