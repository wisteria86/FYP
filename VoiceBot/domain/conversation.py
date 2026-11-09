"""Versioned runtime contracts. Private scenario records never cross learner APIs."""
from typing import Literal
import math
from pydantic import BaseModel, Field, model_validator


class ParticipantKnowledge(BaseModel):
    public_knowledge: list[str] = Field(default_factory=list)
    private_knowledge: dict = Field(default_factory=dict)


class Participant(ParticipantKnowledge):
    id: str = Field(min_length=1,max_length=100)
    name: str
    role: str
    kind: Literal['learner', 'ai']
    team: str = 'participant'
    relationship: str = 'Meeting for this scenario'
    goals: list[str] = Field(default_factory=list)
    style: str = 'Respectful, concise, responsive'
    authority: str = 'Speak only for yourself'
    can_finalize: bool = False
    party: Literal['buyer','seller'] | None = None
    topics: list[str] = Field(default_factory=list)
    initial_contribution: str = ''
    voice_index: int = 0


class Objective(BaseModel):
    id: str
    description: str
    evidence: str
    alternatives: list[str] = Field(default_factory=list)


class ScenarioAction(BaseModel):
    id: str
    participant_id: str
    description: str
    reason: str = ''
    references: list[str] = Field(default_factory=list)


class UnknownQuantity(BaseModel):
    subject: str
    units: list[str]
    clarification: str


class ScenarioDefinition(BaseModel):
    version: Literal[2] = 2
    activity_id: str
    setting: str
    facts: list[str] = Field(min_length=1, max_length=100)
    participants: list[Participant] = Field(min_length=2, max_length=5)
    objectives: list[Objective] = Field(min_length=1, max_length=20)
    prerequisites: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    negotiation: dict | None = None
    actions: list[ScenarioAction] = Field(default_factory=list)
    unknown_quantities: list[UnknownQuantity] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_roster(self):
        if sum(p.kind == 'learner' for p in self.participants) != 1:
            raise ValueError('A scene needs exactly one learner')
        if len({p.id for p in self.participants}) != len(self.participants):
            raise ValueError('Participant IDs must be unique')
        if len({o.id for o in self.objectives}) != len(self.objectives):
            raise ValueError('Objective IDs must be unique')
        if any(not p.name.strip() or not p.role.strip() for p in self.participants):
            raise ValueError('Every participant needs a name and role')
        if any(a.participant_id not in {p.id for p in self.participants} for a in self.actions):
            raise ValueError('Scenario actions must belong to a participant in this case')
        if self.negotiation:
            case = self.negotiation
            if not all(isinstance(case.get(key),dict) for key in ('public','buyer','seller')):
                raise ValueError('Negotiation cases require public terms, a buyer maximum and a seller minimum')
            for side, key in (('buyer','maximum'), ('seller','minimum')):
                value = case[side].get(key)
                if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
                    raise ValueError('Reservation limits must be finite positive numbers')
            if type(case['public'].get('seats')) is not int or not 1 <= case['public']['seats'] <= 1000:
                raise ValueError('A package needs a bounded integer seat count')
            if not isinstance(case.get('feasibility',{}),dict):
                raise ValueError('Feasibility rules must be an object')
            for value in case.get('feasibility',{}).values():
                if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
                    raise ValueError('Feasibility rules must be finite nonnegative numbers')
        return self


class SessionAction(BaseModel):
    action: Literal['interrupt', 'pause', 'resume', 'coach', 'correct', 'preferences',
                    'extra_practice', 'reflect', 'prepare', 'offer', 'accept', 'withdraw', 'skip']
    request_id: str = Field(min_length=1, max_length=100)
    expected_revision: int | None = Field(default=None, ge=0)
    data: dict = Field(default_factory=dict)


class PlaybackAck(BaseModel):
    utterance_id: str = Field(max_length=100)
    segment: int = Field(ge=0)


class ConversationEvent(BaseModel):
    id: int
    revision: int
    kind: str
    participant_id: str | None = None
    utterance_id: str | None = None
    payload: dict


class FloorState(BaseModel):
    floor: str = 'learner'
    generation: str | None = None
    paused: bool = False


class CoachIntervention(BaseModel):
    id: str
    objective_id: str
    level: int = Field(ge=0,le=3)
    text: str
    target: str
    awaiting_practice: bool = True
    created_at: str


class LearningEvidence(BaseModel):
    objective_id: str
    met: bool
    quotes: list[str]
    turn_ids: list[int]
    support: Literal['independent', 'supported', 'unassessed'] = 'unassessed'


class NegotiationTerms(BaseModel):
    price: float = Field(gt=0, le=10000000, allow_inf_nan=False)
    currency: Literal['USD'] = 'USD'
    seats: int = Field(ge=1, le=1000)
    delivery_days: int = Field(ge=1, le=365)
    support_months: int = Field(ge=0, le=36)
    rationale: str = Field(min_length=3, max_length=1500)
    condition: str = Field(default='', max_length=1000)


class RuntimePreferences(BaseModel):
    correction_style: Literal['on_request', 'selective', 'debrief'] = 'on_request'
    coach_language: Literal['English', 'Urdu'] = 'English'
    challenge: Literal['beginner', 'intermediate', 'advanced'] = 'beginner'
    intensity: Literal['gentle', 'balanced', 'challenging'] = 'gentle'
    captions: bool = True


class TurnPlan(BaseModel):
    speaker_ids: list[str] = Field(max_length=2)
    purpose: str = Field(default='', max_length=600)
    topic: str = Field(default='', max_length=200)
