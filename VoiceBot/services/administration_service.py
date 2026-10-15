"""Authorized catalog administration without coupling it to user progress."""
import json
import re
from config import Config
from domain.errors import DomainError
from services.service_context import ApplicationService
from services.training_support import _now


class AdministrationService(ApplicationService):
    def catalog(self,user):
        self.authorize(user)
        with self.connect() as db:
            return {name:[dict(row) for row in db.execute('SELECT * FROM '+table)] for name,table in
                    [('skills','skill_catalog'),('subskills','subskill_catalog'),('activities','training_activities'),('scenarios','scenario_templates')]}
    def save_subskill(self, user, identifier, data):
        self.authorize(user)
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM skill_catalog WHERE id=?',(data['skill_id'],)).fetchone():
                raise DomainError('skill_not_found','Skill not found',status_code=404)
            db.execute('''INSERT INTO subskill_catalog(id,skill_id,name,description,active) VALUES (?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description,active=excluded.active''',
                (identifier,data['skill_id'],data['name'],data['description'],int(data['active'])))
        return {'id':identifier,**data}

    def save_activity(self, user, identifier, data):
        self.authorize(user)
        now=_now()
        people=[{'type':'learner','role':data['learner_role']}]+[{'type':'ai','role':role,'displayName':role} for role in data['ai_roles']]
        mode=data['roleplay_mode']
        if (mode=='one_to_one') != (len(data['ai_roles'])==1):
            raise DomainError('invalid_participants','One-to-one needs exactly one AI; team modes need multiple AI',status_code=422)
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM skill_catalog WHERE id=?',(data['skill_id'],)).fetchone():
                raise DomainError('skill_not_found','Skill not found',status_code=404)
            if db.execute('SELECT 1 FROM training_activities WHERE id=?',(identifier,)).fetchone():
                raise DomainError('activity_exists','Use a new activity identifier; edit existing scenario templates separately',status_code=409)
            db.execute('''INSERT INTO training_activities(id,title,description,primary_skill_id,scenario_type,difficulty,
                estimated_minutes,roleplay_mode,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (identifier,data['title'],data['description'],data['skill_id'],'roleplay' if mode=='one_to_one' else 'multi_ai_roleplay',data['difficulty'],data['estimated_minutes'],mode,now,now))
            db.execute('''INSERT INTO scenario_templates(id,activity_id,learner_role,context,objectives_json,success_criteria_json,
                opening_situation,participants_json,rubric_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                ('template-'+identifier,identifier,data['learner_role'],data['context'],json.dumps(data['objectives']),json.dumps(data['success_criteria']),data['opening_situation'],json.dumps(people),json.dumps({'skillId':data['skill_id']}),now,now))
            db.execute('UPDATE training_activities SET posture_mode=?,knowledge_mode=? WHERE id=?',(data.get('posture_mode','off'),data.get('knowledge_mode','off'),identifier))
        return {'id':identifier,**data}

    def save_lesson_settings(self,user,identifier,data):
        self.authorize(user)
        with self.connect() as db:
            if not db.execute('UPDATE training_activities SET posture_mode=?,knowledge_mode=?,updated_at=? WHERE id=?',(data['posture_mode'],data['knowledge_mode'],_now(),identifier)).rowcount:
                raise DomainError('activity_not_found','Lesson not found',status_code=404)
        return {'id':identifier,**data}

    @staticmethod
    def authorize(user):
        if not user or user.get('email', '').lower() not in Config.ADMIN_EMAILS:
            raise DomainError('administrator_required', 'Platform administrator access required', status_code=403)

    def save_skill(self, user, identifier, data):
        self.authorize(user)
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', identifier):
            raise DomainError('invalid_skill_id','Skill identifier must be a lowercase slug',status_code=422)
        now = _now()
        with self.connect() as db:
            if not data['active'] and db.execute('SELECT COUNT(*) FROM skill_catalog WHERE active=1 AND id<>?',(identifier,)).fetchone()[0]==0:
                raise DomainError('last_active_skill','Keep at least one active skill',status_code=409)
            db.execute('''INSERT INTO skill_catalog(id,name,description,category,active,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                description=excluded.description,category=excluded.category,active=excluded.active,updated_at=excluded.updated_at''',
                (identifier,data['name'],data['description'],data['category'],int(data['active']),now,now))
        return {'id': identifier, **data}

    def save_scenario(self, user, identifier, data):
        self.authorize(user)
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM scenario_templates WHERE id=?', (identifier,)).fetchone():
                raise DomainError('scenario_not_found', 'Scenario not found', status_code=404)
            db.execute('''UPDATE scenario_templates SET context=?,objectives_json=?,success_criteria_json=?,
                opening_situation=?,active=?,version=version+1,updated_at=? WHERE id=?''',
                (data['context'],json.dumps(data['objectives']),json.dumps(data['success_criteria']),
                 data['opening_situation'],int(data['active']),_now(),identifier))
        return {'id': identifier, **data}

    def configuration(self, user):
        self.authorize(user)
        return {'max_document_chunks': self.document_chunk_limit()}

    def document_chunk_limit(self):
        with self.connect() as db:
            row = db.execute("SELECT value_json FROM system_configuration WHERE key='max_document_chunks'").fetchone()
        return json.loads(row[0]) if row else 200

    def save_configuration(self, user, value):
        self.authorize(user)
        with self.connect() as db:
            db.execute('''INSERT INTO system_configuration VALUES ('max_document_chunks',?,?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at''',
                (json.dumps(value),_now()))
        return self.configuration(user)
