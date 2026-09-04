"""FastAPI application for the Hikari employee-training prototype."""
from __future__ import annotations

import asyncio
import base64
import gc
import io
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from core.training_service import TrainingService  # noqa: E402
from core.monitoring import MetricsCollector  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("hikari.api")
training = TrainingService(ROOT / "data" / "hikari.db")
metrics = MetricsCollector()
_tts_model = _llm_model = _stt_model = None
_tts_sample_rate = 24000
_settings_path = ROOT / "data" / "runtime_settings.json"
_tts_switch_lock = threading.Lock()
_engine_catalog = {
    "chattts": {"name": "ChatTTS", "language": "Multilingual", "description": "Expressive local voice; highest resource use."},
    "kokoro": {"name": "Kokoro", "language": "English", "description": "Fast, clear local voice with low latency."},
    "vits_ja": {"name": "VITS Japanese", "language": "Japanese", "description": "Dedicated Japanese Piper-style voice."},
    "vits_ar": {"name": "VITS Arabic", "language": "Arabic", "description": "Dedicated Arabic Piper-style voice; requires eSpeak NG."},
}


def _saved_engine() -> str:
    try:
        value = json.loads(_settings_path.read_text(encoding="utf-8")).get("tts_engine", Config.TTS_ENGINE)
    except (OSError, ValueError, TypeError):
        value = Config.TTS_ENGINE
    return value if value in _engine_catalog else "chattts"


_engine_name = _saved_engine()
_model_errors: dict[str, str] = {}


def _engine_installed(engine: str) -> bool:
    if engine == "chattts":
        return (ROOT / "asset" / "gpt" / "model.safetensors").exists() or (ROOT / Config.CHAT_TTS_CACHE_DIR).exists()
    if engine == "kokoro":
        return (ROOT / "models" / "kokoro-v1.0.onnx").exists() and (ROOT / "models" / "voices-v1.0.bin").exists()
    cache = ROOT / (Config.VITS_JA_CACHE_DIR if engine == "vits_ja" else Config.VITS_AR_CACHE_DIR)
    return cache.exists() and any(cache.rglob("*.onnx")) and any(cache.rglob("*.json"))


def _build_tts_engine(engine: str):
    if engine == "chattts":
        from modules.tts_chattts import ChatTTSModel
        return ChatTTSModel(
            speaker_seed=Config.CHAT_TTS_SPEAKER_SEED, device=Config.CHAT_TTS_DEVICE,
            max_new_tokens=Config.CHAT_TTS_MAX_NEW_TOKENS, cpu_threads=Config.CHAT_TTS_CPU_THREADS,
            enable_cache=Config.CHAT_TTS_ENABLE_CACHE, model_source=Config.CHAT_TTS_MODEL_SOURCE,
            cache_dir=Config.CHAT_TTS_CACHE_DIR, stream_batch=Config.CHAT_TTS_STREAM_BATCH,
        )
    if engine == "kokoro":
        from modules.tts_kokoro import KokoroTTS
        return KokoroTTS(lang=Config.KOKORO_LANG, voice=Config.KOKORO_VOICE)
    from modules.model_downloader import download_vits_ar_model, download_vits_ja_model
    if engine == "vits_ja":
        from modules.tts_vits_ja import VitsJaTTS
        model_path, config_path = download_vits_ja_model(
            Config.VITS_JA_HF_REPO_ID, Config.VITS_JA_ONNX_FILE, Config.VITS_JA_CONFIG_FILE,
            Config.VITS_JA_CACHE_DIR, Config.VITS_JA_HF_REVISION, Config.VITS_JA_QUANTIZE,
        )
        return VitsJaTTS(model_path, config_path, Config.VITS_JA_SPEAKER_ID)
    if engine == "vits_ar":
        from modules.tts_vits_ar import VitsArTTS
        model_path, config_path = download_vits_ar_model(
            Config.VITS_AR_HF_REPO_ID, Config.VITS_AR_ONNX_FILE, Config.VITS_AR_CONFIG_FILE,
            Config.VITS_AR_CACHE_DIR, Config.VITS_AR_HF_REVISION, Config.VITS_AR_QUANTIZE,
        )
        return VitsArTTS(model_path, config_path, Config.VITS_AR_SPEAKER_ID)
    raise ValueError("Unknown TTS engine")


def _activate_tts_engine(engine: str, persist: bool = True) -> dict:
    global _tts_model, _tts_sample_rate, _engine_name
    if engine not in _engine_catalog:
        raise ValueError("Unknown TTS engine")
    with _tts_switch_lock:
        if engine == _engine_name and _tts_model is not None:
            return _tts_state()
        started = time.perf_counter()
        new_model = _build_tts_engine(engine)
        # Warm ChatTTS before exposing it so the first conversation does not stall.
        if engine == "chattts":
            for _ in new_model.synthesize_streaming("Ready.", speed=1.0):
                pass
        old_model = _tts_model
        _tts_model = new_model
        _tts_sample_rate = int(new_model.output_sample_rate)
        _engine_name = engine
        _model_errors.pop("tts", None)
        metrics.set_model_load("tts", (time.perf_counter() - started) * 1000, True)
        metrics.record("settings", "tts engine changed", (time.perf_counter() - started) * 1000, True, engine=engine)
        if persist:
            _settings_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = _settings_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps({"tts_engine": engine}, indent=2), encoding="utf-8")
            temp_path.replace(_settings_path)
        del old_model
        gc.collect()
        return _tts_state()


def _tts_state() -> dict:
    return {
        "active": _engine_name,
        "sample_rate": _tts_sample_rate,
        "engines": [
            {"id": engine, **details, "installed": _engine_installed(engine), "active": engine == _engine_name}
            for engine, details in _engine_catalog.items()
        ],
    }


def _public_reply(text: str) -> str:
    """Remove model reasoning before storage, display, or speech."""
    value = (text or "").strip()
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.IGNORECASE | re.DOTALL).strip()
    if re.search(r"<think\b", value, flags=re.IGNORECASE):
        # An unterminated block means generation ended before a public answer.
        return ""
    value = re.sub(r"</?think>", "", value, flags=re.IGNORECASE)
    return value.strip()


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    audio = np.frombuffer(pcm_bytes, dtype=np.float32).copy()
    # Phrase chunks are independently decoded by Web Audio. A short edge fade
    # prevents waveform discontinuities from becoming audible clicks.
    fade_samples = min(int(sample_rate * 0.004), audio.size // 2)
    if fade_samples:
        audio[:fade_samples] *= np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        audio[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
    audio_i16 = (audio * 32767.0).clip(-32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        wav.writeframes(audio_i16.tobytes())
    return buf.getvalue()


def _synthesize(text: str) -> Optional[str]:
    model, sample_rate = _tts_model, _tts_sample_rate
    if model is None:
        return None
    pcm_parts = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if sentence.strip():
            try:
                pcm_parts.extend(model.synthesize(sentence.strip(), speed=1.0))
            except Exception as exc:
                logger.warning("ChatTTS skipped a sentence: %s", exc)
    if not pcm_parts:
        return None
    return base64.b64encode(_pcm_to_wav(b"".join(pcm_parts), sample_rate)).decode("ascii")


def _load_models() -> None:
    global _llm_model, _stt_model
    started = time.perf_counter()
    try:
        from modules.llm_brain import LLMBrain
        _llm_model = LLMBrain(Config.LLM_API_KEY, Config.LLM_MODEL_NAME, Config.LLM_BASE_URL)
        metrics.set_model_load("llm", (time.perf_counter() - started) * 1000, True)
    except Exception as exc:
        metrics.set_model_load("llm", (time.perf_counter() - started) * 1000, False)
        _model_errors["llm"] = str(exc)
        logger.exception("LLM unavailable; deterministic roleplay fallback enabled")
    started = time.perf_counter()
    try:
        from modules.stt_whisper import WhisperSTT
        _stt_model = WhisperSTT(Config.WHISPER_MODEL_SIZE, Config.WHISPER_CPU_THREADS, Config.WHISPER_WORKERS, Config.WHISPER_DEVICE)
        metrics.set_model_load("stt", (time.perf_counter() - started) * 1000, True)
    except Exception as exc:
        metrics.set_model_load("stt", (time.perf_counter() - started) * 1000, False)
        _model_errors["stt"] = str(exc)
        logger.exception("Whisper unavailable; typed roleplay remains enabled")
    started = time.perf_counter()
    try:
        _activate_tts_engine(_engine_name, persist=False)
    except Exception as exc:
        metrics.set_model_load("tts", (time.perf_counter() - started) * 1000, False)
        _model_errors["tts"] = str(exc)
        logger.exception("Selected TTS engine unavailable; text roleplay remains enabled")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("HIKARI_SKIP_MODELS", "false").lower() != "true":
        await asyncio.get_running_loop().run_in_executor(None, _load_models)
    yield


app = FastAPI(title="Hikari Employee Trainer API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["Server-Timing", "X-Process-Time-Ms"])


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/monitor"):
            metrics.record("http", f"{request.method} {request.url.path}", duration_ms, status < 400, status=status)
        if 'response' in locals():
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
            response.headers["Server-Timing"] = f'app;dur={duration_ms:.1f}'


class SessionCreate(BaseModel):
    user_id: str = "demo"
    skill_id: str
    difficulty: str = "intermediate"


class RoleplayTurn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    duration_seconds: float = Field(default=0, ge=0, le=600)
    synthesize_audio: bool = True


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    correlation_id: Optional[str] = Field(default=None, max_length=80)


class TTSEngineSelection(BaseModel):
    engine: str = Field(pattern="^(chattts|kokoro|vits_ja|vits_ar)$")


class PostureSample(BaseModel):
    slouching: float = Field(ge=0, le=100)
    head_position: float = Field(ge=0, le=100)
    shoulder_alignment: float = Field(ge=0, le=100)
    body_orientation: float = Field(ge=0, le=100)


class MicrophoneMetric(BaseModel):
    event: str = Field(pattern="^(connected|listening|level|speech_detected|stopped|transcribed|error)$")
    device: Optional[str] = Field(default=None, max_length=160)
    state: Optional[str] = Field(default=None, max_length=40)
    level_percent: Optional[float] = Field(default=None, ge=0, le=100)
    peak_percent: Optional[float] = Field(default=None, ge=0, le=100)
    threshold_percent: Optional[float] = Field(default=None, ge=0, le=100)
    duration_ms: float = Field(default=0, ge=0, le=120000)
    transcript: Optional[str] = Field(default=None, max_length=500)
    sample_rate: Optional[int] = Field(default=None, ge=8000, le=192000)
    channel_count: Optional[int] = Field(default=None, ge=1, le=8)
    error: Optional[str] = Field(default=None, max_length=240)


@app.get("/api/health")
def health():
    components = {"llm": _llm_model is not None, "stt": _stt_model is not None, "tts": _tts_model is not None, "database": True}
    return {"status": "ready" if all(components.values()) else "degraded", "engine": _engine_name, "sample_rate": _tts_sample_rate, "components": components, "errors": _model_errors}


@app.get("/api/config")
def config():
    return {"engine": _engine_name, "available_engines": list(_engine_catalog), "language": _engine_catalog[_engine_name]["language"], "model": Config.LLM_MODEL_NAME, "posture_scope": ["slouching", "head_position", "shoulder_alignment", "body_orientation"]}


@app.get("/api/tts/engines")
def tts_engines():
    return _tts_state()


@app.post("/api/tts/engine")
def select_tts_engine(selection: TTSEngineSelection):
    try:
        return _activate_tts_engine(selection.engine)
    except Exception as exc:
        _model_errors["tts"] = str(exc)
        metrics.record("settings", "tts engine changed", 0, False, engine=selection.engine, error_type=type(exc).__name__)
        logger.exception("Could not activate TTS engine %s", selection.engine)
        raise HTTPException(503, f"Could not load {_engine_catalog[selection.engine]['name']}: {exc}") from exc


@app.get("/api/monitor/snapshot")
def monitor_snapshot():
    components = {"llm": _llm_model is not None, "stt": _stt_model is not None,
                  "tts": _tts_model is not None, "database": True}
    return metrics.snapshot(components, _model_errors)


@app.post("/api/monitor/reset")
def monitor_reset():
    metrics.reset()
    return {"reset": True}


@app.post("/api/monitor/microphone")
def monitor_microphone(event: MicrophoneMetric):
    data = event.model_dump(exclude_none=True)
    name = data.pop("event")
    duration_ms = data.pop("duration_ms", 0)
    metrics.record("microphone", name, duration_ms, name != "error", **data)
    return {"accepted": True}


@app.get("/api/skills")
def skills(user_id: str = "demo"):
    return training.skills(user_id)


@app.get("/api/users/{user_id}")
def user(user_id: str):
    if user_id != "demo":
        raise HTTPException(404, "User not found")
    dashboard_data = training.dashboard(user_id)
    return dashboard_data["user"]


@app.get("/api/proficiency")
def proficiency(user_id: str = "demo"):
    return training.skills(user_id)


@app.get("/api/recommendations")
def recommendations(user_id: str = "demo"):
    return training.dashboard(user_id)["recommendation"]


@app.get("/api/training-plans")
def training_plans(user_id: str = "demo"):
    return training.dashboard(user_id)["plan"]


@app.get("/api/dashboard")
def dashboard(user_id: str = "demo"):
    return training.dashboard(user_id)


@app.get("/api/sessions")
def history(user_id: str = "demo"):
    return training.history(user_id)


@app.post("/api/sessions")
def create_session(request: SessionCreate):
    try:
        return training.create_session(request.user_id, request.skill_id, request.difficulty)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/scenarios")
def generate_scenario(request: SessionCreate):
    return create_session(request)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return training.session(session_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/sessions/{session_id}/turn")
async def roleplay(session_id: str, request: RoleplayTurn):
    pipeline_started = time.perf_counter()
    try:
        training.add_turn(session_id, "user", request.text, request.duration_seconds)
        stage_started = time.perf_counter()
        sources = training.search(request.text)
        retrieval_ms = (time.perf_counter() - stage_started) * 1000
        ttft_ms = None
        llm_ms = 0.0
        llm_error = None
        if _llm_model:
            prompt = training.prompt(session_id, sources)
            def generate_timed():
                generation_started = time.perf_counter()
                first_token_ms = None
                tokens = []
                for token in _llm_model.generate_contextual_response(prompt):
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - generation_started) * 1000
                    tokens.append(token)
                return "".join(tokens), first_token_ms, (time.perf_counter() - generation_started) * 1000
            try:
                reply, ttft_ms, llm_ms = await asyncio.get_running_loop().run_in_executor(None, generate_timed)
                reply = _public_reply(reply) or training.fallback_reply(session_id)
            except Exception as exc:
                llm_ms = (time.perf_counter() - pipeline_started) * 1000
                llm_error = type(exc).__name__
                logger.warning("LLM turn failed; using local fallback: %s", exc)
                reply = training.fallback_reply(session_id)
        else:
            reply = training.fallback_reply(session_id)
        training.add_turn(session_id, "assistant", reply)
        correlation_id = uuid.uuid4().hex
        audio = None
        tts_ms = 0.0
        if request.synthesize_audio:
            stage_started = time.perf_counter()
            audio = await asyncio.get_running_loop().run_in_executor(None, _synthesize, reply)
            tts_ms = (time.perf_counter() - stage_started) * 1000
        audio_seconds = ((len(base64.b64decode(audio)) - 44) / 2 / _tts_sample_rate) if audio else None
        total_ms = (time.perf_counter() - pipeline_started) * 1000
        metrics.record("roleplay", "conversation turn", total_ms, True, retrieval_ms=round(retrieval_ms, 1),
                       llm_ttft_ms=round(ttft_ms, 1) if ttft_ms is not None else None,
                       llm_ms=round(llm_ms, 1), tts_ms=round(tts_ms, 1), audio_seconds=round(audio_seconds, 2) if audio_seconds else None,
                       tts_realtime_factor=round(tts_ms / (audio_seconds * 1000), 2) if audio_seconds else None,
                       mode="ai" if _llm_model and not llm_error else "fallback", llm_error=llm_error,
                       correlation_id=correlation_id, response_ready_ms=round(total_ms, 1))
        return {"text": reply, "audio_b64": audio, "engine": _engine_name, "correlation_id": correlation_id,
                "sources": [{"name": x["name"]} for x in sources]}
    except ValueError as exc:
        metrics.record("roleplay", "conversation turn", (time.perf_counter() - pipeline_started) * 1000, False, error_type=type(exc).__name__)
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        metrics.record("roleplay", "conversation turn", (time.perf_counter() - pipeline_started) * 1000, False, error_type=type(exc).__name__)
        raise


@app.post("/api/tts/stream")
def stream_tts(request: TTSRequest):
    model, sample_rate, engine = _tts_model, _tts_sample_rate, _engine_name
    if model is None:
        raise HTTPException(503, "The selected TTS engine is unavailable. The text response is still usable.")

    def generate():
        started = time.perf_counter()
        first_audio_ms = None
        samples = 0
        chunks = 0
        try:
            synthesize = getattr(model, "synthesize_streaming", model.synthesize)
            for pcm in synthesize(request.text, speed=1.0):
                if first_audio_ms is None:
                    first_audio_ms = (time.perf_counter() - started) * 1000
                samples += len(pcm) // 4
                chunks += 1
                wav = _pcm_to_wav(pcm, sample_rate)
                yield json.dumps({"type": "audio", "audio_b64": base64.b64encode(wav).decode("ascii"), "index": chunks, "engine": engine}) + "\n"
            total_ms = (time.perf_counter() - started) * 1000
            audio_seconds = samples / sample_rate
            ok = chunks > 0
            metrics.record("tts", "streamed speech", total_ms, ok,
                           correlation_id=request.correlation_id, engine=engine, first_audio_ms=round(first_audio_ms, 1) if first_audio_ms else None,
                           audio_seconds=round(audio_seconds, 2), chunks=chunks,
                           tts_realtime_factor=round(total_ms / (audio_seconds * 1000), 2) if audio_seconds else None)
            if chunks:
                yield json.dumps({"type": "done", "chunks": chunks, "duration_ms": round(total_ms, 1)}) + "\n"
            else:
                yield json.dumps({"type": "error", "message": f"{_engine_catalog[engine]['name']} returned no playable audio."}) + "\n"
        except Exception as exc:
            total_ms = (time.perf_counter() - started) * 1000
            metrics.record("tts", "streamed speech", total_ms, False, correlation_id=request.correlation_id, error_type=type(exc).__name__)
            yield json.dumps({"type": "error", "message": f"{_engine_catalog[engine]['name']} could not generate this response."}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/api/roleplay/{session_id}/turn")
async def roleplay_alias(session_id: str, request: RoleplayTurn):
    return await roleplay(session_id, request)


@app.post("/api/sessions/{session_id}/complete")
def complete_session(session_id: str):
    try:
        return training.assess(session_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/assessments/{session_id}")
def create_assessment(session_id: str):
    return complete_session(session_id)


@app.post("/api/sessions/{session_id}/posture")
def posture(session_id: str, sample: PostureSample):
    try:
        training.session(session_id)
        training.add_posture(session_id, sample.model_dump())
        return {"accepted": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/posture/{session_id}")
def posture_alias(session_id: str, sample: PostureSample):
    return posture(session_id, sample)


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if _stt_model is None:
        raise HTTPException(503, "Speech recognition is unavailable. You can continue by typing.")
    data = await file.read()
    if not data:
        raise HTTPException(422, "Audio file cannot be empty")
    started = time.perf_counter()
    try:
        text = await asyncio.get_running_loop().run_in_executor(None, _stt_model.transcribe, data)
        duration_ms = (time.perf_counter() - started) * 1000
        metrics.record("transcription", "speech to text", duration_ms, True, upload_kb=round(len(data) / 1024, 1))
        return {"text": text.strip(), "latency_ms": round(duration_ms, 1)}
    except Exception as exc:
        metrics.record("transcription", "speech to text", (time.perf_counter() - started) * 1000, False, error_type=type(exc).__name__)
        raise


@app.get("/api/documents")
def documents(user_id: str = "demo"):
    return training.documents(user_id)


def _extract_document(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if suffix == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    raise ValueError("Use a PDF, DOCX, TXT or MD file")


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), user_id: str = Form("demo")):
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Document must be smaller than 10 MB")
    try:
        return training.add_document(user_id, file.filename or "document", _extract_document(file.filename or "", data))
    except (ValueError, ImportError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str, user_id: str = "demo"):
    if not training.delete_document(document_id, user_id):
        raise HTTPException(404, "Document not found")
    return {"deleted": True}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Compatibility endpoint retained for the earlier generic voice client."""
    if _llm_model:
        text = await asyncio.get_running_loop().run_in_executor(None, lambda: "".join(_llm_model.generate_response(request.text)))
    else:
        text = "Start a training scenario from the Hikari dashboard so I can coach you in context."
    audio = await asyncio.get_running_loop().run_in_executor(None, _synthesize, text)
    return {"text": text, "audio_b64": audio, "engine": "chattts"}


# Production-style local mode: the same process serves the compiled React app.
# Keep this mount last so every /api route remains authoritative.
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
