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
    
    # Whisper Settings
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small.en")
    
    # Kokoro TTS Settings
    KOKORO_LANG = os.getenv("KOKORO_LANG", "a") # 'a' = American English, 'b' = British
    KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart") # Default Kokoro voice
    
    # Audio IO Settings
    SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
    RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", "5"))
    HEADSET_MODE = os.getenv("HEADSET_MODE", "True").lower() == "true"