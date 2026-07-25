"""
Text-to-Speech Module.

This module provides a high-performance implementation of the ITTSModel interface
using the Kokoro-ONNX runtime. It generates extremely fast, natural-sounding
speech locally without requiring a GPU or network access.
"""
# Path: modules/tts_kokoro.py
import os
import urllib.request
import numpy as np
from typing import Iterator
from core.interfaces import ITTSModel
from utils.logger import get_logger
from utils.ui import CLI
from kokoro_onnx import Kokoro

logger = get_logger(__name__)

class KokoroTTS(ITTSModel):
    """
    High-performance TTS implementation using Kokoro-ONNX.
    
    Provides sub-second latency on standard CPUs. It manages the downloading
    and loading of the ONNX models automatically upon instantiation.
    """
    def __init__(self, lang: str = "a", voice: str = "af_heart") -> None:
        """
        Initializes the Kokoro TTS engine and ensures models are present.

        Args:
            lang (str): The language code (e.g., 'a' for American English).
            voice (str): The specific voice model to use (e.g., 'af_heart').
        """
        self.lang = "en-us" if lang == "a" else lang
        self.voice = voice
        
        # Ensure models directory exists
        self.models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.model_path = os.path.join(self.models_dir, "kokoro-v1.0.onnx")
        self.voices_path = os.path.join(self.models_dir, "voices-v1.0.bin")
        
        self._ensure_models_downloaded()
        
        try:
            with CLI.status("Loading Kokoro-ONNX TTS Model...", spinner="dots"):
                self.kokoro = Kokoro(self.model_path, self.voices_path)
            logger.info("Initialized Kokoro-ONNX TTS Engine.")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro-ONNX: {e}")
            raise

    def _download_with_retry(self, url, dest, expected_size, max_retries=3):
        """Robust downloader with retries and size validation."""
        for attempt in range(max_retries):
            try:
                # If file exists but is way too small, it's a corrupted/partial download
                if os.path.exists(dest) and os.path.getsize(dest) < expected_size:
                    os.remove(dest)
                    
                if not os.path.exists(dest):
                    urllib.request.urlretrieve(url, dest)
                    logger.info(f"Downloaded successfully to {dest}")
                return # Success
                
            except urllib.error.ContentTooShortError:
                logger.warning(f"Connection dropped during download (attempt {attempt + 1}/{max_retries}). Retrying...")
            except Exception as e:
                logger.warning(f"Download error: {e}. Retrying...")
                
        raise Exception(f"Failed to download {url} after {max_retries} attempts. Please check your internet connection.")

    def _ensure_models_downloaded(self):
        """Downloads the ONNX models if they don't exist or are corrupted."""
        model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
        
        # model is ~325MB, voices is ~80MB. We use safe minimums to detect partial downloads.
        if not os.path.exists(self.model_path) or os.path.getsize(self.model_path) < 300_000_000:
            with CLI.status("Downloading kokoro-v1.0.onnx (325MB - This may take a while)...", spinner="arrow3"):
                self._download_with_retry(model_url, self.model_path, 300_000_000)
                
        if not os.path.exists(self.voices_path) or os.path.getsize(self.voices_path) < 2_000_000:
            with CLI.status("Downloading voices-v1.0.bin (3MB)...", spinner="arrow3"):
                self._download_with_retry(voices_url, self.voices_path, 2_000_000)

    def synthesize(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """
        Synthesizes text into streaming audio bytes using the ONNX model.

        The model generates audio for the entire text instantly. It strips any
        synthetic robotic silence from the edges before yielding the raw audio bytes.

        Args:
            text (str): The string of text to convert to speech.
            speed (float): Playback speed multiplier (default: 1.0).

        Yields:
            bytes: The synthesized raw PCM audio data.
        """
        try:
            # Kokoro-ONNX creates the full audio for the chunk instantly
            samples, sample_rate = self.kokoro.create(
                text,
                voice=self.voice,
                speed=speed,
                lang=self.lang
            )
            
            # The samples are already a numpy array of floats
            audio_np = np.array(samples, dtype=np.float32)
            
            # Trim silence (robotic padding) from the ends
            threshold = 0.01
            non_silent_indices = np.where(np.abs(audio_np) > threshold)[0]
            if len(non_silent_indices) > 0:
                start_idx = max(0, non_silent_indices[0] - 200) # Leave a tiny pad
                end_idx = min(len(audio_np), non_silent_indices[-1] + 200)
                audio_np = audio_np[start_idx:end_idx]
                
            yield audio_np.tobytes()
            
        except Exception as e:
            logger.error(f"Error during TTS synthesis stream: {e}")