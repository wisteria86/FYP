"""SessionService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService
from intelligence.learning_rubrics import distinct_turns, workplace_targets, observe
from domain.entities import TrainingSession, SessionStatus


class SessionService(ApplicationService):
    def create_session(self, user_id: str, skill_id: str, difficulty: str, activity_id: str | None = None,
                       preview_id: str | None = None, document_ids: list[str] | None = None, posture_enabled: bool = False) -> dict[str, Any]:
        if preview_id:
            with self.connect() as db:
                preview=db.execute('SELECT * FROM scenario_previews WHERE id=? AND user_id=? AND used=0',(preview_id,user_id)).fetchone()
            if not preview:raise ValueError('This briefing is unavailable or has already been used')
            runtime=json.loads(preview['snapshot_json'])
            if runtime['skill_id']!=skill_id or activity_id and runtime['activity_id']!=activity_id:raise ValueError('Briefing does not match the selected lesson')
            if (datetime.now(timezone.utc)-datetime.fromisoformat(preview['created_at'])).total_seconds()>1800:raise ValueError('Briefing expired; prepare this lesson again')
        else:
            runtime=self.context.scenario.scenario_preview(user_id,skill_id,difficulty,activity_id,document_ids,posture_enabled)
        if runtime.get('document_ids'):
            ready={doc['id'] for doc in self.context.knowledge.documents(user_id) if doc['status']=='ready'}
            if not set(runtime['document_ids']).issubset(ready):
                raise ValueError('Selected documents are no longer available; prepare the lesson again')
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM skill_catalog WHERE id=? AND active=1', (skill_id,)).fetchone():
                raise ValueError('Unknown skill')
            if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                raise ValueError("Unknown user")
            activity = self.context.catalog._activity(db, skill_id, activity_id)
        difficulty = activity["proficiency_level"] or (difficulty if difficulty in {"beginner", "intermediate", "advanced"} else "intermediate")
        title = activity["title"]
        situation = runtime['situation']
        objectives = runtime['objectives']
        participant_specs = runtime['participant_specs']
        ai_specs = [person for person in participant_specs if person.get("type") == "ai"]
        opening_speaker = next((person for person in ai_specs if person.get("team") == "opponent"), ai_specs[0] if ai_specs else {})
        counterpart = (opening_speaker.get("displayName") or opening_speaker.get("role")) if opening_speaker else "Conversation partner"
        sid = str(uuid.uuid4())
        opening_text = runtime['opening']
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('UPDATE scenario_previews SET used=1 WHERE id=? AND used=0',(runtime['preview_id'],)).rowcount:raise ValueError('Briefing has already been used')
            db.execute(
                """INSERT INTO sessions(
                    id,user_id,skill_id,difficulty,title,situation,counterpart,objectives,
                    status,created_at,completed_at,activity_id
                ) VALUES (?,?,?,?,?,?,?,?,'active',?,NULL,?)""",
                (sid, user_id, skill_id, difficulty, title, situation, counterpart, _json(objectives), _now(), activity["id"]),
            )
            db.execute('UPDATE sessions SET scenario_snapshot_json=? WHERE id=?',(_json(runtime),sid))
            db.execute(
                """INSERT INTO turns(session_id,role,text,duration_seconds,created_at,speaker_name)
                VALUES (?,?,?,?,?,?)""",
                (sid, "assistant", opening_text, 0, _now(), counterpart),
            )
            for index, person in enumerate(participant_specs):
                display_name = person.get("displayName") or ("You" if person.get("type") == "learner" else person.get("role", "AI"))
                db.execute(
                    """INSERT INTO training_session_participants(
                        id,session_id,participant_type,display_name,scenario_role,position,configuration_json
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (
                        str(uuid.uuid4()), sid, person.get("type", "ai"), display_name,
                        person.get("role", display_name), index, _json({"team": person.get("team", "participant")}),
                    ),
                )
        return self.session(sid)

    def session(self, session_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Session not found")
            result = dict(row)
            result["objectives"] = json.loads(result["objectives"])
            result["turns"] = [dict(r) for r in db.execute(
                "SELECT role,text,duration_seconds,created_at,speaker_name,caption_text FROM turns WHERE session_id=? ORDER BY id",
                (session_id,),
            )]
            activity = db.execute(
                """SELECT a.training_language,a.proficiency_level,a.sequence_number,a.roleplay_mode,
                a.scenario_type,t.variables_json FROM training_activities a
                LEFT JOIN scenario_templates t ON t.activity_id=a.id AND t.active=1 WHERE a.id=?""",
                (result.get("activity_id"),),
            ).fetchone()
            if activity:
                result.update(dict(activity))
                variables = json.loads(result.pop("variables_json") or "{}")
                result["learning_design"] = variables.get("learningDesign")
            snapshot=json.loads(result.pop('scenario_snapshot_json',None) or '{}')
            result['success_criteria']=snapshot.get('success_criteria',result['objectives'])
            result['completion_review']=snapshot.get('completion_review')
            if snapshot:
                for key in ('title','description','situation','objectives','learning_design','difficulty','roleplay_mode','scenario_type','training_language','sequence_number','posture_mode','posture_enabled','knowledge_mode','document_ids','knowledge_evidence','adaptation_reason','previous_feedback'):
                    if key in snapshot:result[key]=snapshot[key]
            else:
                result.update(posture_mode='off',posture_enabled=False,knowledge_mode='off',document_ids=[])
            participants = [dict(r) for r in db.execute(
                """SELECT id,participant_type,display_name,scenario_role,position,configuration_json
                FROM training_session_participants WHERE session_id=? ORDER BY position""",
                (session_id,),
            )]
            if not participants:
                participants = [
                    {"participant_type": "learner", "display_name": "You", "scenario_role": "Learner", "position": 0},
                    *[
                        {"participant_type": "ai", "display_name": role, "scenario_role": role, "position": index}
                        for index, role in enumerate(SCENARIO_PARTICIPANTS.get(result["skill_id"], [result["counterpart"]]), start=1)
                    ],
                ]
            result["participants"] = participants
            with_times=result['turns']
            created=datetime.fromisoformat(result['created_at'])
            for turn in with_times:turn['elapsed_seconds']=max(0,int((datetime.fromisoformat(turn['created_at'])-created).total_seconds()))
            assessment = db.execute("SELECT * FROM assessments WHERE session_id=?", (session_id,)).fetchone()
            result["assessment"] = self.context.assessment._assessment_dict(assessment) if assessment else None
            return result

    def add_turn(self, session_id: str, role: str, text: str, duration_seconds: float = 0,
                 speaker_name: str | None = None, caption_text: str | None = None) -> None:
        if role not in {"user", "assistant"} or not text.strip():
            raise ValueError("Invalid turn")
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sessions WHERE id=? AND status='active'", (session_id,)).fetchone():
                raise ValueError("Active session not found")
            db.execute(
                """INSERT INTO turns(session_id,role,text,duration_seconds,created_at,speaker_name,caption_text)
                VALUES (?,?,?,?,?,?,?)""",
                (session_id, role, text.strip(), max(0, duration_seconds), _now(), speaker_name, caption_text),
            )

    def response_speakers(self, session_id: str) -> list[dict[str, str]]:
        session = self.session(session_id)
        ai_people = [person for person in session["participants"] if person["participant_type"] == "ai"]
        mode = session.get("roleplay_mode", "one_to_one")
        if mode == "one_to_one":
            ai_people = ai_people[:1]
        elif mode in {"round_robin", "ai_team_vs_learner"} and ai_people:
            user_turns = sum(1 for turn in session["turns"] if turn["role"] == "user")
            ai_people = [ai_people[user_turns % len(ai_people)]]
        return [
            {
                "name": person["display_name"],
                "role": person["scenario_role"],
                "team": json.loads(person.get("configuration_json") or "{}").get("team", "participant"),
            }
            for person in ai_people
        ]

    def evaluate_progress(self, session_id: str) -> dict[str, Any]:
        """Return a deterministic live outcome. Failure means keep practising; success completes."""
        session = self.session(session_id)
        user_turns = [turn["text"].strip() for turn in session["turns"] if turn["role"] == "user"]
        level = session.get("proficiency_level") or session["difficulty"]
        design = session.get("learning_design") or {}
        minimum_turns = int(design.get("minimum_turns") or {"beginner": 3, "intermediate": 4, "advanced": 5}.get(level, 4))
        word_target = int(design.get("word_target") or {"beginner": 12, "intermediate": 28, "advanced": 45}.get(level, 28))
        valid_turns = distinct_turns(user_turns)
        word_count = len(_words(' '.join(valid_turns)))
        targets = design.get('targets') or workplace_targets(session['skill_id'], session['objectives'])
        if not design and session.get('success_criteria',session['objectives'])!=session['objectives']:
            targets=workplace_targets('__custom__',session['success_criteria'])
        criteria = [observe(target, valid_turns) for target in targets]
        if session['skill_id']=='company-knowledge':
            criteria=self.context.knowledge.policy_observations(session,valid_turns)
        review=session.get('completion_review') or {}
        semantic = (session['skill_id']!='company-knowledge' and
                    review.get('user_turn_count')==len(user_turns) and
                    {item['name'] for item in criteria}=={item['name'] for item in review.get('criteria',[])})
        if semantic:
            by_name={item['name']:item for item in review['criteria']}
            criteria=[by_name[item['name']] for item in criteria]
        # Counts are practice guidance, not a reason to reject a complete answer.
        # Replaying the same answer cannot manufacture additional evidence.
        repeated_only = not semantic and len(user_turns) > 1 and len(valid_turns) == 1
        criteria_met = bool(criteria) and all(item["met"] for item in criteria)
        success = bool(valid_turns) and criteria_met and not repeated_only
        missing = [item["name"] for item in criteria if not item["met"]]
        if repeated_only and criteria_met:
            missing.append('Apply these skills in a new reply rather than repeating the same answer')
        progress = min(99 if not success else 100, round(
            sum(item['met'] for item in criteria) / max(1, len(criteria)) * 100))
        return {
            "outcome": "success" if success else "failure",
            "continue_session": not success,
            "progress_percent": progress,
            "meaningful_turns": len(valid_turns),
            "minimum_turns": minimum_turns,
            "word_count": word_count,
            "word_target": word_target,
            "criteria": criteria,
            "missing": missing,
            "learning_focus": design.get("focus"),
            "examples": design.get("examples", []),
            "evaluation_mode": 'meaning-based review' if semantic else 'rule-based fallback',
        }

    def completion_review_prompt(self, session_id: str) -> str:
        session=self.session(session_id)
        progress=self.evaluate_progress(session_id)
        # Role labels distinguish learner evidence from questions/model answers.
        turns=[{'role':t['role'],'speaker':t.get('speaker_name'),'text':t['text']} for t in session['turns']]
        return _json({'lesson':session['title'],'situation':session['situation'],
                      'objectives':session['objectives'],'criteria':[c['name'] for c in progress['criteria']],
                      'transcript':turns})

    def save_completion_review(self, session_id: str, review: dict, user_turn_count: int) -> bool:
        """Validate an advisory model decision before making it authoritative.

        Bind it to this learner-turn revision, require the whole rubric, and
        reject invented/assistant-only evidence. Source-policy rules stay local.
        """
        if not isinstance(review,dict) or not isinstance(review.get('criteria'),list):return False
        session=self.session(session_id)
        if session['skill_id']=='company-knowledge' or session['status']!='active':return False
        turns=[t['text'] for t in session['turns'] if t['role']=='user']
        if len(turns)!=user_turn_count:return False
        expected={c['name'] for c in self.evaluate_progress(session_id)['criteria']}
        clean=[];seen=set()
        normalize=lambda text:' '.join(text.casefold().split())
        for item in review['criteria']:
            if not isinstance(item,dict):return False
            name=item.get('name');met=item.get('met');quotes=item.get('evidence')
            if not isinstance(name,str) or name not in expected or name in seen or type(met) is not bool or not isinstance(quotes,list):return False
            seen.add(name)
            if any(not isinstance(q,str) or len(q.strip())<2 or not any(normalize(q) in normalize(t) for t in turns) for q in quotes):return False
            if met and not quotes:return False
            clean.append({'name':name,'met':met,'evidence':quotes[:3],'source':'semantic'})
        if seen!=expected or not expected:return False
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT scenario_snapshot_json FROM sessions WHERE id=? AND status='active'",(session_id,)).fetchone()
            count=db.execute("SELECT COUNT(*) FROM turns WHERE session_id=? AND role='user'",(session_id,)).fetchone()[0]
            if not row or count!=user_turn_count:return False
            snapshot=json.loads(row[0] or '{}')
            snapshot['completion_review']={'user_turn_count':count,'criteria':clean}
            db.execute('UPDATE sessions SET scenario_snapshot_json=? WHERE id=?',(_json(snapshot),session_id))
        return True

    def caption_preferences(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        with self.connect() as db:
            row = db.execute(
                "SELECT native_language,captions_enabled FROM user_settings WHERE user_id=?",
                (session["user_id"],),
            ).fetchone()
        native = row["native_language"] if row else "Urdu"
        return {
            "enabled": bool(row["captions_enabled"]) if row else True,
            "language": native,
            "translate": bool(
                session.get("training_language") == "English"
                and session.get("proficiency_level") == "beginner"
                and native != "English"
            ),
        }

    def set_opening_caption(self, session_id: str, caption_text: str) -> None:
        with self.connect() as db:
            db.execute(
                """UPDATE turns SET caption_text=? WHERE id=(
                    SELECT id FROM turns WHERE session_id=? AND role='assistant' ORDER BY id LIMIT 1
                )""",
                (caption_text.strip(), session_id),
            )

    def add_posture(self, session_id: str, values: dict[str, float]) -> None:
        if not self.session(session_id).get('posture_enabled'):raise ValueError('Posture assessment is disabled for this lesson/session')
        scores = [max(0, min(100, float(values.get(k, 0)))) for k in ("slouching", "head_position", "shoulder_alignment", "body_orientation")]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute("SELECT 1 FROM sessions WHERE id=? AND status='active'", (session_id,)).fetchone():
                raise ValueError('Posture can only be recorded for an active session')
            db.execute("INSERT INTO posture(session_id,slouching,head_position,shoulder_alignment,body_orientation,created_at) VALUES (?,?,?,?,?,?)", (session_id, *scores, _now()))

    def cancel_session(self, session_id):
        current = self.session(session_id)
        entity = TrainingSession(current['id'], current['user_id'], current.get('activity_id') or '', SessionStatus(current['status']))
        entity.cancel()
        with self.connect() as db:
            changed = db.execute("UPDATE sessions SET status=?,completed_at=? WHERE id=? AND status='active'",
                                 (entity.status.value, entity.completion_time, session_id)).rowcount
            if not changed:
                raise ValueError('Session is no longer active')
        return self.session(session_id)
