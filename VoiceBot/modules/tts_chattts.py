"""ChatTTS implementation for the VoiceBot TTS interface."""

import os
import threading
import re
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
        device: Optional[str] = "auto",
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
        self.device = self._resolve_device(device)
        self.speaker_seed = speaker_seed
        self.module_devices: dict[str, str] = {}
        self.last_cuda_peak_mb = 0.0
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
                if self.device.type == "cuda":
                    torch.cuda.set_device(self.device)
                    # Ampere and newer cards accelerate ChatTTS's float32 matrix
                    # multiplications substantially with TF32, without changing
                    # model weights or the public synthesis API.
                    torch.set_float32_matmul_precision("high")
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    torch.backends.cudnn.benchmark = True
                self.chat = ChatTTS.Chat()
                cache_path = os.path.abspath(cache_dir)
                os.makedirs(cache_path, exist_ok=True)
                load_kwargs = {
                    "source": model_source,
                    "custom_path": cache_path,
                    "compile": False,
                    "enable_cache": enable_cache,
                }
                load_kwargs["device"] = self.device
                if not self.chat.load(**load_kwargs):
                    raise RuntimeError("ChatTTS model assets could not be loaded")
                if self.device.type == "cuda" and torch.cuda.is_bf16_supported():
                    self.chat.gpt.gpt.to(dtype=torch.bfloat16)
                self.module_devices = self._inspect_module_devices()
                if self.device.type == "cuda":
                    non_cuda = {
                        name: actual for name, actual in self.module_devices.items()
                        if name in {"gpt", "dvae", "decoder", "embed", "vocos"} and not actual.startswith("cuda")
                    }
                    if non_cuda:
                        raise RuntimeError(f"ChatTTS CUDA verification failed; modules remained off GPU: {non_cuda}")
                with torch.random.fork_rng():
                    torch.manual_seed(speaker_seed)
                    self.speaker = self.chat.sample_random_speaker()
            logger.info(
                "Initialized ChatTTS on %s (%s). Module devices: %s",
                self.device,
                torch.cuda.get_device_name(self.device) if self.device.type == "cuda" else "CPU",
                self.module_devices,
            )
        except Exception as exc:
            logger.error(f"Failed to initialize ChatTTS: {exc}")
            raise

    @staticmethod
    def _resolve_device(requested: Optional[str]) -> torch.device:
        value = (requested or "auto").strip().lower()
        if value == "auto":
            value = "cuda:0" if torch.cuda.is_available() else "cpu"
        if value.startswith("cuda"):
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "ChatTTS was configured for CUDA, but this PyTorch build cannot access CUDA. "
                    f"Installed torch={torch.__version__}, CUDA build={torch.version.cuda or 'CPU-only'}."
                )
            resolved = torch.device(value)
            index = 0 if resolved.index is None else resolved.index
            if index >= torch.cuda.device_count():
                raise RuntimeError(f"ChatTTS requested CUDA device {index}, but only {torch.cuda.device_count()} device(s) are visible")
            return torch.device(f"cuda:{index}")
        if value != "cpu":
            raise ValueError("CHAT_TTS_DEVICE must be auto, cpu, cuda, or cuda:<index>")
        return torch.device("cpu")

    @staticmethod
    def _parameter_device(module) -> str:
        if module is None:
            return "missing"
        try:
            return str(next(module.parameters()).device)
        except (AttributeError, StopIteration, TypeError):
            return str(getattr(module, "device", "unknown"))

    def _inspect_module_devices(self) -> dict[str, str]:
        gpt_wrapper = getattr(self.chat, "gpt", None)
        return {
            "gpt": self._parameter_device(getattr(gpt_wrapper, "gpt", gpt_wrapper)),
            "dvae": self._parameter_device(getattr(self.chat, "dvae", None)),
            "decoder": self._parameter_device(getattr(self.chat, "decoder", None)),
            "embed": self._parameter_device(getattr(self.chat, "embed", None)),
            "vocos": self._parameter_device(getattr(self.chat, "vocos", None)),
        }

    def runtime_info(self) -> dict:
        info = {
            "backend": "cuda" if self.device.type == "cuda" else "cpu",
            "device": str(self.device),
            "device_name": torch.cuda.get_device_name(self.device) if self.device.type == "cuda" else "CPU",
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "module_devices": self.module_devices,
            "gpt_precision": str(self.chat.gpt.gpt.dtype),
            "speaker_seed": self.speaker_seed,
            "delivery": "continuous_utterance",
            "last_peak_memory_mb": round(self.last_cuda_peak_mb, 1),
        }
        if self.device.type == "cuda":
            info.update({
                "allocated_memory_mb": round(torch.cuda.memory_allocated(self.device) / 1024**2, 1),
                "reserved_memory_mb": round(torch.cuda.memory_reserved(self.device) / 1024**2, 1),
            })
        return info

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
        text = re.sub(r'[!?？。！？]', '.', text)
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
            )
            with self._lock, torch.inference_mode():
                if self.device.type == "cuda":
                    torch.cuda.reset_peak_memory_stats(self.device)
                # The API sends one complete WAV per short roleplay response.
                # Non-streaming inference avoids repeated generator/batch overhead
                # and is substantially faster for this delivery mode.
                generated = self.chat.infer(
                    [text.strip()],
                    stream=False,
                    split_text=False,
                    params_infer_code=params,
                    skip_refine_text=True,
                )
                if self.device.type == "cuda":
                    self.last_cuda_peak_mb = torch.cuda.max_memory_allocated(self.device) / 1024**2
                audio = np.asarray(generated[0], dtype=np.float32).reshape(-1) if len(generated) else np.array([], dtype=np.float32)
                if audio.size:
                    yield np.ascontiguousarray(audio).tobytes()
                else:
                    logger.warning("ChatTTS returned no audio.")
        except Exception:
            logger.exception("Error during ChatTTS synthesis")

    def synthesize_streaming(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """Decode each reply as one continuous utterance to avoid underruns.

        Sentence-by-sentence decoding can take longer than the previous
        sentence's playback, creating a gap even with a browser jitter buffer.
        Keep natural prosody and continuity within each speaker's reply.
        """
        if not text or not text.strip():
            return
        import re
        text = re.sub(r'[\n\r\t]', ' ', text)
        text = re.sub(r'[:;：；]', ',', text)
        text = re.sub(r'[!?？。！？]', '.', text)
        text = re.sub(r'[\[\]\(\)\{\}\*~_#$^&|<>\'"「」『』【】+=\-\\/]', '', text).strip()
        if not text:
            return
        params = ChatTTS.Chat.InferCodeParams(
            spk_emb=self.speaker,
            max_new_token=min(self.max_new_tokens, max(96, len(text) * 6)),
            show_tqdm=False,
            stream_batch=self.stream_batch,
            stream_speed=12000,
            pass_first_n_batches=1,
        )
        # Preserve a single utterance/voice, but deliver decoded audio as it arrives.
        with self._lock, torch.inference_mode():
            for wavs in self.chat.infer(
                [text], stream=True, split_text=False,
                params_infer_code=params, skip_refine_text=True,
            ):
                audio=np.asarray(wavs[0], dtype=np.float32).reshape(-1)
                if audio.size:
                    yield np.ascontiguousarray(audio).tobytes()

    def interrupt(self) -> None:
        """Cancel an in-flight ChatTTS generation."""
        self.chat.interrupt()

    def close(self) -> None:
        """Release model references and cached VRAM during an engine switch."""
        chat = getattr(self, "chat", None)
        if chat is not None:
            try:
                chat.unload()
            except Exception:
                logger.debug("ChatTTS unload reported an error", exc_info=True)
        self.chat = None
        self.speaker = None
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
