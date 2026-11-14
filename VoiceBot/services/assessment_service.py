"""AssessmentService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService
from domain.entities import Assessment, AssessmentMetric
from intelligence.speech_analysis import TranscriptSpeechAnalysis
from intelligence.learning_rubrics import fallback_scores, valid_scores
from intelligence.posture_analysis import summarise as summarise_posture


class AssessmentService(ApplicationService):
    def assessment_prompt(self, session_id: str) -> str:
        """Build an evidence-only language assessment request for the model."""
        session = self.context.session.session(session_id)
        design = session.get("learning_design") or {}
        learner_lines = [turn["text"] for turn in session["turns"] if turn["role"] == "user"]
        return (
            f"Lesson: {session['title']} ({session.get('proficiency_level') or session['difficulty']})\n"
            f"Learning focus: {design.get('focus', session['title'])}\n"
            f"Lesson objectives: {'; '.join(session['objectives'])}\n"
            f"Target expressions: {'; '.join(design.get('examples', []))}\n"
            f"Learner transcript:\n" + "\n".join(f"- {line}" for line in learner_lines) +
            "\nEvaluate whether the learner actually demonstrated the lesson objectives. Quote only short exact learner "
            "phrases. You receive text, not audio: never infer pronunciation, intonation, pauses, accent or vocal confidence. "
            "phrases as evidence. Corrections must preserve the learner's intended meaning. A completed lesson can "
            "still receive a low score when the language was weak."
        )

    def assess(self, session_id: str, language_evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
        session = self.context.session.session(session_id)
        if session["assessment"]:
            return session["assessment"]
        if session['status'] != 'active':
            raise ValueError('Only an active session can be assessed')
        if session.get('runtime'):
            if (session['runtime'].get('scene') is not None):
                return self.assess_scene(session, (language_evaluation or {}).get('debrief'))
            return self.assess_runtime(session)
        user_turns = [t for t in session["turns"] if t["role"] == "user"]
        text = " ".join(t["text"] for t in user_turns)
        words = _words(text)
        word_count = len(words)
        spoken_seconds = sum(float(t.get("duration_seconds") or 0) for t in user_turns)
        voice_metrics = TranscriptSpeechAnalysis().analyze_audio(text, spoken_seconds)
        words_per_minute = round(voice_metrics.words_per_minute) if voice_metrics.words_per_minute is not None else None
        pace_score = max(35, 95 - abs(words_per_minute - 135) * .45) if words_per_minute else 70
        filler_count = sum(words.count(w) for w in ('um', 'uh', 'basically'))
        with self.connect() as db:
            subskills=[row['name'] for row in db.execute('SELECT name FROM subskill_catalog WHERE skill_id=? AND active=1',(session['skill_id'],))]
        progress=self.context.session.evaluate_progress(session_id)
        scores, rationales=fallback_scores(session,[turn['text'] for turn in user_turns],subskills,progress)
        supplied=(language_evaluation or {}).get('scores',{})
        if session.get('training_language')=='English' and isinstance(supplied,dict):
            scores.update(valid_scores(supplied,{'fluency','vocabulary','grammar','comprehension'}))
        if words_per_minute is not None:
            scores['delivery']=round(max(0,min(90,pace_score-filler_count*4)),1)
            rationales['delivery']=f'Observed pace {words_per_minute} words/minute; excludes pronunciation claims.'
        with self.connect() as db:
            posture = db.execute("SELECT AVG((slouching+head_position+shoulder_alignment+body_orientation)/4.0) score FROM posture WHERE session_id=?", (session_id,)).fetchone()["score"]
        if posture is not None and session.get('posture_enabled'):
            visual_scores={key:round(value,1) for key,value in zip(('slouching','head_position','shoulder_alignment','body_orientation'),self._posture_averages(session_id))}
        else:visual_scores={}
        if words_per_minute is None:
            scores.pop('delivery', None)
        scores = {k: round(max(0, min(100, v)), 1) for k, v in scores.items()}
        domain_assessment = Assessment(str(uuid.uuid4()), session_id)
        for metric, value in scores.items():
            domain_assessment.add_metric(AssessmentMetric(str(uuid.uuid4()), domain_assessment.id, metric,
                'visual' if metric == 'posture' else 'language', value))
        overall = domain_assessment.calculate_overall_score()
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        strengths = [f"{name.replace('_', ' ').title()} was a relative strength ({score:.0f}/100)." for name, score in ordered[:2]]
        if session.get("training_language") == "English":
            design = session.get("learning_design") or {}
            missing = [item["name"] for item in self.context.session.evaluate_progress(session_id)["criteria"] if not item["met"]]
            models = design.get("examples", [])
            improvements = [
                f"Practise {name}: try '{models[index % len(models)]}' with your own information."
                for index, name in enumerate(missing[:2])
            ] if models else []
            improvements = improvements or [f"Try {design.get('focus', session['title']).lower()} with new details, without looking at the examples.",
                                            'Use the same expressions with a different person or setting to check that you can transfer the skill.']
            evaluated_strengths = (language_evaluation or {}).get("strengths")
            evaluated_improvements = (language_evaluation or {}).get("improvements")
            if isinstance(evaluated_strengths, list) and evaluated_strengths:
                strengths = [str(item) for item in evaluated_strengths[:2]]
            if isinstance(evaluated_improvements, list) and evaluated_improvements:
                supported=[str(item) for item in evaluated_improvements if not re.search(r'\b(?:pronunciation|intonation|vocal|accent|pause)\b',str(item),re.I)]
                improvements = supported[:2] or improvements
        else:
            improvements = [f"Improve {name.replace('_', ' ')} by using one clear example and an explicit next step." for name, _ in ordered[-2:]]
        pace_evidence = f" Estimated speaking pace was {words_per_minute} words per minute." if words_per_minute else " Type-only turns were assessed without speaking pace."
        evidence = [f"You contributed {len(user_turns)} response(s) containing {word_count} words.{pace_evidence}"]
        evidence.extend(f"{item['name']}: {'demonstrated' if item['met'] else 'not demonstrated yet'}. " + ' / '.join(item['evidence']) for item in progress['criteria'])
        evidence.extend(f'{name}: {reason}' for name,reason in rationales.items())
        if session.get('skill_id')=='company-knowledge':
            evidence.extend(f"Policy evidence [{item['name']}]: {item['text'][:350]}" for item in session.get('knowledge_evidence',[]))
        if visual_scores:
            evidence.append('Visual indicators are separate presentation proxies and do not change language proficiency.')
            improvements.extend(f"Camera practice: improve {key.replace('_',' ')}; keep your head, shoulders and hips visible." for key,value in visual_scores.items() if value<70)
        if session.get("training_language") == "English":
            corrections = (language_evaluation or {}).get("corrections", [])
            if isinstance(corrections, list):
                for correction in corrections[:3]:
                    if not isinstance(correction, dict):
                        continue
                    original = str(correction.get("original", "")).strip()
                    improved = str(correction.get("improved", "")).strip()
                    reason = str(correction.get("reason", "")).strip()
                    if original and improved and original.lower() in text.lower():
                        evidence.append(f'You said “{original}”. A stronger version is “{improved}”. {reason}'.strip())
        feedback = ("Lesson objectives demonstrated. Review your feedback and practise the next activity."
                    if progress['outcome']=='success' else "Practice attempt recorded, not mastery. Repeat the missing objectives before advancing.")
        assessment_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM assessments WHERE session_id=?', (session_id,)).fetchone()
            if existing:
                return self._assessment_dict(existing)
            if not db.execute("SELECT 1 FROM sessions WHERE id=? AND status='active'", (session_id,)).fetchone():
                raise ValueError('Session is no longer active')
            db.execute("INSERT INTO assessments VALUES (?,?,?,?,?,?,?,?,?)", (assessment_id, session_id, overall, _json(scores), _json(strengths), _json(improvements), _json(evidence), feedback, _now()))
            db.execute("UPDATE sessions SET status='completed', completed_at=? WHERE id=?", (_now(), session_id))
            for name, value in scores.items():
                db.execute('INSERT INTO assessment_metrics(id,assessment_id,skill_id,metric_name,score,rationale) VALUES (?,?,?,?,?,?)',
                           (str(uuid.uuid4()),assessment_id,session['skill_id'],name,value,rationales.get(name,'Available session modality; prototype estimate')))
            self.context.adaptive.update_proficiency(db, session, scores, assessment_id)
        return self.context.session.session(session_id)["assessment"]

    def _speech_signal(self, session_id):
        """Recognizer confidence, shown as an experiment. It is never scored, and it is not pronunciation."""
        with self.connect() as db:
            values = []
            for row in db.execute("SELECT recognition_json FROM turns WHERE session_id=? AND role='user'", (session_id,)):
                recognition = json.loads(row['recognition_json'] or '{}')
                if isinstance(recognition.get('confidence'), (int, float)) and not recognition.get('corrected'):
                    values.append(float(recognition['confidence']))
        if len(values) < 3:
            return None
        return {'turns': len(values), 'average': round(sum(values) / len(values), 2),
                'note': 'Experimental. This is how confident the speech recognizer was, and it depends on your microphone, the room and how well the model handles your accent. It is not a pronunciation score, and it does not affect your results.'}

    def _posture_averages(self,session_id):
        with self.connect() as db:
            return tuple(db.execute('SELECT AVG(slouching),AVG(head_position),AVG(shoulder_alignment),AVG(body_orientation) FROM posture WHERE session_id=?',(session_id,)).fetchone())

    def scene_scores(self, session):
        """Separate, evidence-tied scores. Unassessed dimensions stay absent, never zero."""
        runtime = session['runtime']
        definition = self.context.runtime.read(session['id'])[0]
        evaluation = (runtime.get('completed_evaluation') if runtime['completed'] else runtime.get('evaluation')) or runtime.get('last_evaluation') or {}
        criteria = evaluation.get('criteria', [])
        credit = {'independent': 1, 'supported': .6}
        task = sum(credit.get(c.get('support'), 0) for c in criteria if c['met']) / max(1, len(definition['objectives']))
        scores, rationales = {}, {}
        if criteria:
            scores['task_achievement'] = round(task * 100, 1)
            rationales['task_achievement'] = 'Objectives shown with quoted evidence. Independent evidence counts fully; supported evidence counts 60%.'
        names = {'comprehension_relevance': 'comprehension', 'grammar': 'grammar', 'vocabulary': 'vocabulary', 'interaction': 'interaction'}
        for source, metric in names.items():
            item = evaluation.get('dimensions', {}).get(source)
            if isinstance(item, dict) and isinstance(item.get('level'), int):
                scores[metric] = item['level'] * 25
                rationales[metric] = item.get('reason') or 'Rated from quoted learner evidence.'
        learner = [t for t in session['turns'] if t['role'] == 'user']
        spoken = sum(float(t.get('duration_seconds') or 0) for t in learner)
        if spoken >= 10:
            text = ' '.join(t['text'] for t in learner)
            metrics = TranscriptSpeechAnalysis().analyze_audio(text, spoken)
            if metrics.words_per_minute:
                words = _words(text)
                fillers = sum(words.count(w) for w in ('um', 'uh', 'basically'))
                scores['delivery'] = round(max(0, min(90, 95 - abs(metrics.words_per_minute - 135) * .45 - fillers * 4)), 1)
                rationales['delivery'] = f'About {round(metrics.words_per_minute)} words a minute and {fillers} filler words. Pace only; pronunciation and accent are not assessed.'
        # N12: decision quality is reported beside language, and never mixed into it.
        for source in ('preparation', 'discovery', 'value_creation', 'concession_discipline', 'ethics', 'implementation'):
            item = evaluation.get('dimensions', {}).get(source)
            if definition.get('negotiation') and isinstance(item, dict) and isinstance(item.get('level'), int):
                scores[f'decision_{source}'] = item['level'] * 25
                rationales[f'decision_{source}'] = item.get('reason') or 'Rated from quoted learner evidence.'
        overall_parts = [scores[key] for key in ('comprehension', 'grammar', 'vocabulary', 'interaction') if key in scores]
        language = sum(overall_parts) / len(overall_parts) if overall_parts else None
        overall = scores.get('task_achievement', 0)
        if language is not None:
            overall = .6 * overall + .4 * language
        # Subskills are recorded only where this attempt produced a matching observation.
        subskills = {}
        for criterion in criteria:
            note = definition['expert_notes'].get(criterion['objective_id'], {})
            value = (85 if criterion.get('support') == 'independent' else 65) if criterion['met'] else 35
            for name in note.get('subskills', []):
                key = name.lower().replace(' ', '_')
                subskills[key] = max(subskills.get(key, 0), value)
        return scores, rationales, round(overall, 1), subskills, criteria, evaluation

    @staticmethod
    def _authored_debrief(definition, runtime, criteria):
        """The debrief when no model is available: authored expert notes and real quotes."""
        notes = definition['expert_notes']
        strengths, improvements = [], []
        for item in criteria:
            if item['met'] and item.get('quotes'):
                strengths.append(f"You said “{item['quotes'][0]}”. {notes[item['objective_id']]['good']}")
        missing = [item for item in criteria if not item['met']] or [{'objective_id': o['id']} for o in definition['objectives'] if not criteria]
        for item in missing:
            note = notes[item['objective_id']]
            improvements.append(f"{note['micro_lesson']} For example: “{note['model']}”")
        return strengths[:2], improvements[:2], (notes[missing[0]['objective_id']]['smaller_step'] if missing else 'Try a fresh version of this situation later to check the skill transfers.')

    def assess_scene(self, session, debrief=None):
        runtime = session['runtime']
        definition = self.context.runtime.read(session['id'])[0]
        scores, rationales, overall, subskills, criteria, evaluation = self.scene_scores(session)
        objectives = {o['id']: o['description'] for o in definition['objectives']}
        strengths, improvements, next_step = self._authored_debrief(definition, runtime, criteria)
        learner_text = ' '.join(t['text'] for t in session['turns'] if t['role'] == 'user').casefold()
        if isinstance(debrief, dict):
            # Model debriefs are accepted only when their quotes are the learner's own words.
            well, change = debrief.get('did_well') or {}, debrief.get('change') or {}
            if isinstance(well, dict) and isinstance(well.get('quote'), str) and well['quote'].strip() and well['quote'].casefold().strip(' .,!?') in learner_text and well.get('why'):
                quoted = well['quote'].casefold().strip(' .,!?')
                strengths = [f"You said “{well['quote']}”. {well['why']}"] + [item for item in strengths if quoted not in item.casefold()][:1]
            if isinstance(change, dict) and change.get('why') and change.get('better'):
                quote = change.get('quote') if isinstance(change.get('quote'), str) else ''
                if not quote or quote.casefold().strip(' .,!?') in learner_text:
                    improvements = [(f"You said “{quote}”. " if quote else '') + f"{change['why']} Try: “{change['better']}”"] + improvements[:1]
            if isinstance(debrief.get('try_next'), str) and debrief['try_next'].strip():
                next_step = debrief['try_next'].strip()[:300]
        for line in self._negotiation_review(definition, runtime):
            improvements.append(line)
        evidence = [f"{objectives[c['objective_id']]}: " + (' / '.join(c['quotes']) if c['met'] and c.get('quotes') else 'not shown yet') +
                    (f" ({c['support']})" if c['met'] else '') for c in criteria]
        evidence += [f"{name.replace('_', ' ')}: {reason}" for name, reason in rationales.items()]
        for check in evaluation.get('policy_check', []):
            evidence.append(f"Policy check: “{check['quote']}” {'agrees with' if check['supported'] else 'is not supported by'} the document. {check['reason']}".strip())
            if not check['supported']:
                improvements.insert(0, f"You said “{check['quote']}”, but the document does not support that. {check['reason']}".strip())
        evidence.append('Pronunciation, accent and vocal confidence are not assessed. These scores describe this practice, not a CEFR level or lasting mastery.')
        identifier = str(uuid.uuid4())
        feedback = ('You showed the objectives in this conversation. ' if runtime['completed'] else 'Practice saved. Some objectives are not demonstrated yet, which is normal at this stage. ') + next_step
        recorded = {**scores, **{key: value for key, value in subskills.items() if key not in scores}}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM assessments WHERE session_id=?', (session['id'],)).fetchone()
            if existing:
                return self._assessment_dict(existing)
            db.execute('INSERT INTO assessments VALUES (?,?,?,?,?,?,?,?,?)', (identifier, session['id'], overall, _json(scores), _json(strengths), _json(improvements), _json(evidence), feedback, _now()))
            db.execute("UPDATE sessions SET status='completed',completed_at=? WHERE id=?", (_now(), session['id']))
            for name, value in scores.items():
                db.execute('INSERT INTO assessment_metrics(id,assessment_id,skill_id,metric_name,score,rationale) VALUES (?,?,?,?,?,?)',
                           (str(uuid.uuid4()), identifier, session['skill_id'], name, value, rationales.get(name, 'Practice estimate')))
            if criteria:
                # An unfinished attempt is real evidence, but counts for less than a finished one.
                self.context.adaptive.update_proficiency(db, session, recorded, identifier, overall=overall, weight=.35 if runtime['completed'] else .15)
        return self.context.session.session(session['id'])['assessment']

    def game_tape(self, session_id):
        """Turn by turn: what the learner said, how the scene answered, and what the evidence shows.

        Built only from the assessed conversation, the review's quoted evidence and authored expert notes.
        Private limits and the characters' instructions are never included.
        """
        session = self.context.session.session(session_id)
        definition, state = self.context.runtime.read(session_id)
        if not state:
            return None
        evaluation = (state.get('completed_evaluation') if state.get('completed') else state.get('evaluation')) or state.get('last_evaluation') or {}
        objectives = {o['id']: o['description'] for o in definition['objectives']}
        notes = definition.get('expert_notes') or {}
        shown = {}
        for criterion in evaluation.get('criteria', []) + list((state.get('met_evidence') or {}).values()):
            if criterion.get('met'):
                for turn_id in criterion.get('turn_ids', []):
                    shown.setdefault(turn_id, set()).add(criterion['objective_id'])
        corrections = [c for c in evaluation.get('corrections', []) if isinstance(c, dict) and c.get('original') and c.get('improved')]
        with self.connect() as db:
            replayable = {row[0] for row in db.execute('SELECT turn_id FROM turn_snapshots WHERE session_id=?', (session_id,))}
            withdrawn = db.execute('SELECT COUNT(*) FROM withdrawn_turns WHERE session_id=? AND role=?', (session_id, 'user')).fetchone()[0]
        reaction_text = {'pleased': 'was pleased', 'encouraging': 'encouraged you', 'curious': 'wanted to know more', 'considering': 'thought it over',
                         'doubtful': 'pushed back', 'firm': 'held firm', 'puzzled': 'was puzzled', 'neutral': 'carried on'}
        tape = []
        for turn in session['turns']:
            item = {'id': turn['id'], 'role': turn['role'], 'speaker': 'You' if turn['role'] == 'user' else (turn.get('speaker_name') or session.get('counterpart')),
                    'text': turn['text'], 'at': turn.get('elapsed_seconds', 0), 'marks': []}
            if turn['role'] == 'user':
                for objective in sorted(shown.get(turn['id'], ())):
                    item['marks'].append({'kind': 'strong', 'text': f'Showed: {objectives.get(objective, objective)}'})
                lowered = ' '.join(turn['text'].casefold().split())
                for correction in corrections:
                    if ' '.join(correction['original'].casefold().split()) in lowered:
                        item['marks'].append({'kind': 'correction', 'text': f"Clearer: “{correction['improved']}”", 'original': correction['original']})
                reply = (state.get('turn_notes') or {}).get(str(turn['id']))
                if reply:
                    item['reaction'] = reply['reaction']
                    item['reaction_by'] = reply.get('speaker')
                    item['reaction_text'] = reaction_text[reply['reaction']]
                    if reply['reaction'] in {'doubtful', 'firm', 'puzzled'}:
                        item['marks'].append({'kind': 'missed', 'text': f"{reply.get('speaker') or 'They'} {reaction_text[reply['reaction']]} here. Worth another try."})
                item['replayable'] = turn['id'] in replayable
            tape.append(item)
        missing = [o for o in definition['objectives'] if not any(o['id'] in ids for ids in shown.values())]
        return {'turns': tape, 'rewinds': int(state.get('rewinds') or 0), 'withdrawn_turns': withdrawn, 'branch': state.get('branch'),
                'expert': [{'objective': o['description'], 'model': notes.get(o['id'], {}).get('model'), 'lesson': notes.get(o['id'], {}).get('micro_lesson')}
                           for o in missing if notes.get(o['id'], {}).get('model')]}

    @staticmethod
    def _negotiation_review(definition, runtime):
        """Point out what the offer record shows. Reservation limits are never revealed."""
        case = definition.get('negotiation')
        if not case:
            return []
        offers = runtime.get('offers', [])
        notes = []
        rules = case.get('feasibility', {})
        latest = rules.get('maximum_delivery_days', 45)
        if rules.get('late_delivery_saving') and not any(o['terms']['delivery_days'] >= latest for o in offers):
            notes.append(f'A trade you did not try: the supplier had spare capacity later on, so accepting delivery in {latest} days would have been worth something to them. Asking why they care about timing could have revealed that.')
        conditional = sum(bool(o['terms'].get('condition')) for o in offers)
        if len(offers) >= 2 and not conditional:
            notes.append('You changed your number without asking for anything in return. Next time, link each move to a condition: "If you can do X, I can do Y."')
        return notes

    def debrief_context(self, session):
        """A compact, private-limit-free view of the attempt for the debrief model."""
        definition = self.context.runtime.read(session['id'])[0]
        _, _, _, _, criteria, _ = self.scene_scores(session)
        met = {c['objective_id']: c for c in criteria}
        return {'lesson': session['title'], 'learner_role': definition['brief']['you_are'], 'facts': definition['facts'],
                'objectives': [{'description': o['description'], 'shown': bool(met.get(o['id'], {}).get('met')), 'quotes': met.get(o['id'], {}).get('quotes', []),
                                'what_good_looks_like': definition['expert_notes'][o['id']]['good'], 'common_mistakes': definition['expert_notes'][o['id']]['common_mistakes']}
                               for o in definition['objectives']],
                'learner_lines': [t['text'][:220] for t in session['turns'] if t['role'] == 'user'][-14:]}

    def assess_runtime(self, session):
        runtime = session['runtime']
        evaluation = (runtime.get('completed_evaluation') if runtime['completed'] else runtime.get('evaluation')) or runtime.get('last_evaluation') or {}
        criteria = evaluation.get('criteria', [])
        objectives = {o['id']: o['description'] for o in runtime['definition']['objectives']}
        demonstrated = [c for c in criteria if c['met']]
        strengths = [f"{objectives[c['objective_id']]}: {' / '.join(c['quotes'])} ({c['support']})" for c in demonstrated]
        improvements = [f"Practise {objectives[c['objective_id']]} with your own details." for c in criteria if not c['met'] or c['support'] != 'independent']
        if not criteria:
            improvements = ['Evidence review is unavailable. This attempt is retained without a proficiency judgment.']
        evidence = [f"{objectives[c['objective_id']]}: {' / '.join(c['quotes']) or 'Not demonstrated yet'}" for c in criteria]
        evidence += [f"{name.replace('_', ' ')}: {value.get('status', 'unassessed')}. {value.get('reason', '')}" for name, value in evaluation.get('dimensions', {}).items() if isinstance(value, dict)]
        improvements += [f"You said: {c['original']} A clearer option: {c['improved']}" for c in evaluation.get('corrections', [])]
        evidence.append('Pronunciation, accent and vocal confidence are unassessed. Completion does not establish lasting mastery or a CEFR level.')
        scores = {'task_achievement': round(100*len(demonstrated)/max(1,len(criteria)),1)} if criteria else {}
        overall = scores.get('task_achievement', 0)
        identifier = str(uuid.uuid4())
        feedback = 'Lesson objectives demonstrated. Choose a fresh case later to check transfer.' if runtime['completed'] else 'Practice saved. Independent achievement has not yet been demonstrated.'
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM assessments WHERE session_id=?', (session['id'],)).fetchone()
            if existing:
                return self._assessment_dict(existing)
            db.execute('INSERT INTO assessments VALUES (?,?,?,?,?,?,?,?,?)', (identifier,session['id'],overall,_json(scores),_json(strengths),_json(improvements),_json(evidence),feedback,_now()))
            db.execute("UPDATE sessions SET status='completed',completed_at=? WHERE id=?", (_now(),session['id']))
            if runtime['completed'] and scores:
                self.context.adaptive.update_proficiency(db,session,scores,identifier)
        return self.context.session.session(session['id'])['assessment']

    def _assessment_dict(self,row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in ("scores", "strengths", "improvements", "evidence"):
            result[key] = json.loads(result[key])
        result['unavailable_modalities'] = [name for name, metric in [('voice','delivery'),('visual','posture')] if metric not in result['scores']]
        result['unavailable_metrics'] = [name for name in ('grammar','fluency') if name not in result['scores']] if 'practice_completion' in result['scores'] else []
        with self.connect() as db:
            record=db.execute('SELECT scenario_snapshot_json FROM sessions WHERE id=?',(result['session_id'],)).fetchone()
            enabled=json.loads(record['scenario_snapshot_json'] or '{}').get('posture_enabled',False)
            samples=db.execute('SELECT COUNT(*) FROM posture WHERE session_id=?',(result['session_id'],)).fetchone()[0]
        result['visual_scores']={key:round(value,1) for key,value in zip(('slouching','head_position','shoulder_alignment','body_orientation'),self._posture_averages(result['session_id']))} if enabled and samples else {}
        result['posture_sample_count']=samples if enabled else 0
        if enabled:
            with self.connect() as db:
                series=[tuple(row) for row in db.execute('SELECT slouching,head_position,shoulder_alignment,body_orientation FROM posture WHERE session_id=? ORDER BY id',(result['session_id'],))]
            result['posture_summary']=summarise_posture(series)
        result['speech_signal']=self._speech_signal(result['session_id'])
        if result['visual_scores']:result['unavailable_modalities']=[name for name in result['unavailable_modalities'] if name!='visual']
        return result
