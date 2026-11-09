"""Stream short role-scoped replies while keeping state changes authoritative."""
import asyncio
import json
import logging
import re
import time
import threading
from intelligence.replies import public_reply
from domain.errors import DomainError
from intelligence.conversation_direction import grounded_reply
from services.group_draft import GroupDraft
from modules.llm_quota import QuotaDeferred, seconds

logger = logging.getLogger(__name__)
REVIEWS = set()
PENDING_REVIEWS = {}
LAST_REVIEW = {}
REVIEW_IDLE_SECONDS = 12
REVIEW_INTERVAL_SECONDS = 120


async def review_session(training, llm, sid, background=False):
    runtime = training.context.runtime
    if not llm or not hasattr(llm, 'evaluate_runtime'):
        return
    context = runtime.evaluation_context(sid)
    _, state = runtime.read(sid)
    if not state or (state.get('evaluation') or {}).get('revision') == context['revision']:
        return
    key = (str(training.path), sid, context['revision'])
    if any(item[:2] == key[:2] for item in REVIEWS):
        return
    REVIEWS.add(key)
    failed = False
    try:
        kwargs={'background':background} if getattr(llm,'supports_quota_priority',False) is True else {}
        result = await asyncio.wait_for(asyncio.to_thread(llm.evaluate_runtime, context, **kwargs), 25)
        runtime.save_evaluation(sid, context['revision'], result)
        if isinstance(result,dict):
            grouped={}
            for item in result.get('contradictions',[]) if isinstance(result.get('contradictions'),list) else []:
                if isinstance(item,dict) and isinstance(item.get('utterance_id'),str):grouped.setdefault(item['utterance_id'],[]).append(item)
            for uid,items in grouped.items():runtime.record_repairs(sid,uid,{'contradictions':items})
    except QuotaDeferred as exc:
        failed = True
        # Deferred evidence is unassessed, not a provider failure or a new score.
        schedule_review(training,llm,sid,min_delay=exc.retry_after)
    except Exception as exc:
        failed = True
        if getattr(exc,'status_code',None)==429:
            schedule_review(training,llm,sid,min_delay=60)
            return
        logger.warning('Runtime assessment unavailable: %s', type(exc).__name__)
        runtime.unavailable(sid, 'Evidence review is unavailable. Your conversation is saved; use guided practice or try again later.')
    finally:
        REVIEWS.discard(key)
        # Coalesce overlapping requests, then review the newest delivered transcript.
        _, latest = runtime.read(sid)
        if not failed and latest and latest['evidence_revision'] != context['revision'] and runtime.ready_for_review(sid):
            schedule_review(training, llm, sid, immediate=True)


BACKGROUND = set()


def cancel_scheduled_review(training,sid):
    pending=PENDING_REVIEWS.pop((str(training.path),sid),None)
    if pending:pending.cancel()


def schedule_review(training, llm, sid, immediate=False, min_delay=0):
    if not llm or not hasattr(llm,'evaluate_runtime'):return
    key=(str(training.path),sid)
    cancel_scheduled_review(training,sid)
    async def delayed():
        provider_key=id(getattr(llm,'provider',llm))
        delay=max(min_delay,0 if immediate else REVIEW_IDLE_SECONDS,REVIEW_INTERVAL_SECONDS-(time.monotonic()-LAST_REVIEW.get(provider_key,0)))
        await asyncio.sleep(delay)
        PENDING_REVIEWS.pop(key,None)
        if training.context.runtime.ready_for_review(sid):
            LAST_REVIEW[provider_key]=time.monotonic()
            await review_session(training,llm,sid,background=True)
    task = asyncio.create_task(delayed())
    PENDING_REVIEWS[key]=task
    BACKGROUND.add(task)
    task.add_done_callback(BACKGROUND.discard)


async def wait_for_delivery(runtime,sid,uid,generation,timeout=75):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if not runtime.active(sid,generation):return False
        with runtime.connect() as db:
            row=db.execute('SELECT status FROM conversation_utterances WHERE id=?',(uid,)).fetchone()
        if not row or row['status']=='interrupted':return False
        if row['status']=='delivered':return True
        await asyncio.sleep(.1)
    return False


async def run_structured_turn(owner, sid, payload, sentence_callback=None):
    runtime = owner.training.context.runtime
    generation, cached = runtime.start(sid, payload)
    if cached is not None:
        return cached
    cancel_scheduled_review(owner.training,sid)
    began = time.perf_counter()
    session = owner.training.session(sid)
    definition, state = runtime.read(sid)
    spoken = sentence_callback is not None
    responses = []
    provider_failed = owner.llm is None
    prefetch = None
    group = None
    stop_prefetch = threading.Event()
    try:
        sources = []
        if session.get('document_ids'):
            ready = {d['id'] for d in owner.training.documents(session['user_id']) if d['status'] == 'ready'}
            if not set(session['document_ids']).issubset(ready):
                raise DomainError('document_unavailable', 'Prepare a new lesson with available sources.', status_code=409)
            sources = await asyncio.to_thread(owner.training.search, payload.text, session['user_id'], document_ids=session['document_ids'])
        speakers = runtime.speakers(sid)
        if (owner.llm and getattr(owner.llm,'supports_group_response',False) is True
                and not grounded_reply(definition,state,speakers[0])
                and not (state['completed'] and not state['extra_practice'])):
            group_prompt=runtime.group_prompt(sid,speakers,sources)
            if group_prompt:group=GroupDraft(owner.llm,group_prompt)
        index = 0
        while index < len(speakers) and index < 2:
            speaker = speakers[index]
            if not runtime.active(sid, generation):
                break
            uid = runtime.create_utterance(sid, generation, speaker)
            emitted = []
            filtered = []
            local_reply = grounded_reply(definition,state,speaker) if index==0 else None
            def emit(sentence):
                cleaned = public_reply(sentence).strip()
                if not cleaned or not runtime.active(sid, generation):
                    return
                cleaned = runtime.validate_sentence(sid, speaker, cleaned)
                if not cleaned:
                    filtered.append(sentence)
                    return
                segment = runtime.sentence(sid, uid, cleaned, spoken)
                if segment is None:
                    return
                emitted.append(cleaned)
                if sentence_callback:
                    with runtime.connect() as db:
                        event=db.execute("SELECT id,revision FROM conversation_events WHERE session_id=? AND utterance_id=? AND kind='speech_text' ORDER BY id DESC LIMIT 1",(sid,uid)).fetchone()
                    sentence_callback(cleaned, speaker['name'], {'event_id':event['id'],'revision':event['revision'],'utterance_id': uid, 'segment': segment, 'participant_id': speaker['id'], 'generation_id': generation, 'voice_index': speaker['voice_index']})
            if state['completed'] and not state['extra_practice']:
                emit('Thank you. We have covered what we needed to discuss. It was good talking with you.')
            elif local_reply:
                for sentence in re.findall(r'.+?(?:[.!?](?=\s|$)|$)',local_reply):
                    if sentence.strip():emit(sentence.strip())
            elif owner.llm:
                # Deliver the authoritative repair explicitly, once. An unheard
                # correction stays pending so interruption cannot erase it.
                _, current_state = runtime.read(sid)
                repairs = [r for r in current_state.get('repairs', []) if not r.get('resolved')][-2:]
                for repair in repairs:
                    emit('I need to correct an earlier statement: ' + repair['binding_fact'])
                instruction = runtime.prompt(sid, speaker, sources)
                # Already queued ahead of this reply; do not repeat it in generated dialogue.
                if repairs:instruction['context']['corrections_to_acknowledge'] = []
                def generate():
                    buffer = ''
                    tokens = prefetched_tokens if prefetched_tokens is not None else (
                        group.tokens(speaker['id']) if group and speaker['id'] in group.ids
                        else owner.llm.generate_contextual_response(instruction))
                    for token in tokens:
                        if not runtime.active(sid, generation):
                            return
                        buffer += token
                        while True:
                            match = re.search(r'^(.+?[.!?])(?:\s+|$)', buffer, re.S)
                            if not match:
                                break
                            emit(match.group(1))
                            buffer = buffer[match.end():]
                            if len(emitted)>=2:return
                    if buffer.strip():
                        emit(buffer)
                try:
                    prefetched_tokens = await prefetch if prefetch else None
                    prefetch = None
                    worker = asyncio.create_task(asyncio.to_thread(generate))
                    await asyncio.wait_for(worker, 20)
                except asyncio.TimeoutError:
                    provider_failed = True
                    runtime.unavailable(sid,'The response timed out. Your words are saved; retry the response when you are ready.',uid)
                except asyncio.CancelledError:
                    runtime.fail(sid, generation)
                    raise
                except Exception as exc:
                    logger.warning('Character provider unavailable: %s', type(exc).__name__)
                    provider_failed = True
                    limited=getattr(exc,'status_code',None)==429
                    headers=getattr(getattr(exc,'response',None),'headers',{})
                    retry_after=max(1,seconds(headers.get('retry-after'),15)) if limited else None
                    limit_name='daily token limit' if (getattr(exc,'limit_reason',None) or {}).get('kind')=='tokens per day' else 'usage limit'
                    message=(f'The AI provider has reached its {limit_name}. Your words are saved. Retry in about {int(retry_after)+1} seconds.'
                             if limited else 'The AI service could not respond. Your words are saved; retry the response.')
                    runtime.unavailable(sid,message,uid,retry_after)
            else:
                runtime.unavailable(sid,'The conversation provider is offline. Your words are saved. You can use the coach or retry after reconnecting.',uid)
            if not emitted and filtered and not provider_failed:
                emit(runtime.repetition_repair(sid,speaker))
            if not emitted and not provider_failed:
                provider_failed=True
                runtime.unavailable(sid,'The AI did not provide a usable new response. Your words are saved; retry the response.',uid)
            if emitted:
                responses.append({'speaker': speaker['name'], 'speaker_role': speaker['role'], 'participant_id': speaker['id'],
                    'team': speaker['team'], 'text': ' '.join(emitted), 'utterance_id': uid, 'correlation_id': uid,
                    'response_mode':'grounded' if local_reply else 'generated'})
            if provider_failed and not local_reply:break
            runtime.response_available(sid)
            index += 1
            if group and index==1 and ' '.join(group.taken.get(speaker['id'],'').split())!=' '.join(' '.join(emitted).split()):
                # A changed/filtered first reply invalidates the speculative continuation.
                group.close()
                group=None
            if index==1 and emitted and not any(p.get('_directed') for p in speakers[1:]):
                handoff=runtime.handoff(sid,speaker,' '.join(emitted))
                if handoff:
                    speakers=speakers[:1]+[handoff]
            if spoken and index < len(speakers):
                # Prepare privately during playback; never publish a speculative
                # response or count its predecessor as heard before the ACK.
                if owner.llm:
                    draft_instruction=runtime.prompt(sid,speakers[index],sources,anticipated={
                        'speaker_id':speaker['id'],'speaker':speaker['name'],'text':' '.join(emitted),'utterance_id':uid})
                    def draft():
                        pieces=[]
                        tokens=(group.tokens(speakers[index]['id']) if group and speakers[index]['id'] in group.ids
                                else owner.llm.generate_contextual_response(draft_instruction))
                        for token in tokens:
                            if stop_prefetch.is_set() or not runtime.active(sid,generation):return []
                            pieces.append(token)
                        return pieces
                    async def prefetch_draft():
                        return await asyncio.wait_for(asyncio.to_thread(draft),20)
                    prefetch=asyncio.create_task(prefetch_draft())
                if not await wait_for_delivery(runtime,sid,uid,generation):
                    stop_prefetch.set()
                    if prefetch:
                        prefetch.cancel()
                        await asyncio.gather(prefetch,return_exceptions=True)
                        prefetch=None
                    break
        result = {'text': responses[0]['text'] if responses else '', 'responses': responses,
            'audio_b64': None, 'engine': owner.engine, 'correlation_id': generation,
            'session_progress': runtime.progress(sid), 'assessment': None,
            'sources': [{'name': s['name'], 'document_id': s.get('document_id'), 'excerpt': s['text'][:900]} for s in sources],
            'runtime': runtime.view(sid), 'guided_practice': provider_failed}
        if not spoken and getattr(payload,'synthesize_audio',False) and owner.synthesize and result['text']:
            try:
                result['audio_b64'] = await asyncio.wait_for(asyncio.to_thread(owner.synthesize,result['text']),20)
            except Exception:
                result['speech_unavailable'] = True
        runtime.finish(sid, generation, result)
        if not provider_failed and runtime.ready_for_review(sid):schedule_review(owner.training, owner.llm, sid)
        owner.metrics.record('roleplay', 'structured conversation', (time.perf_counter()-began)*1000, True, correlation_id=generation)
        return result
    except BaseException:
        runtime.fail(sid, generation)
        raise
    finally:
        stop_prefetch.set()
        if group:group.close()
        if prefetch:
            prefetch.cancel()
            await asyncio.gather(prefetch,return_exceptions=True)
