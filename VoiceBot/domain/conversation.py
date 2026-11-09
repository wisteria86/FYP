"""Versioned runtime contracts. Private scenario records never cross learner APIs."""
from typing import Literal
import math
import re
from pydantic import BaseModel, Field, model_validator


class ParticipantKnowledge(BaseModel):
    public_knowledge: list[str] = Field(default_factory=list)
    private_knowledge: dict = Field(default_factory=dict)


class CharacterCard(BaseModel):
    """What makes a case-pack character a person rather than a job title."""
    want: str = Field(min_length=8)
    hidden_need: str = ''
    attitude: str = Field(min_length=4)
    speech: str = Field(min_length=4)
    tactics: list[str] = Field(default_factory=list)
    pressure: dict[str, str] = Field(default_factory=dict)


class LearnerBrief(BaseModel):
    """Everything a lost learner needs in order to be re-oriented."""
    you_are: str = Field(min_length=4)
    situation: str = Field(min_length=8)
    task: str = Field(min_length=8)
    done_looks_like: str = Field(min_length=8)


class LedgerFact(BaseModel):
    """A case fact. Owner 'public' is shared; otherwise only that participant knows it."""
    id: str
    owner: str = 'public'
    text: str = Field(min_length=4)
    available_from: str | None = None


class Beat(BaseModel):
    """One stage of a scene: who drives it and how it moves on if it stalls."""
    id: str
    goal: str = Field(min_length=4)
    driver: str
    objectives: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    opportunity: list[str] = Field(default_factory=list)
    orient: str = ''
    fallback: list[str] = Field(default_factory=list)
    stall_turns: int = Field(default=3, ge=1, le=12)
    min_turns: int = Field(default=1, ge=1, le=8)
    second_speaker: str | None = None
    second_line: str = ''


class ExpertNote(BaseModel):
    """Authored teaching knowledge for one objective."""
    good: str = Field(min_length=8)
    common_mistakes: list[str] = Field(default_factory=list)
    micro_lesson: str = Field(min_length=8)
    model: str = Field(min_length=4)
    smaller_step: str = Field(min_length=4)
    subskills: list[str] = Field(default_factory=list)


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
    card: CharacterCard | None = None


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
    version: Literal[2, 3] = 2
    activity_id: str
    archetype: str = 'general'
    level: Literal['beginner', 'intermediate', 'advanced'] = 'intermediate'
    brief: LearnerBrief | None = None
    ledger: list[LedgerFact] = Field(default_factory=list)
    beats: list[Beat] = Field(default_factory=list)
    expert_notes: dict[str, ExpertNote] = Field(default_factory=dict)
    forbidden_claims: list[str] = Field(default_factory=list)
    closing_line: str = ''
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
        if self.version == 3:
            self._validate_case_pack()
        return self

    def _validate_case_pack(self):
        """A case pack must give every character something real to say and a scene to run."""
        ai = {p.id: p for p in self.participants if p.kind == 'ai'}
        objective_ids = {o.id for o in self.objectives}
        beat_ids = [b.id for b in self.beats]
        if self.brief is None:
            raise ValueError('A case pack needs a learner brief')
        if not self.beats or not self.ledger:
            raise ValueError('A case pack needs beats and a fact ledger')
        if len(set(beat_ids)) != len(beat_ids) or len({f.id for f in self.ledger}) != len(self.ledger):
            raise ValueError('Beat and fact IDs must be unique')
        for person in ai.values():
            if person.card is None:
                raise ValueError(f'{person.name} needs a character card')
            if person.card.want.lower().startswith('fulfil your role'):
                raise ValueError(f'{person.name} has a generic goal')
        generic = ('practice focus', 'participants retain', 'expect a follow-up', 'your partner should', 'keep the lesson setting')
        for fact in self.ledger:
            if any(term in fact.text.lower() for term in generic):
                raise ValueError(f'Fact {fact.id} contains a stage direction')
            if fact.owner != 'public' and fact.owner not in ai:
                raise ValueError(f'Fact {fact.id} has an unknown owner')
            if fact.available_from and fact.available_from not in beat_ids:
                raise ValueError(f'Fact {fact.id} refers to an unknown beat')
        covered = set()
        for beat in self.beats:
            if beat.driver not in ai:
                raise ValueError(f'Beat {beat.id} is driven by an unknown character')
            if beat.second_speaker and beat.second_speaker not in ai:
                raise ValueError(f'Beat {beat.id} has an unknown second speaker')
            if not set(beat.objectives) <= objective_ids:
                raise ValueError(f'Beat {beat.id} refers to an unknown objective')
            if not beat.opportunity or not beat.fallback or not beat.orient:
                raise ValueError(f'Beat {beat.id} needs opportunity, orientation and fallback lines')
            covered |= set(beat.objectives)
        missing = objective_ids - covered - (set(self.expert_notes) & {o.id for o in self.objectives if o.id.startswith('prep')})
        if missing:
            raise ValueError(f'No beat creates a chance to show: {sorted(missing)}')
        if set(self.expert_notes) != objective_ids:
            raise ValueError('Every objective needs exactly one expert note')
        if self.negotiation:
            # A reservation limit must never sit in text a character can read out.
            limits = {str(int(self.negotiation[side][key])) for side, key in (('buyer', 'maximum'), ('seller', 'minimum'))}
            for fact in self.ledger:
                digits = set(re.findall(r'\d+', fact.text.replace(',', '')))
                if digits & limits:
                    raise ValueError(f'Fact {fact.id} exposes a reservation limit')


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
