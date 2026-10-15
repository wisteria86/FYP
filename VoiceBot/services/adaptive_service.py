"""AdaptiveTrainingService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService


class AdaptiveTrainingService(ApplicationService):
    def persistent_plan(self, user_id):
        with self.connect() as db:
            plan = db.execute("SELECT * FROM training_plans WHERE user_id=? AND status='active' ORDER BY updated_at DESC LIMIT 1", (user_id,)).fetchone()
            if not plan:
                return None
            activities = db.execute('''SELECT p.*,a.title,a.primary_skill_id,a.difficulty,r.reason,r.source_assessment_id FROM training_plan_activities p
                JOIN training_activities a ON a.id=p.activity_id LEFT JOIN recommendations r ON r.id=p.id
                WHERE p.plan_id=? ORDER BY p.position''', (plan['id'],)).fetchall()
        return {**dict(plan), 'activities': [dict(row) for row in activities]}

    @staticmethod
    def plan(skills: list[dict[str, Any]]) -> list[dict[str, str]]:
        chosen = sorted(skills, key=lambda x: (x["score"], x["sessions"]))[:3]
        return [{"day": f"Session {i + 1}", "skill_id": s["id"], "activity": s["name"], "focus": s["subskills"][i % len(s["subskills"])] if s['subskills'] else s['name']} for i, s in enumerate(chosen)]

    def update_proficiency(self, db, session, scores, assessment_id):
        user_id, skill_id = session['user_id'], session['skill_id']
        overall = round(sum(scores.values()) / len(scores), 1)
        current = db.execute('SELECT score,sessions FROM proficiency WHERE user_id=? AND skill_id=?', (user_id, skill_id)).fetchone()
        previous, count = (current['score'], current['sessions']) if current else (50, 0)
        updated = round(previous * .65 + overall * .35, 1) if count else overall
        db.execute('INSERT INTO proficiency VALUES (?,?,?,?,?) ON CONFLICT(user_id,skill_id) DO UPDATE SET score=excluded.score,sessions=excluded.sessions,updated_at=excluded.updated_at', (user_id, skill_id, updated, count + 1, _now()))
        db.execute('INSERT INTO proficiency_history(user_id,skill_id,session_id,previous_score,observed_score,new_score,created_at) VALUES (?,?,?,?,?,?,?)', (user_id,skill_id,session['id'],previous,overall,updated,_now()))
        subskills = db.execute('SELECT id,name FROM subskill_catalog WHERE skill_id=? AND active=1 ORDER BY rowid', (skill_id,)).fetchall()
        for sub in subskills:
            metric = sub['name'].lower().replace(' ', '_')
            if metric not in scores:
                # Preserve unmeasured subskills rather than cycling unrelated
                # aggregate metrics into invented per-subskill observations.
                continue
            current = db.execute('SELECT score,sessions FROM subskill_proficiency WHERE user_id=? AND skill_id=? AND subskill=?', (user_id,skill_id,sub['name'])).fetchone()
            prior, count = (current['score'],current['sessions']) if current else (50,0)
            observed = scores[metric]
            updated = round(prior*.65+observed*.35,1) if count else observed
            db.execute('INSERT INTO subskill_proficiency VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,skill_id,subskill) DO UPDATE SET score=excluded.score,sessions=excluded.sessions,updated_at=excluded.updated_at', (user_id,skill_id,sub['name'],updated,count+1,_now()))
            db.execute('INSERT INTO proficiency_history(user_id,skill_id,subskill_id,session_id,previous_score,observed_score,new_score,created_at) VALUES (?,?,?,?,?,?,?,?)', (user_id,skill_id,sub['id'],session['id'],prior,observed,updated,_now()))
        self.update_training_plan(db, user_id, assessment_id, session)

    def update_training_plan(self, db, user_id, assessment_id, session):
        plan_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'hikari-plan:'+user_id))
        now = _now()
        db.execute("INSERT INTO training_plans(id,user_id,title,generated_reason,created_at,updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,status='active'", (plan_id,user_id,'Personalized workplace training','Based on assessed skill and subskill proficiency',now,now))
        db.execute("UPDATE recommendations SET status='completed' WHERE user_id=? AND activity_id=? AND status='active'", (user_id,session.get('activity_id')))
        db.execute("UPDATE training_plan_activities SET status='completed',session_id=? WHERE plan_id=? AND activity_id=? AND status='upcoming'", (session['id'],plan_id,session.get('activity_id')))
        db.execute("UPDATE recommendations SET status='superseded' WHERE user_id=? AND status='active'", (user_id,))
        db.execute("UPDATE training_plan_activities SET status='superseded' WHERE plan_id=? AND status='upcoming'", (plan_id,))
        weakest = db.execute('SELECT s.id,s.name,COALESCE(p.score,50) score FROM skill_catalog s LEFT JOIN proficiency p ON p.skill_id=s.id AND p.user_id=? WHERE s.active=1 ORDER BY (s.id=?) DESC,score,s.id LIMIT 3', (user_id,session['skill_id'])).fetchall()
        for priority, skill in enumerate(weakest):
            activity = db.execute('''SELECT a.id FROM training_activities a WHERE a.primary_skill_id=? AND a.active=1
                AND (a.training_language IS NULL OR NOT EXISTS (SELECT 1 FROM sessions s JOIN assessments x ON x.session_id=s.id
                    WHERE s.user_id=? AND s.activity_id=a.id AND s.status='completed' AND x.overall>=60))
                ORDER BY COALESCE(a.sequence_number,999),a.title LIMIT 1''', (skill['id'],user_id)).fetchone()
            if not activity:
                continue
            reason = f"Practise {skill['name']}: your current prototype score is {skill['score']:.0f}/100. Build on the feedback from your last activity."
            rid = str(uuid.uuid5(uuid.NAMESPACE_URL, assessment_id+activity['id']))
            db.execute('INSERT INTO recommendations(id,user_id,activity_id,reason,priority,source_assessment_id,created_at) VALUES (?,?,?,?,?,?,?)', (rid,user_id,activity['id'],reason,3-priority,assessment_id,now))
            db.execute('INSERT INTO training_plan_activities(id,plan_id,activity_id,position) VALUES (?,?,?,?)', (rid,plan_id,activity['id'],priority))
