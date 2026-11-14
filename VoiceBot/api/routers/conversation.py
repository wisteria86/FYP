"""Owner-authorized runtime controls and resumable event delivery."""
import asyncio
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from domain.conversation import SessionAction, PlaybackAck


class RewindRequest(BaseModel):
    turn_id: int | None = Field(default=None, ge=1)


class BranchRequest(BaseModel):
    turn_id: int = Field(ge=1)


def build_conversation_router(training, authorize, get_llm):
    router = APIRouter(prefix='/api/sessions', tags=['conversation'])
    service = lambda: training() if callable(training) else training
    runtime = lambda: service().context.runtime

    @router.get('/{sid}/runtime')
    def state(sid: str, request: Request):
        authorize(request, sid)
        return runtime().view(sid)

    @router.post('/{sid}/actions')
    async def action(sid: str, payload: SessionAction, request: Request):
        authorize(request, sid)
        try:
            result = runtime().action(sid, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if payload.action in {'correct', 'offer', 'accept', 'withdraw', 'prepare'}:
            from services.structured_orchestrator import schedule_review
            schedule_review(service(), get_llm(), sid)
        return {**result, 'runtime': runtime().view(sid)}

    @router.post('/{sid}/rewind')
    def rewind(sid: str, payload: RewindRequest, request: Request):
        """Take back the latest learner turn (or a chosen one) and everything after it."""
        authorize(request, sid)
        if runtime().rewind(sid, payload.turn_id) is None:
            raise HTTPException(404, 'This lesson has no live conversation.')
        return {'runtime': runtime().view(sid), 'session': service().context.session.session(sid)}

    @router.get('/{sid}/game-tape')
    def game_tape(sid: str, request: Request):
        """The turn-by-turn debrief for a lesson."""
        authorize(request, sid)
        tape = service().context.assessment.game_tape(sid)
        if tape is None:
            raise HTTPException(404, 'This lesson has no scene to replay.')
        return tape

    @router.post('/{sid}/branch')
    def branch(sid: str, payload: BranchRequest, request: Request):
        """Start a new practice attempt from just before one of the learner's turns."""
        owner = authorize(request, sid)['user_id']  # authorize returns the session after checking ownership
        try:
            return service().context.session.branch_session(owner, sid, payload.turn_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post('/{sid}/playback')
    async def playback(sid: str, payload: PlaybackAck, request: Request):
        authorize(request, sid)
        runtime().acknowledge(sid, payload.utterance_id, payload.segment)
        if runtime().ready_for_review(sid):
            from services.structured_orchestrator import schedule_review
            schedule_review(service(), get_llm(), sid)
        return {'accepted': True}

    @router.get('/{sid}/events')
    async def events(sid: str, request: Request, after: int = 0):
        try:
            authorize(request, sid)
        except ValueError as exc:  # an old tab reconnecting to a lesson that no longer exists
            raise HTTPException(404, str(exc)) from exc
        try:
            cursor = max(after, int(request.headers.get('last-event-id', 0)))
        except ValueError:
            cursor = max(0, after)
        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                authorize(request, sid)
                rows = runtime().events(sid, cursor)
                for event in rows:
                    cursor = event['id']
                    event.pop('payload_json', None)
                    yield f"id: {cursor}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if not rows:
                    yield ': keepalive\n\n'
                await asyncio.sleep(.5)
        return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @router.delete('/{sid}/conversation-data')
    def erase(sid: str, request: Request):
        authorize(request, sid)
        with service().connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM assessment_evidence WHERE assessment_id IN (SELECT id FROM assessments WHERE session_id=?) OR turn_id IN (SELECT id FROM turns WHERE session_id=?)', (sid, sid))
            for table in ('conversation_events', 'conversation_requests', 'conversation_utterances', 'conversation_runtime', 'learning_reviews', 'turns', 'posture', 'turn_snapshots', 'withdrawn_turns'):
                column = 'source_session_id' if table == 'learning_reviews' else 'session_id'
                db.execute(f'DELETE FROM {table} WHERE {column}=?', (sid,))
            db.execute("UPDATE assessments SET strengths='[]',improvements='[]',evidence='[]',feedback='Conversation evidence deleted by learner.' WHERE session_id=?", (sid,))
            db.execute("UPDATE sessions SET scenario_snapshot_json='{}',situation='Conversation data deleted',status=CASE WHEN status='active' THEN 'cancelled' ELSE status END WHERE id=?", (sid,))
        return {'deleted': True}

    return router
