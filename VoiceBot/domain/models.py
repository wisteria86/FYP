"""Typed domain contracts used by the scenario and assessment migrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ADAPTIVE = "adaptive"


class ParticipantType(StrEnum):
    LEARNER = "learner"
    AI = "ai"


@dataclass(frozen=True)
class ParticipantDefinition:
    participant_type: ParticipantType
    display_name: str
    scenario_role: str
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioDefinition:
    id: str
    activity_id: str
    learner_role: str
    context: str
    objectives: tuple[str, ...]
    success_criteria: tuple[str, ...]
    opening_situation: str
    participants: tuple[ParticipantDefinition, ...]
    rubric: dict[str, Any]


@dataclass(frozen=True)
class AssessmentDraft:
    overall_score: float
    skill_scores: dict[str, float]
    subskill_scores: dict[str, float]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    mistakes: tuple[dict[str, str], ...]
    improvement_suggestions: tuple[str, ...]
    recommended_exercise_id: str | None = None
