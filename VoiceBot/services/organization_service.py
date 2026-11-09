"""Organization membership and a privacy-limited trainer view.

Trainers see practice summaries only: never transcripts, recordings, reflections or
private preparation. Scores describe practice in Hikari, not job performance.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from domain.errors import DomainError
from services.service_context import ApplicationService

MANAGERS = {'owner', 'admin'}
VIEWERS = {'owner', 'admin', 'trainer'}
INVITE_ROLES = {'learner', 'trainer', 'admin'}


def _now():
    return datetime.now(timezone.utc)


def _hash(code):
    return hashlib.sha256(code.strip().encode('utf-8')).hexdigest()


class OrganizationService(ApplicationService):
    def membership(self, user_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.membership(user_id, connection)
        row = db.execute("""SELECT m.organization_id,m.role,o.name FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
            WHERE m.user_id=? ORDER BY m.created_at LIMIT 1""", (user_id,)).fetchone()
        if not row:
            raise DomainError('organization_required', 'Organization membership is required', status_code=403)
        return dict(row)

    def overview(self, user_id):
        with self.connect() as db:
            mine = self.membership(user_id, db)
            count = db.execute('SELECT COUNT(*) FROM organization_memberships WHERE organization_id=?', (mine['organization_id'],)).fetchone()[0]
        return {'organization': mine['name'], 'role': mine['role'], 'members': count,
                'can_invite': mine['role'] in MANAGERS, 'can_view_team': mine['role'] in VIEWERS}

    def create_invite(self, user_id, role='learner'):
        if role not in INVITE_ROLES:
            raise DomainError('invalid_role', 'Choose learner, trainer or admin.', status_code=422)
        code = secrets.token_urlsafe(9)
        now = _now()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            mine = self.membership(user_id, db)
            if mine['role'] not in MANAGERS:
                raise DomainError('invite_permission', 'Only organization owners and administrators can invite people.', status_code=403)
            db.execute('INSERT INTO organization_invites(code_hash,organization_id,role,created_by,created_at,expires_at) VALUES (?,?,?,?,?,?)',
                       (_hash(code), mine['organization_id'], role, user_id, now.isoformat(), (now + timedelta(days=7)).isoformat()))
        # The code is returned once. Only its hash is stored.
        return {'code': code, 'role': role, 'expires_in_days': 7}

    def join(self, user_id, code):
        now = _now().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            invite = db.execute('SELECT * FROM organization_invites WHERE code_hash=?', (_hash(code),)).fetchone()
            if not invite or invite['used_at'] or invite['expires_at'] < now:
                raise DomainError('invite_invalid', 'This invite code is not valid. Ask for a new one.', status_code=404)
            mine = self.membership(user_id, db)
            if mine['organization_id'] == invite['organization_id']:
                raise DomainError('already_member', 'You are already in this organization.', status_code=409)
            documents = db.execute('SELECT COUNT(*) FROM document_organizations WHERE organization_id=?', (mine['organization_id'],)).fetchone()[0]
            others = db.execute('SELECT COUNT(*) FROM organization_memberships WHERE organization_id=? AND user_id!=?', (mine['organization_id'], user_id)).fetchone()[0]
            if documents and not others:
                raise DomainError('documents_block_join', 'Delete the documents in your current organization before joining another one.', status_code=409)
            db.execute('DELETE FROM organization_memberships WHERE user_id=?', (user_id,))
            db.execute('INSERT INTO organization_memberships VALUES (?,?,?,?)', (invite['organization_id'], user_id, invite['role'], now))
            db.execute('UPDATE organization_invites SET used_by=?,used_at=? WHERE code_hash=?', (user_id, now, invite['code_hash']))
            name = db.execute('SELECT name FROM organizations WHERE id=?', (invite['organization_id'],)).fetchone()['name']
            db.execute('UPDATE users SET organization=? WHERE id=?', (name, user_id))
        return {'organization': name, 'role': invite['role']}

    def team_progress(self, user_id):
        """Cohort summaries for trainers: enough to plan support, and nothing private."""
        with self.connect() as db:
            mine = self.membership(user_id, db)
            if mine['role'] not in VIEWERS:
                raise DomainError('team_permission', 'Only trainers and organization administrators can view team progress.', status_code=403)
            members = db.execute("""SELECT u.id,u.name,m.role FROM organization_memberships m JOIN users u ON u.id=m.user_id
                WHERE m.organization_id=? ORDER BY u.name""", (mine['organization_id'],)).fetchall()
            team, totals = [], {}
            for member in members:
                completed = db.execute("""SELECT COUNT(*) sessions,AVG(a.overall) average,MAX(s.completed_at) last_active FROM sessions s
                    JOIN assessments a ON a.session_id=s.id WHERE s.user_id=? AND s.status='completed'""", (member['id'],)).fetchone()
                skills = db.execute("""SELECT c.name,p.score FROM proficiency p JOIN skill_catalog c ON c.id=p.skill_id
                    WHERE p.user_id=? AND p.sessions>0 ORDER BY p.score""", (member['id'],)).fetchall()
                for skill in skills:
                    totals.setdefault(skill['name'], []).append(skill['score'])
                team.append({'name': member['name'], 'role': member['role'], 'completed_sessions': completed['sessions'],
                             'average': round(completed['average'], 1) if completed['average'] is not None else None,
                             'last_active': completed['last_active'], 'practice_next': skills[0]['name'] if skills else None})
        cohort = sorted(({'skill': name, 'average': round(sum(values) / len(values), 1), 'learners': len(values)} for name, values in totals.items()), key=lambda item: item['average'])
        return {'organization': mine['name'], 'members': team, 'cohort': cohort}
