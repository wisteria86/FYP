"""ChatTTS implementation for the VoiceBot TTS interface."""

import os
import threading
from typing import Iterator, Optional

import ChatTTS
import numpy as np
import torch

from core.interfaces import ITTSModel
from utils.logger import get_logger
from utils.ui import CLI


logger = get_logger(__name__)


class ChatTTSModel(ITTSModel):
    """Local ChatTTS engine used for all input languages."""

    output_sample_rate = 24000

    def __init__(
        self,
        speaker_seed: int = 42,
        device: Optional[str] = "cpu",
        max_new_tokens: int = 512,
        cpu_threads: int = 4,
        enable_cache: bool = True,
        model_source: str = "huggingface",
        cache_dir: str = "models/chattts",
        stream_batch: int = 12,
    ) -> None:
        self._lock = threading.Lock()
        self.max_new_tokens = max(96, max_new_tokens)
        self.stream_batch = max(4, stream_batch)
        if not enable_cache:
            logger.warning(
                "ChatTTS 0.2.5 requires its generation cache; overriding "
                "enable_cache=False to prevent invalid audio-token embeddings."
            )
            enable_cache = True
        try:
            with CLI.status("Loading ChatTTS Model...", spinner="dots"):
                # Avoid Torch saturating every core and allocating oversized workspaces.
                torch.set_num_threads(max(1, cpu_threads))
                try:
                    torch.set_num_interop_threads(1)
                except RuntimeError:
                    # Torch permits setting this only once per process (e.g. API reloads).
                    pass
                self.chat = ChatTTS.Chat()
                cache_path = os.path.abspath(cache_dir)
                os.makedirs(cache_path, exist_ok=True)
                load_kwargs = {
                    "source": model_source,
                    "custom_path": cache_path,
                    "compile": False,
                    "enable_cache": enable_cache,
                }
                resolved_device = device
                if not resolved_device or resolved_device == "auto":
                    resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
                load_kwargs["device"] = torch.device(resolved_device)
                if not self.chat.load(**load_kwargs):
                    raise RuntimeError("ChatTTS model assets could not be loaded")
                with torch.random.fork_rng():
                    torch.manual_seed(speaker_seed)
                    self.speaker = self.chat.sample_random_speaker()
            logger.info("Initialized ChatTTS engine for all languages.")
        except Exception as exc:
            logger.error(f"Failed to initialize ChatTTS: {exc}")
            raise

    @staticmethod
    def _apply_speed(audio: np.ndarray, speed: float) -> np.ndarray:
        if speed <= 0:
            raise ValueError("TTS speed must be greater than zero")
        if np.isclose(speed, 1.0) or audio.size < 2:
            return audio
        length = max(1, int(audio.size / speed))
        return np.interp(
            np.linspace(0, audio.size - 1, length),
            np.arange(audio.size),
            audio,
        ).astype(np.float32)

    def synthesize(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """Yield mono 24 kHz float32 PCM for any supplied text."""
        if not text or not text.strip():
            return
            
        # Sanitize input to ChatTTS to avoid errors or glitches
        import re
        text = re.sub(r'[\n\r\t]', ' ', text)
        text = re.sub(r'[:;：；]', ',', text) # Replace colon/semicolon with comma
        text = re.sub(r'[\[\]\(\)\{\}\*~_#$^&|<>\'"「」『』【】+=\-\\/]', '', text) # Strip symbols and markdown
        text = text.strip()
        
        if not text:
            return
            
        try:
            # Bound the KV/logit tensors to the sentence size instead of ChatTTS's
            # memory-heavy 2,048-token default. Roughly six audio tokens/character
            # leaves headroom for normal speech while respecting the configured cap.
            token_limit = min(self.max_new_tokens, max(96, len(text.strip()) * 6))
            params = ChatTTS.Chat.InferCodeParams(
                spk_emb=self.speaker,
                max_new_token=token_limit,
                show_tqdm=False,
                stream_batch=self.stream_batch,
                pass_first_n_batches=1,
            )
            with self._lock, torch.inference_mode():
                generated = self.chat.infer(
                    [text.strip()],
                    stream=True,
                    split_text=False,
                    params_infer_code=params,
                    skip_refine_text=True,
                )
                produced = False
                for batch in generated:
                    audio = np.asarray(batch[0], dtype=np.float32).reshape(-1)
                    if audio.size:
                        produced = True
                        yield np.ascontiguousarray(audio).tobytes()
                if not produced:
                    logger.warning("ChatTTS returned no audio.")
        except Exception:
            logger.exception("Error during ChatTTS synthesis")

    def interrupt(self) -> None:
        """Cancel an in-flight ChatTTS generation."""
        self.chat.interrupt()
