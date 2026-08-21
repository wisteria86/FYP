# Path: config.py
import os
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

class Config:
    """Central configuration class."""
    # LLM Settings
    COMMUNICATION_LANGUAGE = os.getenv("COMMUNICATION_LANGUAGE", "English")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "your-default-key-here")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen/qwen3-32b")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1") # GroqCloud base URL

    # Whisper Settings
    # Memory-safe multilingual default. Override with "small" for more accuracy.
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
    WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "4"))
    WHISPER_WORKERS = int(os.getenv("WHISPER_WORKERS", "1"))

    # Audio IO Settings
    SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
    RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", "5"))
    HEADSET_MODE = os.getenv("HEADSET_MODE", "False").lower() == "true"
    MIC_DEVICE = os.getenv("MIC_DEVICE") or None  # input device index or name

    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # TTS Engine Selection
    # ---------------------------------------------------------------------------
    # "kokoro"  → use KokoroTTS (default, English). No extra downloads.
    # "vits_ja" → use VitsJaTTS (Japanese). Auto-downloads model from HuggingFace
    # "vits_ar" → use VitsArTTS (Arabic). Auto-downloads model from HuggingFace
    # ChatTTS is preserved, but we dynamically select the best TTS engine for the language.
    if COMMUNICATION_LANGUAGE.lower() == "japanese":
        TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro")
        KOKORO_LANG = os.getenv("KOKORO_LANG", "j")
        KOKORO_VOICE = os.getenv("KOKORO_VOICE", "jf_alpha")
    elif COMMUNICATION_LANGUAGE.lower() == "arabic":
        TTS_ENGINE = os.getenv("TTS_ENGINE", "vits_ar")
        KOKORO_LANG = os.getenv("KOKORO_LANG", "a")
        KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
    else:
        TTS_ENGINE = os.getenv("TTS_ENGINE", "chattts")
        KOKORO_LANG = os.getenv("KOKORO_LANG", "a")
        KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
    
    CHAT_TTS_PERSONAS = {
        "English": 42,
        "Japanese": 1337,
        "Arabic": 9001
    }
    CHAT_TTS_SPEAKER_SEED = int(os.getenv("CHAT_TTS_SPEAKER_SEED", str(CHAT_TTS_PERSONAS.get(COMMUNICATION_LANGUAGE, 42))))
    CHAT_TTS_DEVICE = os.getenv("CHAT_TTS_DEVICE", "auto")
    CHAT_TTS_MODEL_SOURCE = os.getenv("CHAT_TTS_MODEL_SOURCE", "huggingface")
    CHAT_TTS_CACHE_DIR = os.getenv("CHAT_TTS_CACHE_DIR", "models/chattts")
    CHAT_TTS_MAX_NEW_TOKENS = int(os.getenv("CHAT_TTS_MAX_NEW_TOKENS", "512"))
    CHAT_TTS_CPU_THREADS = int(os.getenv("CHAT_TTS_CPU_THREADS", "4"))
    CHAT_TTS_STREAM_BATCH = int(os.getenv("CHAT_TTS_STREAM_BATCH", "12"))
    # Required by ChatTTS 0.2.5 generation; token/thread limits bound its memory use.
    CHAT_TTS_ENABLE_CACHE = True
    ENABLE_THINKING_AUDIO = os.getenv("ENABLE_THINKING_AUDIO", "False").lower() == "true"

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

    # ---------------------------------------------------------------------------
    # VITS Arabic TTS Settings  (only active when TTS_ENGINE=vits_ar)
    # ---------------------------------------------------------------------------
    # Model: rhasspy/piper-voices — ar/ar_JO/kareem/medium on HuggingFace.
    # Dialect: Jordanian Arabic (ar_JO), broadly intelligible as Modern Standard Arabic.
    # Phonemizer: espeak-ng 'ar' voice (baked into piper config).
    #   Handles undiacritized Arabic text via letter-to-sound rules — no separate
    #   diacritization step is required for inference with this voice.
    #
    # ⚠ LICENSE NOTICE: The Kareem voice is trained on the Arabic Speech Corpus
    #   by Nawar Halabi, released under CC BY 4.0. Attribution is required:
    #   http://en.arabicspeechcorpus.com/
    #   The piper-voices repository license is MIT.
    #   HuggingFace repo: https://huggingface.co/rhasspy/piper-voices
    #
    # PRECISION: The kareem-medium model ships as fp32 ONNX — preferred for CPU
    # inference (no fp16 penalty). VITS_AR_QUANTIZE=True (default) generates an
    # int8 copy via onnxruntime dynamic quantization on first run for even faster
    # CPU throughput (3-4x speedup). Set to False to use the native fp32 model.
    VITS_AR_HF_REPO_ID   = os.getenv("VITS_AR_HF_REPO_ID",  "rhasspy/piper-voices")
    VITS_AR_ONNX_FILE    = os.getenv("VITS_AR_ONNX_FILE",   "ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx")
    VITS_AR_CONFIG_FILE  = os.getenv("VITS_AR_CONFIG_FILE",  "ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json")
    VITS_AR_HF_REVISION  = os.getenv("VITS_AR_HF_REVISION",  "main")
    VITS_AR_CACHE_DIR    = os.getenv("VITS_AR_CACHE_DIR",    "models/vits_ar")
    VITS_AR_SPEAKER_ID   = int(os.getenv("VITS_AR_SPEAKER_ID",  "0"))

    # Native audio sample rate of the kareem-medium model (22050 Hz, standard piper rate).
    # SpeakerPlayer is initialized with this value directly — no resampling needed.
    VITS_AR_SAMPLE_RATE  = int(os.getenv("VITS_AR_SAMPLE_RATE", "22050"))

    # When True, onnxruntime.quantization.quantize_dynamic() converts the
    # downloaded fp32 model to int8 and saves a local "*-int8.onnx" cache.
    # The int8 model is used for all subsequent inference (3-4x faster on CPU).
    # fp32 → int8 quantization is fast (runs once, offline, ~30s for a 64MB model).
    VITS_AR_QUANTIZE     = os.getenv("VITS_AR_QUANTIZE", "True").lower() == "true"
