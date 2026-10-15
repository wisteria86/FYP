"""AssessmentService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService
from domain.entities import Assessment, AssessmentMetric
from intelligence.speech_analysis import TranscriptSpeechAnalysis
from intelligence.learning_rubrics import fallback_scores, valid_scores


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

    def _posture_averages(self,session_id):
        with self.connect() as db:
            return tuple(db.execute('SELECT AVG(slouching),AVG(head_position),AVG(shoulder_alignment),AVG(body_orientation) FROM posture WHERE session_id=?',(session_id,)).fetchone())

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
        if result['visual_scores']:result['unavailable_modalities']=[name for name in result['unavailable_modalities'] if name!='visual']
        return result
