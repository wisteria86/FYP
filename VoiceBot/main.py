"""
Main Entry Point for the Voice Assistant Application.

This module is responsible for bootstrapping the application. It initializes all
hardware interfaces (microphone, speaker) and machine learning models (STT, LLM, TTS),
then injects them into the central orchestrator (ConversationManager) before
starting the main event loop.

TTS engine is selected via the TTS_ENGINE environment variable (see config.py):
  - "kokoro"  → KokoroTTS (default, English)
  - "vits_ja" → VitsJaTTS (Japanese, requires HuggingFace download on first run)
  - "vits_ar" → VitsArTTS (Arabic, requires HuggingFace download on first run
                 + espeak-ng system binary for G2P)
"""
# Path: main.py
from config import Config
from core.conversation_manager import ConversationManager
from modules.stt_whisper import WhisperSTT
from modules.llm_brain import LLMBrain
from io_interfaces.mic_recorder import MicRecorder
from io_interfaces.speaker_player import SpeakerPlayer
from utils.ui import CLI


def main() -> None:
    """
    Initializes and starts the voice assistant application.

    Construction order matters: TTS is built first so its output_sample_rate
    can be passed to SpeakerPlayer, eliminating any need for resampling.

    Steps:
    1. Load STT and LLM models (hardware-agnostic, order-independent).
    2. Load TTS model (engine selected by Config.TTS_ENGINE).
    3. Update the LLM language persona to match the selected engine's language.
    4. Initialize audio I/O, passing TTS native sample rate to SpeakerPlayer.
    5. Wire everything into ConversationManager and start the loop.
    """
    CLI.print_header("Voice Assistant Initialization")

    # ------------------------------------------------------------------ #
    # 1. Speech-to-Text                                                   #
    # ------------------------------------------------------------------ #
    with CLI.status("Loading Whisper STT (This may take a moment)..."):
        stt_model = WhisperSTT(model_size=Config.WHISPER_MODEL_SIZE)

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
    # 3. TTS Engine — branched on Config.TTS_ENGINE                      #
    # ------------------------------------------------------------------ #
    tts_sample_rate: int  # will be set by whichever branch runs

    if Config.TTS_ENGINE == "vits_ja":
        # --- Japanese VITS ONNX path ---
        from modules.model_downloader import download_vits_ja_model
        from modules.tts_vits_ja import VitsJaTTS

        onnx_path, config_path = download_vits_ja_model(
            repo_id         = Config.VITS_JA_HF_REPO_ID,
            onnx_filename   = Config.VITS_JA_ONNX_FILE,
            config_filename = Config.VITS_JA_CONFIG_FILE,
            cache_dir       = Config.VITS_JA_CACHE_DIR,
            revision        = Config.VITS_JA_HF_REVISION,
            quantize        = Config.VITS_JA_QUANTIZE,
        )

        with CLI.status("Loading VITS Japanese TTS..."):
            tts_model = VitsJaTTS(
                onnx_path   = onnx_path,
                config_path = config_path,
                speaker_id  = Config.VITS_JA_SPEAKER_ID,
            )

        # Use the model's declared native rate (e.g. 22050 Hz) — no resampling
        tts_sample_rate = tts_model.output_sample_rate

        # Wire Japanese language into the LLM persona (persisted to user_profile.json)
        with CLI.status("Configuring Japanese persona..."):
            llm_model.save_profile(new_summary=None, language="Japanese")

    elif Config.TTS_ENGINE == "vits_ar":
        # --- Arabic VITS ONNX path ---
        from modules.model_downloader import download_vits_ar_model
        from modules.tts_vits_ar import VitsArTTS

        onnx_path, config_path = download_vits_ar_model(
            repo_id         = Config.VITS_AR_HF_REPO_ID,
            onnx_filename   = Config.VITS_AR_ONNX_FILE,
            config_filename = Config.VITS_AR_CONFIG_FILE,
            cache_dir       = Config.VITS_AR_CACHE_DIR,
            revision        = Config.VITS_AR_HF_REVISION,
            quantize        = Config.VITS_AR_QUANTIZE,
        )

        with CLI.status("Loading VITS Arabic TTS..."):
            tts_model = VitsArTTS(
                onnx_path   = onnx_path,
                config_path = config_path,
                speaker_id  = Config.VITS_AR_SPEAKER_ID,
            )

        # Use the model's declared native rate (22050 Hz for kareem-medium) — no resampling
        tts_sample_rate = tts_model.output_sample_rate

        # Wire Arabic language into the LLM persona (persisted to user_profile.json)
        with CLI.status("Configuring Arabic persona..."):
            llm_model.save_profile(new_summary=None, language="Arabic")

    else:
        # --- Default: Kokoro English path (unchanged behaviour) ---
        from modules.tts_kokoro import KokoroTTS

        with CLI.status("Loading Kokoro TTS (This may take a moment)..."):
            tts_model = KokoroTTS(
                lang=Config.KOKORO_LANG,
                voice=Config.KOKORO_VOICE,
            )

        tts_sample_rate = 24000  # Kokoro native output rate

    # ------------------------------------------------------------------ #
    # 4. Audio I/O  — SpeakerPlayer initialized with TTS sample rate     #
    # ------------------------------------------------------------------ #
    with CLI.status("Initializing Audio Interfaces..."):
        mic = MicRecorder(
            sample_rate=Config.SAMPLE_RATE,
            record_seconds=Config.RECORD_SECONDS,
        )
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