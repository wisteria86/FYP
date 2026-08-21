# Path: config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Central configuration class."""
    # LLM Settings
    LLM_API_KEY = os.getenv("LLM_API_KEY", "your-default-key-here")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen/qwen3-32b")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1") # GroqCloud base URL
    COMMUNICATION_LANGUAGE = os.getenv("COMMUNICATION_LANGUAGE", "English")

    # Whisper Settings
    # NOTE: When using TTS_ENGINE=vits_ja, change this to "small" (multilingual)
    # so Whisper can transcribe Japanese speech. "small.en" is English-only.
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small.en")

    # Kokoro TTS Settings (used when TTS_ENGINE=kokoro, the default)
    KOKORO_LANG = os.getenv("KOKORO_LANG", "a")       # 'a' = American English, 'b' = British
    KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")

    # Audio IO Settings
    SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
    RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", "5"))
    HEADSET_MODE = os.getenv("HEADSET_MODE", "True").lower() == "true"

    # ---------------------------------------------------------------------------
    # TTS Engine Selection
    # ---------------------------------------------------------------------------
    # "kokoro"  → use KokoroTTS (default, English). No extra downloads.
    # "vits_ja" → use VitsJaTTS (Japanese). Auto-downloads model from HuggingFace
    #             on first run into VITS_JA_CACHE_DIR (gitignored).
    TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro")
    TTS_SPEED = float(os.getenv("TTS_SPEED", "1.0"))

    # ---------------------------------------------------------------------------
    # VITS Japanese TTS Settings  (only active when TTS_ENGINE=vits_ja)
    # ---------------------------------------------------------------------------
    # Model: ayousanz/piper-plus-tsukuyomi-chan on HuggingFace.
    #
    # ⚠ LICENSE NOTICE: The Tsukuyomi-chan voice corpus belongs to Rei Yumesaki.
    #   Usage requires attribution and restricts certain commercial uses.
    #   Corpus license: https://tyc.rei-yumesaki.net/material/corpus/
    #   HuggingFace repo: https://huggingface.co/ayousanz/piper-plus-tsukuyomi-chan
    #
    # PRECISION: fp32 ONNX is strongly preferred for CPU inference; fp16 is
    # significantly slower on CPU because no vectorized fp16 arithmetic exists.
    # The default below targets the fp16 file (only file available at time of
    # writing). Enable VITS_JA_QUANTIZE=True (default) to auto-generate a fast
    # int8 copy via onnxruntime dynamic quantization on first run.
    VITS_JA_HF_REPO_ID   = os.getenv("VITS_JA_HF_REPO_ID",  "ayousanz/piper-plus-tsukuyomi-chan")
    VITS_JA_ONNX_FILE    = os.getenv("VITS_JA_ONNX_FILE",   "tsukuyomi-chan-6lang-fp16.onnx")
    VITS_JA_CONFIG_FILE  = os.getenv("VITS_JA_CONFIG_FILE",  "config.json")
    VITS_JA_HF_REVISION  = os.getenv("VITS_JA_HF_REVISION",  "main")
    VITS_JA_CACHE_DIR    = os.getenv("VITS_JA_CACHE_DIR",    "models/vits_ja")
    VITS_JA_SPEAKER_ID   = int(os.getenv("VITS_JA_SPEAKER_ID",  "0"))

    # Native audio sample rate of the model (22050 Hz for tsukuyomi-chan).
    # SpeakerPlayer is initialized with this value directly — no resampling needed.
    VITS_JA_SAMPLE_RATE  = int(os.getenv("VITS_JA_SAMPLE_RATE", "22050"))

    # When True, onnxruntime.quantization.quantize_dynamic() converts the
    # downloaded model to int8 and saves a local "*-int8.onnx" cache. The int8
    # model is used for all subsequent inference (3–4× faster than fp16 on CPU).
    # Set to False only if you supply a native fp32 model via VITS_JA_ONNX_FILE.
    VITS_JA_QUANTIZE     = os.getenv("VITS_JA_QUANTIZE", "True").lower() == "true"

    # ONNX Runtime thread allocation for InferenceSession (0 = auto-detect cores).
    ORT_INTRA_THREADS    = int(os.getenv("ORT_INTRA_THREADS", "0"))
    ORT_INTER_THREADS    = int(os.getenv("ORT_INTER_THREADS", "0"))