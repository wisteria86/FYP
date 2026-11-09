"""Organization membership, invites and the trainer summary."""
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


class InviteRequest(BaseModel):
    role: str = Field(default='learner', max_length=20)


class JoinRequest(BaseModel):
    code: str = Field(min_length=6, max_length=80)


def build_organization_router(get_service, current_user):
    router = APIRouter(prefix='/api/organization', tags=['organization'])

    @router.get('')
    def overview(request: Request):
        return get_service().overview(current_user(request))

    @router.post('/invites')
    def invite(payload: InviteRequest, request: Request):
        return get_service().create_invite(current_user(request), payload.role)

    @router.post('/join')
    def join(payload: JoinRequest, request: Request):
        return get_service().join(current_user(request), payload.code)

    @router.get('/team')
    def team(request: Request):
        return get_service().team_progress(current_user(request))

    return router
