"""Provider-independent intelligence interfaces from Figure 5.2."""
from typing import Protocol, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class AIResponse:
    text: str
    speaker: str


@dataclass(frozen=True)
class VoiceMetrics:
    words_per_minute: float | None
    filler_count: int
    spoken_seconds: float


@dataclass(frozen=True)
class VisualMetrics:
    scores: dict[str, float]
    available: bool
    reason: str | None = None


class SpeechService(Protocol):
    def transcribe(self, audio: bytes, language: str | None = None) -> dict: ...
    def synthesize(self, text: str) -> Iterable[bytes]: ...


class SpeechAnalysisService(Protocol):
    def analyze_audio(self, transcript: str, spoken_seconds: float) -> VoiceMetrics: ...


class ConversationalAIService(Protocol):
    def generate_response(self, context: str) -> Iterable[str]: ...
    def generate_scenario(self, context: str) -> dict: ...
    def evaluate_conversation(self, context: str) -> dict: ...


class VisionService(Protocol):
    def analyze_posture(self, landmarks: list[dict]) -> VisualMetrics: ...


class EmbeddingService(Protocol):
    def generate_embedding(self, texts: list[str]) -> list[list[float]]: ...


class RetrievalService(Protocol):
    def store(self, document_id: str, organization_id: str, chunks: list[str], embeddings: list[list[float]]) -> None: ...
    def search(self, query_embedding: list[float], organization_id: str, limit: int = 3) -> list[dict]: ...
