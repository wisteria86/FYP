"""ProgressService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService


class ProgressService(ApplicationService):
    def dashboard(self, user_id: str = "demo") -> dict[str, Any]:
        skills = self.context.catalog.skills(user_id)
        with self.connect() as db:
            user = db.execute("SELECT id,name,email,role,organization FROM users WHERE id=?", (user_id,)).fetchone()
            if not user:
                raise ValueError("User not found")
            rows = db.execute("SELECT s.id,s.title,s.skill_id,s.completed_at,a.overall FROM sessions s LEFT JOIN assessments a ON a.session_id=s.id WHERE s.user_id=? AND s.status='completed' ORDER BY s.completed_at DESC LIMIT 8", (user_id,)).fetchall()
            practice_seconds = db.execute(
                """SELECT COALESCE(SUM(t.duration_seconds),0) total FROM turns t
                JOIN sessions s ON s.id=t.session_id WHERE s.user_id=? AND t.role='user'""",
                (user_id,),
            ).fetchone()["total"]
            history = db.execute(
                """SELECT s.id,s.completed_at,a.overall FROM sessions s
                JOIN assessments a ON a.session_id=s.id
                WHERE s.user_id=? ORDER BY s.completed_at""",
                (user_id,),
            ).fetchall()
        practiced = [s for s in skills if s["sessions"]]
        overall = round(sum(s["score"] for s in practiced) / len(practiced), 1) if practiced else 50.0
        weakest = min(skills, key=lambda s: s["score"])
        difficulty = "advanced" if weakest["score"] >= 80 else "intermediate" if weakest["score"] >= 60 else "beginner"
        completed_dates = sorted({r["completed_at"][:10] for r in rows if r["completed_at"]}, reverse=True)
        streak = 0
        if completed_dates:
            latest = datetime.fromisoformat(completed_dates[0]).date()
            for index, value in enumerate(completed_dates):
                if (latest - datetime.fromisoformat(value).date()).days == index:
                    streak += 1
                else:
                    break
        ranked = sorted(skills, key=lambda item: item["score"], reverse=True)
        persistent_plan = self.context.adaptive.persistent_plan(user_id)
        upcoming = [item for item in (persistent_plan or {}).get('activities', []) if item['status'] == 'upcoming']
        plan = [{'day': f'Session {index+1}', 'skill_id': item['primary_skill_id'],
                 'activity': item['title'], 'activity_id': item['activity_id'],
                 'difficulty': item['difficulty'],
                 'focus': item['reason'] or item['title']} for index,item in enumerate(upcoming)]
        recommendation = {'skill_id': weakest['id'],'skill':weakest['name'],'difficulty':difficulty,
                          'reason':f"Practise {weakest['name']} based on your current proficiency."}
        if upcoming:
            item=upcoming[0]
            recommendation.update(skill_id=item['primary_skill_id'],skill=item['title'],activity_id=item['activity_id'],
                difficulty='intermediate' if item['difficulty']=='adaptive' else item['difficulty'],reason=item['reason'])
        return {
            "user": dict(user),
            "overall": overall,
            "completed_sessions": sum(s["sessions"] for s in skills),
            "skills_in_progress": len(practiced),
            "practice_minutes": round(float(practice_seconds or 0) / 60, 1),
            "current_streak": streak,
            "skills": skills,
            "recent_sessions": [dict(r) for r in rows],
            "progress_history": [dict(r) for r in history],
            # Only evidence counts: a skill never practised is neither a strength nor a weakness.
            "strengths": [item for item in ranked if item["sessions"] and item["score"] >= 60][:3],
            "focus_areas": sorted((item for item in skills if item["sessions"] and item["score"] < 70), key=lambda item: item["score"])[:2],
            "recommendation": recommendation,
            "plan": plan or self.context.adaptive.plan(skills),
            "persistent_plan": persistent_plan,
            "learning_reviews": self.learning_reviews(user_id),
        }

    def goals(self, user_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT id,title,description,target_date,status,skill_id,created_at FROM user_goals WHERE user_id=? AND status='active' ORDER BY created_at", (user_id,))]

    def add_goal(self, user_id, title, skill_id=None, target_date=None):
        now = _now()
        goal_id = str(uuid.uuid4())
        with self.connect() as db:
            if skill_id and not db.execute('SELECT 1 FROM skill_catalog WHERE id=? AND active=1', (skill_id,)).fetchone():
                raise ValueError('Unknown skill')
            db.execute('INSERT INTO user_goals(id,user_id,title,target_date,skill_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?)', (goal_id, user_id, title.strip(), target_date, skill_id, now, now))
        return {'id': goal_id, 'title': title.strip(), 'skill_id': skill_id, 'target_date': target_date, 'status': 'active'}

    def close_goal(self, user_id, goal_id):
        with self.connect() as db:
            if not db.execute("UPDATE user_goals SET status='done',updated_at=? WHERE id=? AND user_id=?", (_now(), goal_id, user_id)).rowcount:
                raise ValueError('Goal not found')
        return {'id': goal_id, 'status': 'done'}

    def learning_reviews(self, user_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT r.*,a.title,a.primary_skill_id FROM learning_reviews r JOIN training_activities a ON a.id=r.activity_id WHERE r.user_id=? ORDER BY r.due_at', (user_id,))]

    def history(self, user_id: str = "demo") -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT s.id,s.title,s.skill_id,s.difficulty,s.status,s.created_at,s.completed_at,a.overall,json_extract(c.definition_json,'$.version') engine_version FROM sessions s LEFT JOIN assessments a ON a.session_id=s.id LEFT JOIN conversation_runtime c ON c.session_id=s.id WHERE s.user_id=? ORDER BY s.created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]
