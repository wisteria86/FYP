"""ProgressService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService


class ProgressService(ApplicationService):
    def dashboard(self, user_id: str = "demo") -> dict[str, Any]:
        skills = self.context.catalog.skills(user_id)
        with self.connect() as db:
            user = db.execute("SELECT id,name,role,organization FROM users WHERE id=?", (user_id,)).fetchone()
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
            "strengths": ranked[:3] if practiced else [],
            "focus_areas": sorted(skills, key=lambda item: item["score"])[:2],
            "recommendation": recommendation,
            "plan": plan or self.context.adaptive.plan(skills),
            "persistent_plan": persistent_plan,
        }

    def history(self, user_id: str = "demo") -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT s.id,s.title,s.skill_id,s.difficulty,s.status,s.created_at,s.completed_at,a.overall FROM sessions s LEFT JOIN assessments a ON a.session_id=s.id WHERE s.user_id=? ORDER BY s.created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]
