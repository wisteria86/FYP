"""Transport schemas for the compatibility API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=200)
    organization_name: Optional[str] = Field(default=None, min_length=2, max_length=120)


class PoseLandmark(BaseModel):
    x: float = Field(ge=-2, le=2)
    y: float = Field(ge=-2, le=2)
    z: float = Field(default=0, ge=-10, le=10)
    visibility: float = Field(ge=0, le=1)


class PoseLandmarksRequest(BaseModel):
    landmarks: list[PoseLandmark] = Field(min_length=33, max_length=33)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class UserSettingsUpdate(BaseModel):
    preferred_language: str = Field(pattern="^(English|Japanese|Arabic|Chinese|Korean)$")
    native_language: str = Field(pattern="^(English|Urdu|Japanese|Arabic|Chinese|Korean)$")
    proficiency_level: str = Field(pattern="^(beginner|intermediate|advanced)$")
    captions_enabled: bool


class SessionCreate(BaseModel):
    user_id: Optional[str] = None
    skill_id: str
    activity_id: Optional[str] = None
    difficulty: str = Field(default="intermediate", pattern="^(beginner|intermediate|advanced)$")
    preview_id: Optional[str] = Field(default=None,max_length=80)
    document_ids: list[str] = Field(default_factory=list,max_length=20)
    posture_enabled: bool = False


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
    engine: str = Field(pattern="^(chattts|kokoro|piper|kitten|vits_ja|vits_ar)$")
    voice: Optional[str] = Field(default=None, max_length=50)


class PostureSample(BaseModel):
    slouching: float = Field(ge=0, le=100)
    head_position: float = Field(ge=0, le=100)
    shoulder_alignment: float = Field(ge=0, le=100)
    body_orientation: float = Field(ge=0, le=100)


class STTEngineSelection(BaseModel):
    engine: str = Field(pattern='^(whisper_small_onnx|whisper_medium_onnx|nemotron)$')
    device: str = Field(default='auto',pattern='^(auto|cpu)$')


class MicrophoneMetric(BaseModel):
    event: str = Field(pattern="^(connected|listening|level|speech_detected|stopped|transcribed|playback_started|error)$")
    engine: Optional[str] = Field(default=None, max_length=40)
    endpointing_ms: Optional[float] = Field(default=None, ge=0, le=120000)
    transcription_wall_ms: Optional[float] = Field(default=None, ge=0, le=120000)
    response_to_playback_ms: Optional[float] = Field(default=None, ge=0, le=120000)
    audio_output_latency_ms: Optional[float] = Field(default=None, ge=0, le=10000)
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
