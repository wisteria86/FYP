"""CatalogService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words, _slug
from services.service_context import ApplicationService


class CatalogService(ApplicationService):
    def _initialize(self) -> None:
        run_migrations(self.path)
        with self.connect() as db:
            now = _now()
            db.execute(
                "INSERT OR IGNORE INTO users(id,name,role,organization,created_at) VALUES (?, ?, ?, ?, ?)",
                ("demo", "Demo Learner", "Employee", "Hikari Demo", now),
            )
            for skill_id, *_ in SKILLS:
                db.execute(
                    "INSERT OR IGNORE INTO proficiency VALUES (?, ?, ?, 0, ?)",
                    ("demo", skill_id, 50.0, _now()),
                )
            for skill_id, _, _, subskills in SKILLS:
                for subskill in subskills:
                    db.execute("INSERT OR IGNORE INTO subskill_proficiency VALUES (?,?,?,50,0,?)", ("demo", skill_id, subskill, _now()))
            self._seed_platform_catalog(db, now)

    @staticmethod
    def _seed_platform_catalog(db: sqlite3.Connection, now: str) -> None:
        """Seed catalog records while legacy API tables remain available."""

        db.execute(
            "INSERT OR IGNORE INTO organizations(id,name,slug,created_at,updated_at) VALUES (?,?,?,?,?)",
            ("hikari-demo", "Hikari Demo", "hikari-demo", now, now),
        )
        db.execute(
            "INSERT OR IGNORE INTO organization_memberships VALUES (?,?,?,?)",
            ("hikari-demo", "demo", "learner", now),
        )
        db.execute(
            "INSERT OR IGNORE INTO user_settings(user_id,updated_at) VALUES (?,?)",
            ("demo", now),
        )
        for skill_id, name, description, subskills in SKILLS:
            db.execute(
                "INSERT OR IGNORE INTO skill_catalog(id,name,description,created_at,updated_at) VALUES (?,?,?,?,?)",
                (skill_id, name, description, now, now),
            )
            subskill_ids = []
            for subskill in subskills:
                subskill_id = f"{skill_id}:{_slug(subskill)}"
                subskill_ids.append(subskill_id)
                db.execute(
                    "INSERT OR IGNORE INTO subskill_catalog(id,skill_id,name) VALUES (?,?,?)",
                    (subskill_id, skill_id, subskill),
                )
            if skill_id == "english-speaking":
                continue
            title, situation, counterpart, objectives = SCENARIOS[skill_id]
            activity_id = f"activity-{skill_id}"
            scenario_type = "multi_ai_roleplay" if skill_id in MULTI_AI_SKILLS else "roleplay"
            mode = "ai_team_vs_learner" if skill_id in MULTI_AI_SKILLS else "one_to_one"
            db.execute(
                """INSERT OR IGNORE INTO training_activities(
                    id,title,description,primary_skill_id,scenario_type,difficulty,
                    estimated_minutes,created_at,updated_at,posture_mode,knowledge_mode
                ) VALUES (?,?,?,?,?,'adaptive',15,?,?,?,?)""",
                (activity_id, title, description, skill_id, scenario_type, now, now,
                 'optional' if skill_id in {'presentations','interviews'} else 'off',
                 'required' if skill_id=='company-knowledge' else 'optional'),
            )
            # Keep seeded catalogs current for databases created by an earlier
            # prototype version where every activity was labelled "roleplay".
            db.execute(
                "UPDATE training_activities SET scenario_type=?,roleplay_mode=?,updated_at=? WHERE id=?",
                (scenario_type, mode, now, activity_id),
            )
            for subskill_id in subskill_ids:
                db.execute(
                    "INSERT OR IGNORE INTO activity_subskills(activity_id,subskill_id,weight) VALUES (?,?,1)",
                    (activity_id, subskill_id),
                )
            participants = [
                {"type": "learner", "role": "Learner"},
                *[
                    {"type": "ai", "role": role, "displayName": role}
                    for role in SCENARIO_PARTICIPANTS.get(skill_id, [counterpart])
                ],
            ]
            rubric = {
                "skillId": skill_id,
                "subskills": subskills,
                "requiresTranscriptEvidence": True,
            }
            db.execute(
                """INSERT OR IGNORE INTO scenario_templates(
                    id,activity_id,learner_role,context,objectives_json,success_criteria_json,
                    opening_situation,participants_json,rubric_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"template-{skill_id}", activity_id, "Learner", situation,
                    _json(objectives), _json(objectives), SCENARIO_OPENINGS[skill_id],
                    _json(participants), _json(rubric), now, now,
                ),
            )
            db.execute(
                "UPDATE scenario_templates SET participants_json=?,updated_at=? WHERE id=? AND version=1",
                (_json(participants), now, f"template-{skill_id}"),
            )
        CatalogService._seed_english_curriculum(db, now)
        resources = [
            ("resource-communication-guide", "Professional Communication Guide", "Communicate clearly and professionally in workplace situations.", "guide", "communication"),
            ("resource-interview-checklist", "Interview Preparation Checklist", "A practical checklist for structured, relevant interview answers.", "checklist", "interviews"),
            ("resource-negotiation-playbook", "Negotiation Playbook", "Discovery questions, trade-offs, concessions, and closing techniques.", "guide", "negotiation"),
            ("resource-presentation-tips", "Presentation Skills Tips", "Plan concise presentations with a strong opening and clear decision.", "video", "presentations"),
            ("resource-difficult-conversations", "Difficult Conversations Guide", "De-escalate tension while protecting relationships and outcomes.", "guide", "conflict-resolution"),
            ("resource-ai-literacy", "AI Literacy Basics", "Verify AI output and handle private information responsibly.", "article", "ai-literacy"),
            ("resource-follow-up", "Follow-Up Email Templates", "Reusable structures for professional summaries and next steps.", "template", "communication"),
        ]
        for resource_id, title, description, resource_type, skill_id in resources:
            db.execute(
                """INSERT OR IGNORE INTO resources(
                    id,title,description,resource_type,content_text,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?)""",
                (resource_id, title, description, resource_type, description, now, now),
            )
            db.execute(
                "INSERT OR IGNORE INTO resource_skill_links(resource_id,skill_id,subskill_id) VALUES (?,?,?)",
                (resource_id, skill_id, None),
            )

    @staticmethod
    def _seed_english_curriculum(db: sqlite3.Connection, now: str) -> None:
        subskill_ids = [
            row["id"] for row in db.execute(
                "SELECT id FROM subskill_catalog WHERE skill_id='english-speaking' ORDER BY id"
            )
        ]
        for sequence, title, level, description, counterpart, objectives, opening in ENGLISH_CURRICULUM:
            activity_id = f"english-{sequence:02d}"
            mode = roleplay_mode(sequence)
            scenario_type = "multi_ai_roleplay" if mode != "one_to_one" else "roleplay"
            db.execute(
                """INSERT OR IGNORE INTO training_activities(
                    id,title,description,primary_skill_id,scenario_type,difficulty,
                    estimated_minutes,guided_mode,training_language,proficiency_level,
                    sequence_number,roleplay_mode,created_at,updated_at
                ) VALUES (?,?,?,'english-speaking',?,?,15,1,'English',?,?,?,?,?)""",
                (activity_id, title, description, scenario_type, level, level, sequence, mode, now, now),
            )
            db.execute(
                """UPDATE training_activities SET title=?,description=?,scenario_type=?,difficulty=?,
                    training_language='English',proficiency_level=?,sequence_number=?,roleplay_mode=?,updated_at=?
                    WHERE id=?""",
                (title, description, scenario_type, level, level, sequence, mode, now, activity_id),
            )
            for subskill_id in subskill_ids:
                db.execute(
                    "INSERT OR IGNORE INTO activity_subskills(activity_id,subskill_id,weight) VALUES (?,?,1)",
                    (activity_id, subskill_id),
                )
            people = english_participants(sequence, counterpart)
            context = description
            db.execute(
                """INSERT OR IGNORE INTO scenario_templates(
                    id,activity_id,learner_role,context,objectives_json,success_criteria_json,
                    opening_situation,participants_json,variables_json,rubric_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"template-{activity_id}", activity_id, "English learner", context,
                    _json(objectives), _json(objectives), opening, _json(people),
                    _json({"targetLanguage": "English", "level": level, "roleplayMode": mode,
                           "learningDesign": learning_design(sequence)}),
                    _json({"skillId": "english-speaking", "subskills": ["fluency", "vocabulary", "grammar", "comprehension"]}),
                    now, now,
                ),
            )
            db.execute(
                """UPDATE scenario_templates SET context=?,objectives_json=?,success_criteria_json=?,
                    opening_situation=?,participants_json=?,variables_json=?,updated_at=? WHERE id=? AND version=1""",
                (
                    context, _json(objectives), _json(objectives), opening, _json(people),
                    _json({"targetLanguage": "English", "level": level, "roleplayMode": mode,
                           "learningDesign": learning_design(sequence)}),
                    now, f"template-{activity_id}",
                ),
            )

    def skills(self, user_id: str = "demo") -> list[dict[str, Any]]:
        with self.connect() as db:
            values = {r["skill_id"]: dict(r) for r in db.execute("SELECT * FROM proficiency WHERE user_id=?", (user_id,))}
            subvalues = {(r["skill_id"], r["subskill"]): r["score"] for r in db.execute("SELECT * FROM subskill_proficiency WHERE user_id=?", (user_id,))}
            catalog = [(row['id'], row['name'], row['description'],
                        [s['name'] for s in db.execute('SELECT name FROM subskill_catalog WHERE skill_id=? AND active=1', (row['id'],))])
                       for row in db.execute('SELECT * FROM skill_catalog WHERE active=1 ORDER BY rowid')]
        return [
            {"id": sid, "name": name, "description": desc, "subskills": subskills,
             "subskill_scores": {sub: round(subvalues.get((sid, sub), 50), 1) for sub in subskills},
             "score": round(values.get(sid, {}).get("score", 50), 1), "sessions": values.get(sid, {}).get("sessions", 0)}
            for sid, name, desc, subskills in catalog
        ]

    def _activity(self, db: sqlite3.Connection, skill_id: str, activity_id: str | None = None) -> sqlite3.Row:
        query = """SELECT a.*,t.learner_role,t.context,t.objectives_json,t.success_criteria_json,t.opening_situation,
            t.participants_json,t.variables_json,s.name skill_name
            FROM training_activities a
            JOIN skill_catalog s ON s.id=a.primary_skill_id
            JOIN scenario_templates t ON t.activity_id=a.id AND t.active=1
            WHERE a.active=1 AND a.primary_skill_id=?"""
        params: list[Any] = [skill_id]
        if activity_id:
            query += " AND a.id=?"
            params.append(activity_id)
        query += " ORDER BY COALESCE(a.sequence_number,999),a.title LIMIT 1"
        row = db.execute(query, params).fetchone()
        if not row:
            raise ValueError("Training activity not found")
        return row

    def activities(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT a.*,s.name skill_name FROM training_activities a
                JOIN skill_catalog s ON s.id=a.primary_skill_id
                WHERE a.active=1 ORDER BY
                CASE WHEN a.training_language IS NULL THEN 1 ELSE 0 END,
                a.training_language,COALESCE(a.sequence_number,999),a.title"""
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["subskills"] = [
                    value["name"] for value in db.execute(
                        """SELECT s.name FROM activity_subskills x
                        JOIN subskill_catalog s ON s.id=x.subskill_id
                        WHERE x.activity_id=? ORDER BY s.name""",
                        (row["id"],),
                    )
                ]
                result.append(item)
        return result

    def resources(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT r.id,r.title,r.description,r.resource_type,r.content_text,
                GROUP_CONCAT(s.name, ', ') skills
                FROM resources r
                LEFT JOIN resource_skill_links x ON x.resource_id=r.id
                LEFT JOIN skill_catalog s ON s.id=x.skill_id
                WHERE r.active=1 GROUP BY r.id ORDER BY r.title"""
            ).fetchall()
        return [dict(row) for row in rows]
