"""Coordinate one training turn through application and intelligence interfaces.

No FastAPI requests, provider imports, or SQL. Provider snapshots are supplied
by the composition root; tests can replace any capability independently.
"""
import asyncio
import base64
import logging
import re
import time
import uuid
import threading
from domain.errors import DomainError
from intelligence.replies import public_reply, redundant_correction

logger = logging.getLogger(__name__)


class TrainingOrchestrator:
    def __init__(self, training, llm, synthesize, metrics, sample_rate, engine):
        self.training, self.llm, self.synthesize = training, llm, synthesize
        self.metrics, self.sample_rate, self.engine = metrics, sample_rate, engine

    async def run_turn(self, session_id, payload, sentence_callback=None, response_callback=None):
        pipeline_started = time.perf_counter()
        try:
            session = self.training.session(session_id)
            if session.get('document_ids'):
                ready={doc['id'] for doc in self.training.documents(session['user_id']) if doc['status']=='ready'}
                if not set(session['document_ids']).issubset(ready):
                    raise DomainError('document_unavailable','Selected policy documents are no longer available. Prepare a new lesson.',status_code=409)
            self.training.add_turn(session_id, "user", payload.text, payload.duration_seconds)
            # One shared, persisted judgement precedes dialogue and auto-close.
            # Bound the extra work; offline/unsupported providers retain local
            # evidence rules rather than freezing a call waiting for a judge.
            if self.llm and hasattr(self.llm,'evaluate_objectives') and session['skill_id']!='company-knowledge':
                review_started=time.perf_counter()
                try:
                    count=sum(t['role']=='user' for t in session['turns'])+1
                    review=await asyncio.wait_for(asyncio.to_thread(
                        self.llm.evaluate_objectives,self.training.completion_review_prompt(session_id)),timeout=3.5)
                    accepted=self.training.save_completion_review(session_id,review,count)
                    self.metrics.record('completion','objective review',(time.perf_counter()-review_started)*1000,accepted)
                except Exception as exc:
                    logger.warning('Completion review unavailable; retaining local evidence checks: %s',type(exc).__name__)
                    self.metrics.record('completion','objective review',(time.perf_counter()-review_started)*1000,False,error_type=type(exc).__name__)
            turn_progress = self.training.evaluate_progress(session_id)
            stage_started = time.perf_counter()
            ids=session.get('document_ids')
            if session.get('knowledge_mode','off')=='off':sources=[]
            else:
                sources = await asyncio.get_running_loop().run_in_executor(None, lambda:self.training.search(payload.text+' '+session['situation'],session['user_id'],document_ids=ids))
                if not sources:sources=session.get('knowledge_evidence',[])
            retrieval_ms = (time.perf_counter() - stage_started) * 1000
            ttft_ms = None
            llm_ms = 0.0
            llm_error = None
            responses = []
            caption_preferences = self.training.caption_preferences(session_id)
    
            def generate_timed(instruction: str):
                if not self.llm:
                    return "", None, 0.0
                cancelled=threading.Event()
                def run():
                    generation_started = time.perf_counter()
                    first_token_ms = None
                    tokens = []
                    delivered = 0
                    for token in self.llm.generate_contextual_response(instruction):
                        if cancelled.is_set():
                            return '',None,0.0
                        if first_token_ms is None:
                            first_token_ms = (time.perf_counter() - generation_started) * 1000
                        tokens.append(token)
                        if sentence_callback:
                            public = public_reply("".join(tokens))
                            if session.get('training_language')=='English' and redundant_correction(public,payload.text):
                                # Do not speak an identical phrase as a correction.
                                continue
                            sentences = list(re.finditer(r'.+?[.!?](?:\s|$)', public, re.DOTALL))
                            for match in sentences[delivered:]:
                                sentence_callback(match.group().strip(), speaker["name"])
                                delivered += 1
                    if sentence_callback:
                        public = public_reply("".join(tokens))
                        if session.get('training_language')=='English' and redundant_correction(public,payload.text):
                            public=self.training.fallback_reply(session_id,speaker)
                        matches = list(re.finditer(r'.+?[.!?](?:\s|$)', public, re.DOTALL))
                        tail = public[matches[-1].end():].strip() if matches else public
                        if tail:
                            sentence_callback(tail, speaker["name"])
                    return "".join(tokens), first_token_ms, (time.perf_counter() - generation_started) * 1000
                run.cancel=cancelled.set
                return run
    
            speakers = self.training.response_speakers(session_id)
            if turn_progress['outcome'] == 'success':
                speakers = speakers[:1]
            for speaker in speakers:
                reply = ""
                caption_text = None
                if turn_progress['outcome'] == 'success':
                    # Decide before streaming: a completed scene must not speak a
                    # fresh question and then abruptly disappear into results.
                    reply = self.training.fallback_reply(session_id, speaker)
                    if sentence_callback:
                        sentence_callback(reply, speaker['name'])
                elif self.llm:
                    prompt = self.training.prompt(session_id, sources, speaker)
                    runner = generate_timed(prompt)
                    try:
                        raw_reply, first_token, generation_ms = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, runner),timeout=20)
                        if ttft_ms is None:
                            ttft_ms = first_token
                        llm_ms += generation_ms
                        reply = public_reply(raw_reply) or self.training.fallback_reply(session_id, speaker)
                    except asyncio.CancelledError:
                        runner.cancel()
                        raise
                    except Exception as exc:
                        runner.cancel()
                        llm_error = type(exc).__name__
                        logger.warning("LLM turn failed for %s; using local fallback: %s", speaker["name"], exc)
                        reply = self.training.fallback_reply(session_id, speaker)
                else:
                    reply = self.training.fallback_reply(session_id, speaker)
    
                is_user_query = any(q in payload.text.lower() for q in (
                    "?", "what", "who", "why", "how", "explain", "context", "background",
                    "task", "goal", "objective", "clarif", "mean", "help", "tell me", "should i", "do i"
                ))
                if is_user_query and any(phrase in reply.lower() for phrase in (
                    "not the excuse", "focus on the solution", "make excuses", "making excuses"
                )):
                    reply = self.training.fallback_reply(session_id, speaker)
                if session.get("training_language") == "English" and any(phrase in reply.lower() for phrase in (
                    "what specific action", "propose we take next", "focus on the solution",
                    "stakeholder impact", "action plan"
                )):
                    logger.warning("Rejected workplace-coaching leakage in language lesson %s", session_id)
                    reply = self.training.fallback_reply(session_id, speaker)
    
                if response_callback:
                    if session.get('training_language')=='English' and redundant_correction(reply,payload.text):
                        reply=self.training.fallback_reply(session_id,speaker)
                    response_callback(reply, speaker["name"])
                elif session.get('training_language')=='English' and redundant_correction(reply,payload.text):
                    reply=self.training.fallback_reply(session_id,speaker)
                if caption_preferences["translate"] and self.llm:
                    try:
                        translation_started = time.perf_counter()
                        translated = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(
                            None, self.llm.translate_caption, reply, caption_preferences["language"]
                        ),timeout=8)
                        llm_ms += (time.perf_counter() - translation_started) * 1000
                        caption_text = public_reply(translated) or None
                    except Exception as exc:
                        logger.warning("Caption translation failed: %s", exc)
    
                correlation_id = uuid.uuid4().hex
                self.training.add_turn(
                    session_id, "assistant", reply, speaker_name=speaker["name"], caption_text=caption_text
                )
                responses.append({
                    "text": reply,
                    "speaker": speaker["name"],
                    "speaker_role": speaker["role"],
                    "team": speaker["team"],
                    "caption_text": caption_text,
                    "caption_language": caption_preferences["language"] if caption_text else None,
                    "correlation_id": correlation_id,
                })
    
            if not responses:
                raise ValueError("This lesson has no AI participant")
            reply = responses[0]["text"]
            correlation_id = responses[0]["correlation_id"]
            session_progress = self.training.evaluate_progress(session_id)
            assessment = None
            if session_progress["outcome"] == "success":
                language_evaluation = None
                if session.get("training_language") == "English" and self.llm and hasattr(self.llm, "evaluate_english"):
                    try:
                        language_evaluation = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(
                            None, self.llm.evaluate_english, self.training.assessment_prompt(session_id)
                        ),timeout=15)
                    except Exception as exc:
                        logger.warning("Language assessment failed; using deterministic assessment: %s", exc)
                assessment = self.training.assess(session_id, language_evaluation)
            audio = None
            tts_ms = 0.0
            if payload.synthesize_audio:
                stage_started = time.perf_counter()
                audio = await asyncio.get_running_loop().run_in_executor(None, self.synthesize, reply)
                tts_ms = (time.perf_counter() - stage_started) * 1000
            audio_seconds = ((len(base64.b64decode(audio)) - 44) / 2 / self.sample_rate) if audio else None
            total_ms = (time.perf_counter() - pipeline_started) * 1000
            self.metrics.record("roleplay", "conversation turn", total_ms, True, retrieval_ms=round(retrieval_ms, 1),
                           llm_ttft_ms=round(ttft_ms, 1) if ttft_ms is not None else None,
                           llm_ms=round(llm_ms, 1), tts_ms=round(tts_ms, 1), audio_seconds=round(audio_seconds, 2) if audio_seconds else None,
                           tts_realtime_factor=round(tts_ms / (audio_seconds * 1000), 2) if audio_seconds else None,
                           mode="ai" if self.llm and not llm_error else "fallback", llm_error=llm_error,
                           correlation_id=correlation_id, response_ready_ms=round(total_ms, 1))
            return {"text": reply, "responses": responses, "audio_b64": audio, "engine": self.engine, "correlation_id": correlation_id,
                    "session_progress": session_progress, "assessment": assessment,
                    "sources": [{'document_id':x.get('document_id'),"name": x["name"],'excerpt':x['text'][:900]} for x in sources]}
        except ValueError as exc:
            self.metrics.record("roleplay", "conversation turn", (time.perf_counter() - pipeline_started) * 1000, False, error_type=type(exc).__name__)
            raise DomainError('session_not_found', str(exc), status_code=404) from exc
        except Exception as exc:
            self.metrics.record("roleplay", "conversation turn", (time.perf_counter() - pipeline_started) * 1000, False, error_type=type(exc).__name__)
            raise
