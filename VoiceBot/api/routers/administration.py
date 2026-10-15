"""Platform administrator API; demo mode never grants administrator access."""
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from config import Config
from typing import Literal


class SubskillUpdate(BaseModel):
    skill_id: str = Field(min_length=1,max_length=80)
    name: str = Field(min_length=1,max_length=160)
    description: str = Field(default='',max_length=3000)
    active: bool = True


class SkillUpdate(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    description: str = Field(max_length=3000)
    category: str = Field(default='workplace',min_length=1,max_length=80)
    active: bool = True


class ScenarioUpdate(BaseModel):
    context: str = Field(min_length=1,max_length=6000)
    objectives: list[str] = Field(min_length=1,max_length=20)
    success_criteria: list[str] = Field(min_length=1,max_length=20)
    opening_situation: str = Field(min_length=1,max_length=2000)
    active: bool = True

    @field_validator('objectives','success_criteria')
    @classmethod
    def meaningful_items(cls,values):
        if any(not value.strip() or len(value)>600 for value in values):
            raise ValueError('Use non-empty items, each at most 600 characters')
        return [value.strip() for value in values]


class ConfigurationUpdate(BaseModel):
    max_document_chunks: int = Field(ge=1,le=1000)


class ActivityCreate(ScenarioUpdate):
    skill_id: str = Field(min_length=1,max_length=80)
    title: str = Field(min_length=1,max_length=160)
    description: str = Field(min_length=1,max_length=3000)
    learner_role: str = Field(default='Learner',min_length=1,max_length=100)
    ai_roles: list[str] = Field(min_length=1,max_length=4)
    roleplay_mode: Literal['one_to_one','learner_with_ai_team','ai_team_vs_learner','round_robin'] = 'one_to_one'
    difficulty: Literal['beginner','intermediate','advanced','adaptive'] = 'adaptive'
    estimated_minutes: int = Field(default=15,ge=1,le=120)
    posture_mode: Literal['off','optional'] = 'off'
    knowledge_mode: Literal['off','optional','required'] = 'off'

class LessonSettings(BaseModel):
    posture_mode: Literal['off','optional']
    knowledge_mode: Literal['off','optional','required']


def build_administration_router(service, auth):
    router = APIRouter(prefix='/api/admin',tags=['administration'])
    def user(request):
        return auth.user_for_token(request.cookies.get(Config.AUTH_COOKIE_NAME))

    @router.get('/catalog')
    def catalog(request: Request):
        return service.catalog(user(request))

    @router.put('/skills/{identifier}')
    def save_skill(identifier: str, payload: SkillUpdate, request: Request):
        return service.save_skill(user(request),identifier,payload.model_dump())

    @router.put('/subskills/{identifier}')
    def save_subskill(identifier: str, payload: SubskillUpdate, request: Request):
        return service.save_subskill(user(request),identifier,payload.model_dump())

    @router.put('/activities/{identifier}')
    def create_activity(identifier: str, payload: ActivityCreate, request: Request):
        return service.save_activity(user(request),identifier,payload.model_dump())

    @router.put('/lesson-settings/{identifier}')
    def lesson_settings(identifier:str,payload:LessonSettings,request:Request):
        return service.save_lesson_settings(user(request),identifier,payload.model_dump())

    @router.put('/scenarios/{identifier}')
    def save_scenario(identifier: str, payload: ScenarioUpdate, request: Request):
        return service.save_scenario(user(request),identifier,payload.model_dump())

    @router.get('/configuration')
    def configuration(request: Request):
        return service.configuration(user(request))

    @router.put('/configuration')
    def configure(payload: ConfigurationUpdate, request: Request):
        return service.save_configuration(user(request),payload.max_document_chunks)

    return router
