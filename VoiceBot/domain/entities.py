"""Domain entities from Figure 5.2; independent of HTTP, SQL, and AI vendors."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import math


def now():
    return datetime.now(timezone.utc).isoformat()


class SessionStatus(StrEnum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    CANCELED = 'canceled'
    FAILED = 'failed'
    INCOMPLETE = 'incomplete'


class ProcessingStatus(StrEnum):
    PROCESSING = 'processing'
    READY = 'ready'
    FAILED = 'failed'


def score(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('A proficiency or assessment score must be between 0 and 100')
    return value


@dataclass
class Organization:
    id: str
    name: str
    configuration: dict = field(default_factory=dict)

    def update_configuration(self, data):
        self.configuration.update(data)


@dataclass
class User:
    id: str
    name: str
    email: str
    organization_id: str | None = None
    account_type: str = 'learner'
    training_preferences: dict = field(default_factory=dict)

    def update_profile(self, name):
        if not name.strip():
            raise ValueError('Name cannot be empty')
        self.name = name.strip()

    def update_preferences(self, data):
        self.training_preferences.update(data)


@dataclass(frozen=True)
class Subskill:
    id: str
    skill_id: str
    name: str
    description: str = ''


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    category: str = 'workplace'
    subskills: tuple[Subskill, ...] = ()


@dataclass
class Scenario:
    id: str
    skill_id: str
    title: str
    difficulty: str
    role_type: str
    objectives: tuple[str, ...]
    criteria: tuple[str, ...]
    source_type: str = 'template'

    def update_criteria(self, criteria):
        if not criteria:
            raise ValueError('A scenario needs success criteria')
        self.criteria = tuple(criteria)


@dataclass
class TrainingSession:
    id: str
    user_id: str
    scenario_id: str
    status: SessionStatus = SessionStatus.INCOMPLETE
    start_time: str | None = None
    completion_time: str | None = None

    def start(self):
        if self.status != SessionStatus.INCOMPLETE:
            raise ValueError('Only an unfinished session can start')
        self.status = SessionStatus.ACTIVE
        self.start_time = now()

    def _finish(self, status):
        if self.status != SessionStatus.ACTIVE:
            raise ValueError('Only an active session can change outcome')
        self.status = status
        self.completion_time = now()

    def complete(self): self._finish(SessionStatus.COMPLETED)
    def cancel(self): self._finish(SessionStatus.CANCELED)
    def mark_failed(self): self._finish(SessionStatus.FAILED)


@dataclass
class AssessmentMetric:
    id: str
    assessment_id: str
    name: str
    modality: str
    score: float | None
    details: str = ''
    availability_status: str = 'available'

    def __post_init__(self):
        if self.score is not None:
            self.score = score(self.score)
        if self.availability_status != 'available' and self.score is not None:
            raise ValueError('Unavailable modalities must not receive fabricated scores')


@dataclass
class Assessment:
    id: str
    session_id: str
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    mistakes: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    metrics: list[AssessmentMetric] = field(default_factory=list)
    created_at: str = field(default_factory=now)

    def add_metric(self, metric):
        if metric.assessment_id != self.id:
            raise ValueError('Metric belongs to another assessment')
        self.metrics.append(metric)

    def calculate_overall_score(self):
        values = [m.score for m in self.metrics if m.score is not None and m.availability_status == 'available']
        return round(sum(values) / len(values), 1) if values else None


@dataclass
class Proficiency:
    id: str
    user_id: str
    skill_id: str
    score: float
    subskill_id: str | None = None
    updated_at: str = field(default_factory=now)

    def update_score(self, value):
        self.score = score(value)
        self.updated_at = now()


@dataclass(frozen=True)
class ProficiencyUpdate:
    id: str
    proficiency_id: str
    assessment_id: str
    previous_score: float
    new_score: float
    updated_at: str = field(default_factory=now)


@dataclass
class Recommendation:
    id: str
    plan_id: str
    skill_id: str
    scenario_id: str
    source_assessment_id: str | None
    priority: int
    reason: str
    status: str = 'pending'

    def mark_accepted(self): self.status = 'accepted'
    def mark_completed(self): self.status = 'completed'
    def dismiss(self): self.status = 'dismissed'


@dataclass
class TrainingPlan:
    id: str
    user_id: str
    status: str = 'active'
    recommendations: list[Recommendation] = field(default_factory=list)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def activate(self): self.status = 'active'; self.updated_at = now()
    def complete(self): self.status = 'completed'; self.updated_at = now()


@dataclass
class Document:
    id: str
    organization_id: str
    file_name: str
    document_type: str
    processing_status: ProcessingStatus = ProcessingStatus.PROCESSING
    uploaded_at: str = field(default_factory=now)

    def mark_processing(self): self.processing_status = ProcessingStatus.PROCESSING
    def mark_ready(self): self.processing_status = ProcessingStatus.READY
    def mark_failed(self): self.processing_status = ProcessingStatus.FAILED


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    document_id: str
    index: int
    content_reference: str
    vector_reference: str | None = None
