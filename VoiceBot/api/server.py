"""
VoiceBot Web API Server
=======================

Bridges the existing VoiceBot engine (LLM + TTS) to a REST API consumed by
the React frontend.  All heavy model loading happens once at startup in a
thread executor so the event loop is never blocked.

Start the server from the VoiceBot/ directory:
    uvicorn api.server:app --reload --port 8000

Endpoints
---------
GET  /api/health      — liveness / readiness probe
GET  /api/config      — active engine + available engines
POST /api/chat        — send text, receive {text, audio_b64} response
"""
# Path: api/server.py
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import re
import sys
import wave
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Make sure project root is importable ──────────────────────────────────── #
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import Config  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(name)s │ %(message)s")
logger = logging.getLogger("voicebot.api")

# ── Singletons (populated in lifespan) ───────────────────────────────────── #
_tts_model = None
_llm_model = None
_tts_sample_rate: int = 24000
_engine_name: str = Config.TTS_ENGINE


# ── Helpers ──────────────────────────────────────────────────────────────── #

def _pcm_float32_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """Wrap raw float32 LE PCM in a WAV container (all browsers can decode WAV)."""
    audio = np.frombuffer(pcm_bytes, dtype=np.float32)
    audio_i16 = (audio * 32767.0).clip(-32768.0, 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_i16.tobytes())
    return buf.getvalue()


def _split_sentences(text: str) -> list[str]:
    """
    Language-aware sentence splitter.

    Uses pysbd for English (already in requirements), and simple regex splits
    for Japanese / Arabic where sentence boundaries differ.
    """
    engine = _engine_name

    if engine == "vits_ja":
        # Japanese sentence terminators
        parts = re.split(r"(?<=[。！？\n])\s*", text)
    elif engine == "vits_ar":
        # Arabic / mixed terminators
        parts = re.split(r"(?<=[.!?؟\n])\s*", text)
    else:
        try:
            import pysbd  # type: ignore
            parts = pysbd.Segmenter(language="en", clean=False).segment(text)
        except Exception:
            parts = re.split(r"(?<=[.!?])\s+", text)

    return [p.strip() for p in parts if p.strip()]


def _synthesize_full(text: str) -> Optional[bytes]:
    """Synthesize the full *text* by splitting into sentences, then concatenating PCM."""
    sentences = _split_sentences(text)
    pcm_parts: list[bytes] = []

    for sentence in sentences:
        if not sentence:
            continue
        try:
            chunks = list(_tts_model.synthesize(sentence, speed=1.0))
            if chunks:
                pcm_parts.append(b"".join(chunks))
        except Exception as exc:
            logger.warning("TTS failed for sentence '%s…': %s", sentence[:40], exc)

    return b"".join(pcm_parts) if pcm_parts else None


def _load_models() -> None:
    """Blocking model bootstrap — called once in a thread executor at startup."""
    global _tts_model, _llm_model, _tts_sample_rate, _engine_name

    engine = Config.TTS_ENGINE
    _engine_name = engine
    logger.info("Bootstrapping engine: %s", engine)

    # LLM
    from modules.llm_brain import LLMBrain  # noqa: PLC0415
    _llm_model = LLMBrain(
        api_key=Config.LLM_API_KEY,
        model_name=Config.LLM_MODEL_NAME,
        base_url=Config.LLM_BASE_URL,
    )
    logger.info("LLM ready: %s", Config.LLM_MODEL_NAME)

    # TTS — same branching logic as main.py
    if engine == "vits_ja":
        from modules.model_downloader import download_vits_ja_model  # noqa: PLC0415
        from modules.tts_vits_ja import VitsJaTTS  # noqa: PLC0415

        onnx_path, config_path = download_vits_ja_model(
            repo_id=Config.VITS_JA_HF_REPO_ID,
            onnx_filename=Config.VITS_JA_ONNX_FILE,
            config_filename=Config.VITS_JA_CONFIG_FILE,
            cache_dir=Config.VITS_JA_CACHE_DIR,
            revision=Config.VITS_JA_HF_REVISION,
            quantize=Config.VITS_JA_QUANTIZE,
        )
        _tts_model = VitsJaTTS(onnx_path, config_path, speaker_id=Config.VITS_JA_SPEAKER_ID)
        _tts_sample_rate = _tts_model.output_sample_rate
        _llm_model.save_profile(new_summary=None, language="Japanese")

    elif engine == "vits_ar":
        from modules.model_downloader import download_vits_ar_model  # noqa: PLC0415
        from modules.tts_vits_ar import VitsArTTS  # noqa: PLC0415

        onnx_path, config_path = download_vits_ar_model(
            repo_id=Config.VITS_AR_HF_REPO_ID,
            onnx_filename=Config.VITS_AR_ONNX_FILE,
            config_filename=Config.VITS_AR_CONFIG_FILE,
            cache_dir=Config.VITS_AR_CACHE_DIR,
            revision=Config.VITS_AR_HF_REVISION,
            quantize=Config.VITS_AR_QUANTIZE,
        )
        _tts_model = VitsArTTS(onnx_path, config_path, speaker_id=Config.VITS_AR_SPEAKER_ID)
        _tts_sample_rate = _tts_model.output_sample_rate
        _llm_model.save_profile(new_summary=None, language="Arabic")

    else:  # kokoro (default)
        from modules.tts_kokoro import KokoroTTS  # noqa: PLC0415

        _tts_model = KokoroTTS(lang=Config.KOKORO_LANG, voice=Config.KOKORO_VOICE)
        _tts_sample_rate = 24000

    logger.info("TTS ready — engine=%s  sample_rate=%d Hz", engine, _tts_sample_rate)


# ── FastAPI app ───────────────────────────────────────────────────────────── #

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_models)
    yield


app = FastAPI(title="VoiceBot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ──────────────────────────────────────────────────────── #

class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    text: str
    audio_b64: Optional[str] = None
    engine: str


# ── Routes ────────────────────────────────────────────────────────────────── #

@app.get("/api/health")
def health():
    ready = _tts_model is not None and _llm_model is not None
    return {
        "status": "ready" if ready else "loading",
        "engine": _engine_name,
        "sample_rate": _tts_sample_rate,
    }


@app.get("/api/config")
def get_config():
    return {
        "engine": _engine_name,
        "available_engines": ["kokoro", "vits_ja", "vits_ar"],
        "sample_rate": _tts_sample_rate,
        "model": Config.LLM_MODEL_NAME,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _llm_model is None or _tts_model is None:
        raise HTTPException(503, "Models are still initializing — try again in a moment.")

    text = req.text.strip()
    if not text:
        raise HTTPException(422, "text cannot be empty.")

    loop = asyncio.get_event_loop()

    # 1 — LLM generation (blocking → thread)
    def _gen() -> str:
        return "".join(_llm_model.generate_response(text))

    try:
        response_text: str = await loop.run_in_executor(None, _gen)
    except Exception as exc:
        logger.exception("LLM generation failed")
        raise HTTPException(500, f"LLM error: {exc}") from exc

    # 2 — TTS synthesis (blocking → thread)
    pcm_bytes: Optional[bytes] = await loop.run_in_executor(
        None, _synthesize_full, response_text
    )

    audio_b64: Optional[str] = None
    if pcm_bytes:
        wav_bytes = _pcm_float32_to_wav(pcm_bytes, _tts_sample_rate)
        audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

    return ChatResponse(text=response_text, audio_b64=audio_b64, engine=_engine_name)
