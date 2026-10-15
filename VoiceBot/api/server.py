"""FastAPI application for the Hikari employee-training platform."""
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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from api.application import create_application  # noqa: E402
from api.routers.auth import build_auth_router  # noqa: E402
from api.schemas import (  # noqa: E402
    ChatRequest,
    MicrophoneMetric,
    PostureSample,
    PoseLandmarksRequest,
    RoleplayTurn,
    SessionCreate,
    TTSEngineSelection,
    STTEngineSelection,
    TTSRequest,
)
from core.training_service import TrainingService  # noqa: E402
from core.monitoring import MetricsCollector  # noqa: E402
from database.migration_runner import current_version  # noqa: E402
from services.auth_service import AuthService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("hikari.api")
training = TrainingService(Config.DATABASE_PATH)
auth_service = AuthService(Config.DATABASE_PATH, Config.AUTH_SESSION_HOURS)
metrics = MetricsCollector()
_tts_model = _llm_model = _stt_model = None
_tts_sample_rate = 24000
_settings_path = ROOT / "data" / "runtime_settings.json"
_tts_switch_lock = threading.Lock()
from services.speech_activity import SpeechActivity
_stt_activity=SpeechActivity()
_settings_write_lock=threading.Lock()


def _persist_runtime_settings(updates):
    with _settings_write_lock:
        data=_saved_settings();data.update(updates)
        _settings_path.parent.mkdir(parents=True,exist_ok=True)
        temporary=_settings_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
        temporary.replace(_settings_path)
_engine_catalog = {
    "kokoro": {
        "name": "Kokoro",
        "language": "English (Multi-voice)",
        "description": "Clear local ONNX voice with bounded CPU inference.",
        "default": True,
        "latency_label": "Device-dependent",
        "features": ["Ultra-low latency", "Lightweight CPU inference", "Multiple voice personas", "Recommended default"]
    },
    "chattts": {
        "name": "ChatTTS",
        "language": "Multilingual",
        "description": "Expressive conversational local voice; higher resource use.",
        "default": False,
        "latency_label": "~2.5 s",
        "features": ["Conversational inflections", "High expressiveness", "Higher RAM/GPU use"]
    },
    "vits_ja": {
        "name": "VITS Japanese",
        "language": "Japanese",
        "description": "Dedicated Japanese Piper-style voice (Tsukuyomi-chan).",
        "default": False,
        "latency_label": "< 300 ms",
        "features": ["Native Japanese phonemes", "Clear articulation", "Lightweight ONNX"]
    },
    "vits_ar": {
        "name": "VITS Arabic",
        "language": "Arabic",
        "description": "Dedicated Arabic Piper-style voice (Kareem); requires eSpeak NG.",
        "default": False,
        "latency_label": "< 350 ms",
        "features": ["Modern Standard Arabic", "Piper engine", "Requires eSpeak NG"]
    },
}

_kokoro_voices = [
    {"id": "af_heart", "name": "Heart (US Female - Default)", "gender": "Female", "accent": "American"},
    {"id": "af_bella", "name": "Bella (US Female - Warm)", "gender": "Female", "accent": "American"},
    {"id": "af_nicole", "name": "Nicole (US Female - Clear)", "gender": "Female", "accent": "American"},
    {"id": "af_sarah", "name": "Sarah (US Female - Crisp)", "gender": "Female", "accent": "American"},
    {"id": "af_sky", "name": "Sky (US Female - Soft)", "gender": "Female", "accent": "American"},
    {"id": "am_adam", "name": "Adam (US Male - Deep)", "gender": "Male", "accent": "American"},
    {"id": "am_michael", "name": "Michael (US Male - Professional)", "gender": "Male", "accent": "American"},
    {"id": "bf_emma", "name": "Emma (British Female)", "gender": "Female", "accent": "British"},
    {"id": "bf_isabella", "name": "Isabella (British Female)", "gender": "Female", "accent": "British"},
    {"id": "bm_george", "name": "George (British Male)", "gender": "Male", "accent": "British"},
    {"id": "bm_lewis", "name": "Lewis (British Male)", "gender": "Male", "accent": "British"},
    {"id": "jf_alpha", "name": "Alpha (Japanese Female)", "gender": "Female", "accent": "Japanese"},
]


def _saved_settings() -> dict:
    try:
        return json.loads(_settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _saved_engine() -> str:
    value = _saved_settings().get("tts_engine", Config.TTS_ENGINE)
    return value if value in _engine_catalog else "kokoro"


def _saved_kokoro_voice() -> str:
    return _saved_settings().get("kokoro_voice", Config.KOKORO_VOICE)


_engine_name = _saved_engine()
_current_kokoro_voice = _saved_kokoro_voice()
_model_errors: dict[str, str] = {}


def _authorized_user_id(request: Request, requested_user_id: str | None = None) -> str:
    """Resolve the authenticated owner; demo access is development-only."""

    token = request.cookies.get(Config.AUTH_COOKIE_NAME)
    current_user = auth_service.user_for_token(token)
    if current_user:
        if requested_user_id and requested_user_id != current_user["id"]:
            raise HTTPException(403, "You cannot access another learner's data")
        return current_user["id"]
    if Config.ALLOW_DEMO_ACCESS and requested_user_id in {None, "demo"}:
        return "demo"
    raise HTTPException(401, "Authentication required")


def _authorized_session(request: Request, session_id: str) -> dict:
    session = training.session(session_id)
    _authorized_user_id(request, session["user_id"])
    return session


def _engine_installed(engine: str) -> bool:
    if engine == "chattts":
        return (ROOT / "asset" / "gpt" / "model.safetensors").exists() or (ROOT / Config.CHAT_TTS_CACHE_DIR).exists()
    if engine == "kokoro":
        return (ROOT / "models" / "kokoro-v1.0.onnx").exists() and (ROOT / "models" / "voices-v1.0.bin").exists()
    cache = ROOT / (Config.VITS_JA_CACHE_DIR if engine == "vits_ja" else Config.VITS_AR_CACHE_DIR)
    return cache.exists() and any(cache.rglob("*.onnx")) and any(cache.rglob("*.json"))


def _build_tts_engine(engine: str, voice: Optional[str] = None):
    global _current_kokoro_voice
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
        chosen_voice = voice or _current_kokoro_voice or Config.KOKORO_VOICE
        _current_kokoro_voice = chosen_voice
        return KokoroTTS(lang=Config.KOKORO_LANG, voice=chosen_voice)
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


def _activate_tts_engine(engine: str, voice: Optional[str] = None, persist: bool = True) -> dict:
    global _tts_model, _tts_sample_rate, _engine_name, _current_kokoro_voice
    if engine not in _engine_catalog:
        raise ValueError("Unknown TTS engine")
    with _tts_switch_lock:
        # If Kokoro is already active and only the voice is updated
        if engine == "kokoro" and _engine_name == "kokoro" and _tts_model is not None:
            if voice and voice != _current_kokoro_voice:
                _current_kokoro_voice = voice
                _tts_model.voice = voice
                if persist:
                    _persist_runtime_settings({'tts_engine':'kokoro','kokoro_voice':_current_kokoro_voice})
            return _tts_state()

        if engine == _engine_name and _tts_model is not None:
            return _tts_state()

        started = time.perf_counter()
        new_model = _build_tts_engine(engine, voice)
        # Warm ChatTTS before exposing it so the first conversation does not stall.
        if engine == "chattts":
            for _ in new_model.synthesize_streaming("Ready.", speed=1.0):
                pass
        old_model = _tts_model
        _tts_model = new_model
        _tts_sample_rate = int(new_model.output_sample_rate)
        _engine_name = engine
        if engine == "kokoro" and voice:
            _current_kokoro_voice = voice
        _model_errors.pop("tts", None)
        metrics.set_model_load("tts", (time.perf_counter() - started) * 1000, True)
        metrics.record("settings", "tts engine changed", (time.perf_counter() - started) * 1000, True, engine=engine)
        if persist:
            data = {"tts_engine": engine}
            if _engine_name == "kokoro":
                data["kokoro_voice"] = _current_kokoro_voice
            _persist_runtime_settings(data)
        if old_model is not None and hasattr(old_model, "close"):
            try:
                old_model.close()
            except Exception:
                logger.warning("Previous TTS engine did not release cleanly", exc_info=True)
        del old_model
        gc.collect()
        return _tts_state()


def _tts_state() -> dict:
    runtime = _tts_model.runtime_info() if _tts_model is not None and hasattr(_tts_model, "runtime_info") else None
    return {
        "active": _engine_name,
        "default": "kokoro",
        "sample_rate": _tts_sample_rate,
        "current_voice": _current_kokoro_voice if _engine_name == "kokoro" else None,
        "voices": _kokoro_voices,
        "runtime": runtime,
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
                logger.warning("TTS engine skipped a sentence: %s", exc)
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
        from modules.stt_router import create_stt
        preferences=_saved_settings()
        try:
            _stt_model = create_stt(engine=preferences.get('stt_engine'),device=preferences.get('stt_device'))
        except Exception:
            logger.exception('Saved recognizer unavailable; using automatic fallback')
            _stt_model=create_stt(engine='auto',device='auto')
        metrics.set_model_load("stt", (time.perf_counter() - started) * 1000, True)
    except Exception as exc:
        metrics.set_model_load("stt", (time.perf_counter() - started) * 1000, False)
        _model_errors["stt"] = str(exc)
        logger.exception("Whisper unavailable; typed roleplay remains enabled")
    started = time.perf_counter()
    try:
        _activate_tts_engine(_engine_name, persist=False)
        if os.getenv('TTS_WARMUP','true').lower()=='true':
            warm_started=time.perf_counter()
            warmed=bool(_synthesize('Hello.'))
            metrics.record('tts','startup warmup',(time.perf_counter()-warm_started)*1000,warmed,engine=_engine_name)
    except Exception as exc:
        metrics.set_model_load("tts", (time.perf_counter() - started) * 1000, False)
        _model_errors["tts"] = str(exc)
        logger.exception("Selected TTS engine unavailable; text roleplay remains enabled")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("HIKARI_SKIP_MODELS", "false").lower() != "true":
        await asyncio.get_running_loop().run_in_executor(None, _load_models)
    yield


app = create_application(lifespan=lifespan)
app.include_router(build_auth_router(auth_service))
from api.routers.administration import build_administration_router
app.include_router(build_administration_router(training.context.administration, auth_service))


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


@app.get("/api/health")
def health():
    components = {"llm": _llm_model is not None, "stt": _stt_model is not None, "tts": _tts_model is not None, "database": True}
    runtime = _tts_model.runtime_info() if _tts_model is not None and hasattr(_tts_model, "runtime_info") else None
    stt_runtime = _stt_model.runtime_info() if _stt_model is not None and hasattr(_stt_model, "runtime_info") else None
    return {"status": "ready" if all(components.values()) else "degraded", "engine": _engine_name, "sample_rate": _tts_sample_rate, "tts_runtime": runtime, "stt_runtime": stt_runtime, "database_schema": current_version(Config.DATABASE_PATH), "components": components, "errors": _model_errors}


@app.get("/api/config")
def config():
    return {"engine": _engine_name, "available_engines": list(_engine_catalog), "language": _engine_catalog[_engine_name]["language"], "model": Config.LLM_MODEL_NAME, "posture_scope": ["slouching", "head_position", "shoulder_alignment", "body_orientation"]}


def _stt_state():
    saved=_saved_settings()
    runtime=_stt_model.runtime_info() if _stt_model and hasattr(_stt_model,'runtime_info') else None
    cache=Config.BASE_DIR/Config.WHISPER_ONNX_CACHE_DIR
    installed=lambda size:all((cache/size/f'{size}-{suffix}').is_file() for suffix in ('encoder.int8.onnx','decoder.int8.onnx','tokens.txt'))
    return {'selected':saved.get('stt_engine','nemotron'),'device':saved.get('stt_device','auto'),
            'runtime':runtime,'busy':_stt_activity.users>0 or _stt_activity.switching,
            'engines':[
                {'id':'whisper_small_onnx','name':'Whisper Small ONNX','installed':installed('small'),'description':'Multilingual INT8. Lower CPU cost; may be less accurate than medium.'},
                {'id':'whisper_medium_onnx','name':'Whisper Medium ONNX','installed':installed('medium'),'description':'Multilingual INT8. Higher CPU and memory cost.'},
                {'id':'nemotron','name':'NVIDIA Nemotron Streaming ASR','installed':all((Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR/name).is_file() for name in ('tokens.txt','encoder.int8.onnx','decoder.int8.onnx','joiner.int8.onnx')),'description':'English live recognition. Auto uses CUDA with Whisper fallback; CPU mode runs the same INT8 model locally.'},
            ]}


@app.get('/api/stt/engines')
def stt_engines(request:Request):
    _authorized_user_id(request)
    return _stt_state()


@app.post('/api/stt/engine')
def select_stt_engine(payload:STTEngineSelection,request:Request):
    global _stt_model
    _authorized_user_id(request)
    from modules.stt_router import create_stt
    try:
        with _stt_activity.switch():
            candidate=create_stt(engine=payload.engine,device=payload.device,strict=True)
            try:_persist_runtime_settings({'stt_engine':payload.engine,'stt_device':payload.device})
            except Exception:
                if hasattr(candidate,'close'):candidate.close()
                raise
            old=_stt_model;_stt_model=candidate
            _model_errors.pop('stt',None)
            if old and hasattr(old,'close'):
                try:old.close()
                except Exception:logger.warning('Previous recognition engine did not release cleanly',exc_info=True)
            del old;gc.collect()
        return _stt_state()
    except RuntimeError as exc:
        raise HTTPException(409,str(exc)) from exc
    except Exception as exc:
        logger.exception('Recognition engine switch failed')
        raise HTTPException(503,'Recognition engine could not load. The previous engine is retained; check model installation and diagnostics.') from exc


@app.get("/api/tts/engines")
def tts_engines():
    return _tts_state()


@app.post("/api/tts/engine")
def select_tts_engine(selection: TTSEngineSelection):
    try:
        return _activate_tts_engine(selection.engine, voice=selection.voice)
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
def skills(request: Request, user_id: str | None = None):
    return training.skills(_authorized_user_id(request, user_id))


@app.get("/api/training/activities")
def training_activities():
    return training.activities()


@app.get("/api/resources")
def learning_resources():
    return training.resources()


@app.get("/api/users/{user_id}")
def user(user_id: str, request: Request):
    user_id = _authorized_user_id(request, user_id)
    dashboard_data = training.dashboard(user_id)
    return dashboard_data["user"]


@app.get("/api/proficiency")
def proficiency(request: Request, user_id: str | None = None):
    return training.skills(_authorized_user_id(request, user_id))


@app.get("/api/recommendations")
def recommendations(request: Request, user_id: str | None = None):
    return training.dashboard(_authorized_user_id(request, user_id))["recommendation"]


@app.get("/api/training-plans")
def training_plans(request: Request, user_id: str | None = None):
    return training.dashboard(_authorized_user_id(request, user_id))["plan"]


@app.get("/api/dashboard")
def dashboard(request: Request, user_id: str | None = None):
    return training.dashboard(_authorized_user_id(request, user_id))


@app.get("/api/sessions")
def history(request: Request, user_id: str | None = None):
    return training.history(_authorized_user_id(request, user_id))


@app.post("/api/sessions")
def create_session(payload: SessionCreate, request: Request):
    try:
        user_id = _authorized_user_id(request, payload.user_id)
        session = training.create_session(user_id, payload.skill_id, payload.difficulty, payload.activity_id,payload.preview_id,payload.document_ids,payload.posture_enabled)
        caption_preferences = training.caption_preferences(session["id"])
        if caption_preferences["translate"] and _llm_model and session["turns"]:
            try:
                caption = _public_reply(
                    _llm_model.translate_caption(session["turns"][0]["text"], caption_preferences["language"])
                )
                if caption:
                    training.set_opening_caption(session["id"], caption)
                    session = training.session(session["id"])
            except Exception as exc:
                logger.warning("Opening caption translation failed: %s", exc)
        return session
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/scenarios")
def generate_scenario(payload: SessionCreate, request: Request):
    return create_session(payload, request)


@app.post("/api/scenarios/preview")
def preview_scenario(payload: SessionCreate, request: Request):
    try:
        user_id = _authorized_user_id(request, payload.user_id)
        return training.scenario_preview(user_id, payload.skill_id, payload.difficulty, payload.activity_id,payload.document_ids,payload.posture_enabled,payload.preview_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, request: Request):
    try:
        return _authorized_session(request, session_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/sessions/{session_id}/turn")
async def roleplay(session_id: str, payload: RoleplayTurn, request: Request, sentence_callback=None, response_callback=None):
    _authorized_session(request, session_id)
    from services.training_orchestrator import TrainingOrchestrator
    from integrations.conversation import ConversationAdapter
    orchestrator = TrainingOrchestrator(training, ConversationAdapter(_llm_model) if _llm_model else None,
                                        _synthesize, metrics, _tts_sample_rate, _engine_name)
    return await orchestrator.run_turn(session_id, payload, sentence_callback, response_callback)


@app.post("/api/sessions/{session_id}/voice-stream")
async def voice_turn_stream(session_id: str, payload: RoleplayTurn, request: Request):
    from services.audio_stream import audio_chunks
    session = _authorized_session(request, session_id)
    model, sample_rate = _tts_model, _tts_sample_rate
    synthesize = getattr(model, 'synthesize_streaming', None) or getattr(model, 'synthesize', None)
    if model is None:
        async def text_only():
            result=await roleplay(session_id,payload.model_copy(update={'synthesize_audio':False}),request)
            yield json.dumps({'type':'speech_error','message':'Voice engine unavailable. Your response is shown as text.'})+'\n'
            yield json.dumps({'type':'result','result':result})+'\n'
        return StreamingResponse(text_only(),media_type='application/x-ndjson')
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    def sentence_ready(text, speaker):
        # Do not speak persona leakage before the turn's validation runs.
        if session.get("training_language") == "English" and any(phrase in text.lower() for phrase in (
            "what specific action", "propose we take next", "focus on the solution",
            "stakeholder impact", "action plan"
        )):
            return
        loop.call_soon_threadsafe(queue.put_nowait, (text, speaker))
    async def generate():
        started = time.perf_counter()
        first_audio_ms = None
        samples = 0
        # Each complete sentence is a synthesis unit; do not await the full reply.
        task = asyncio.create_task(roleplay(
            session_id, payload.model_copy(update={"synthesize_audio": False}), request,
            sentence_ready,
            None,
        ))
        audio_count = 0
        try:
            while not task.done() or not queue.empty():
                try:
                    sentence, speaker = await asyncio.wait_for(queue.get(), timeout=.1)
                except asyncio.TimeoutError:
                    continue
                yield json.dumps({'type':'speech_text','speaker':speaker,'text':sentence})+'\n'
                async for pcm in audio_chunks(synthesize, sentence):
                    audio_count += 1
                    samples += len(pcm) // 4
                    if first_audio_ms is None:
                        first_audio_ms = (time.perf_counter() - started) * 1000
                    yield json.dumps({"type": "audio", "speaker": speaker, "audio_b64": base64.b64encode(_pcm_to_wav(pcm, sample_rate)).decode("ascii")}) + "\n"
            result = await task
            if not audio_count:
                for response in result["responses"]:
                    yield json.dumps({'type':'speech_text','speaker':response['speaker'],'text':response['text']})+'\n'
                    async for pcm in audio_chunks(synthesize, response["text"]):
                        audio_count += 1
                        samples += len(pcm) // 4
                        if first_audio_ms is None:
                            first_audio_ms = (time.perf_counter() - started) * 1000
                        yield json.dumps({"type": "audio", "speaker": response["speaker"], "audio_b64": base64.b64encode(_pcm_to_wav(pcm, sample_rate)).decode("ascii")}) + "\n"
            metrics.record("tts", "streamed speech", (time.perf_counter() - started) * 1000,
                           audio_count > 0, correlation_id=result.get("correlation_id"),
                           engine=_engine_name, first_audio_ms=first_audio_ms,
                           audio_seconds=samples / sample_rate, chunks=audio_count,
                           overlaps_response=True)
            if not audio_count:
                raise RuntimeError("Voice engine returned no playable audio")
            yield json.dumps({"type": "result", "result": result}) + "\n"
        except Exception as exc:
            logger.exception('Voice turn speech synthesis failed')
            try:
                result=await asyncio.wait_for(asyncio.shield(task),timeout=25)
            except Exception:
                yield json.dumps({'type':'error','message':'The response could not finish. Please retry or switch to chat.'})+'\n'
            else:
                yield json.dumps({'type':'speech_error','message':'Speech playback failed. Your response is shown as text.'})+'\n'
                yield json.dumps({'type':'result','result':result})+'\n'
        finally:
            if not task.done():
                task.cancel()
    return StreamingResponse(generate(), media_type="application/x-ndjson")


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
            synthesize = getattr(model, "synthesize_streaming", getattr(model, "synthesize", None))
            if synthesize is None:
                raise RuntimeError(f"{_engine_catalog[engine]['name']} does not implement synthesis")
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
async def roleplay_alias(session_id: str, payload: RoleplayTurn, request: Request):
    return await roleplay(session_id, payload, request)


@app.post("/api/sessions/{session_id}/complete")
async def complete_session(session_id: str, request: Request):
    try:
        session = _authorized_session(request, session_id)
        language_evaluation = None
        if session.get("assessment"):
            return session["assessment"]
        progress=training.evaluate_progress(session_id)
        if progress['outcome']!='success':
            raise HTTPException(409, 'Keep practising: '+ '; '.join(progress['missing'][:3]) + '. You may leave without awarding mastery.')
        if session.get("training_language") == "English" and _llm_model and hasattr(_llm_model, "evaluate_english"):
            try:
                language_evaluation = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(
                    None, _llm_model.evaluate_english, training.assessment_prompt(session_id)
                ),timeout=15)
            except Exception as exc:
                logger.warning("Language assessment failed; using deterministic assessment: %s", exc)
        return training.assess(session_id, language_evaluation)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/assessments/{session_id}")
async def create_assessment(session_id: str, request: Request):
    return await complete_session(session_id, request)


@app.post("/api/sessions/{session_id}/posture")
def posture(session_id: str, sample: PostureSample, request: Request):
    try:
        _authorized_session(request, session_id)
        training.add_posture(session_id, sample.model_dump())
        return {"accepted": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/posture/{session_id}")
def posture_alias(session_id: str, sample: PostureSample, request: Request):
    return posture(session_id, sample, request)


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), language: str | None = Form(None),
                     context: str | None = Form(None), duration_ms: float = Form(0), partial: bool = Form(False)):
    if _stt_model is None:
        raise HTTPException(503, "Speech recognition is unavailable. You can continue by typing.")
    data = await file.read()
    if not data:
        raise HTTPException(422, "Audio file cannot be empty")
    if len(data)>10*1024*1024:
        raise HTTPException(413, 'Audio capture must be smaller than 10 MB')
    started = time.perf_counter()
    try:
        language_code = {"English": "en", "Japanese": "ja", "Arabic": "ar", "Chinese": "zh", "Korean": "ko"}.get(language or "", language)
        if hasattr(_stt_model, "transcribe_detailed"):
            def recognize():
                with _stt_activity.use():
                    return _stt_model.transcribe_detailed(data,language_code,context)
            result = await asyncio.get_running_loop().run_in_executor(None,recognize)
        else:
            text = await asyncio.get_running_loop().run_in_executor(None, _stt_model.transcribe, data)
            result = {"text": text, "confidence": None, "detected_language": language_code, "language_probability": None}
        processing_ms = (time.perf_counter() - started) * 1000
        metrics.record("transcription", "partial speech" if partial else "speech to text", processing_ms, True, upload_kb=round(len(data) / 1024, 1),partial=partial)
        text = result["text"].strip()
        capture_duration_ms = max(0, float(duration_ms or 0))
        suspicious_short = capture_duration_ms >= 1600 and len(re.findall(r"[\w'-]+", text, re.UNICODE)) <= 1
        low_confidence = result.get("confidence") is not None and result["confidence"] < .18
        return {
            **result, "text": text, "latency_ms": round(processing_ms, 1), "partial":partial,
            "needs_retry": bool(text and (suspicious_short or low_confidence)),
            "retry_reason": "I only caught a very short or uncertain fragment." if text and (suspicious_short or low_confidence) else None,
        }
    except Exception as exc:
        metrics.record("transcription", "speech to text", (time.perf_counter() - started) * 1000, False, error_type=type(exc).__name__)
        if isinstance(exc, RuntimeError):
            raise HTTPException(503, str(exc)) from exc
        raise


@app.get("/api/documents")
def documents(request: Request, user_id: str | None = None):
    return training.documents(_authorized_user_id(request, user_id))


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
async def upload_document(request: Request, file: UploadFile = File(...), user_id: str | None = Form(None)):
    user_id = _authorized_user_id(request, user_id)
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Document must be smaller than 10 MB")
    try:
        content = await asyncio.get_running_loop().run_in_executor(None, _extract_document, file.filename or '', data)
        return await asyncio.get_running_loop().run_in_executor(None, training.add_document, user_id, file.filename or 'document', content)
    except (ValueError, ImportError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str, request: Request, user_id: str | None = None):
    user_id = _authorized_user_id(request, user_id)
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
@app.post('/api/sessions/{session_id}/posture-landmarks')
def posture_landmarks(session_id: str, request: Request, payload: PoseLandmarksRequest):
    _authorized_session(request, session_id)
    from integrations.vision import LandmarkVisionAdapter
    result = LandmarkVisionAdapter().analyze_posture([p.model_dump() for p in payload.landmarks])
    if result.available:
        try:
            training.add_posture(session_id, result.scores)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    return {'available': result.available, 'scores': result.scores, 'reason': result.reason}


@app.post('/api/sessions/{session_id}/cancel')
def cancel_session(session_id: str, request: Request):
    _authorized_session(request, session_id)
    try:
        return training.cancel_session(session_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# Production-style local mode: the same process serves the compiled React app.
# Keep this mount last so every /api route remains authoritative.
from api.routers.speech_stream import install_speech_stream
install_speech_stream(app,lambda:_stt_model,_authorized_session,metrics,activity=_stt_activity)

FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def index_route():
        return FileResponse(
            FRONTEND_DIST / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )

    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
