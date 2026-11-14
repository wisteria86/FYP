"""Level-based learning path built only from stored evidence.

Units group the English lessons, and a unit's last lesson is its checkpoint. Passing
it opens the next unit. A learner can always attempt a checkpoint, or try a locked
lesson anyway: locks guide, and they never trap anyone. Nothing here claims a CEFR
level or lasting mastery.
"""
import json
from datetime import datetime, timezone

from intelligence.case_library import load_pack
from services.service_context import ApplicationService

UNITS = [
    ('Meeting people', 'Greet people, introduce yourself and talk about your life.', range(1, 6)),
    ('Everyday situations', 'Order, shop, find your way, book and keep a conversation going.', range(6, 11)),
    ('Telling and explaining', 'Tell stories, make plans, explain problems and give instructions.', range(11, 16)),
    ('English at work', 'Small talk, updates, listening, customers and group planning.', range(16, 21)),
    ('Proving your case', 'Interviews, proposals, negotiation and constructive disagreement.', range(21, 26)),
    ('Leading conversations', 'Feedback, conflict, difficult meetings and cross-cultural work.', range(26, 31)),
]
STATES = {'not_started': 'Not started', 'practising': 'Practising', 'independent_today': 'Shown today', 'transferred': 'Used in a new case', 'retained_later': 'Retained later'}


def _passed(row):
    scores = json.loads(row['scores'] or '{}')
    if 'task_achievement' in scores:
        return scores['task_achievement'] >= 100
    return (row['overall'] or 0) >= 60


class LearningPathService(ApplicationService):
    def _evidence(self, db, user_id):
        evidence = {}
        for row in db.execute("""SELECT s.activity_id,x.overall,x.scores,x.strengths,s.completed_at,s.branch_of,
                COALESCE(json_extract(r.state_json,'$.rewinds'),0) AS rewinds
                FROM sessions s JOIN assessments x ON x.session_id=s.id LEFT JOIN conversation_runtime r ON r.session_id=s.id
                WHERE s.user_id=? AND s.status='completed' ORDER BY s.completed_at""", (user_id,)):
            item = evidence.setdefault(row['activity_id'], {'attempts': 0, 'passed': False, 'best': 0, 'quote': None, 'retried': 0})
            item['attempts'] += 1
            item['best'] = max(item['best'], row['overall'] or 0)
            # Taking turns back, or replaying a moment, is good practice but not independent evidence.
            if row['rewinds'] or row['branch_of']:
                item['retried'] += 1
                continue
            if _passed(row):
                item['passed'] = True
                strengths = json.loads(row['strengths'] or '[]')
                if strengths:
                    item['quote'] = strengths[0]
        reviews = {}
        for row in db.execute('SELECT activity_id,status FROM learning_reviews WHERE user_id=?', (user_id,)):
            reviews.setdefault(row['activity_id'], set()).add(row['status'])
        return evidence, reviews

    @staticmethod
    def _state(activity_id, evidence, reviews):
        item = evidence.get(activity_id)
        marks = reviews.get(activity_id, set())
        if 'retained_later' in marks:
            return 'retained_later'
        if 'transferred' in marks:
            return 'transferred'
        if item and item['passed']:
            return 'independent_today'
        return 'practising' if item else 'not_started'

    @staticmethod
    def _can_do(activity_id, evidence):
        item = evidence.get(activity_id)
        pack = load_pack(activity_id)
        if not item or not item['passed'] or not pack:
            return None
        return {'objectives': [o['description'] for o in pack['objectives']], 'evidence': item['quote']}

    def path(self, user_id):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            activities = {row['id']: dict(row) for row in db.execute('SELECT id,title,description,primary_skill_id,proficiency_level,difficulty,sequence_number,training_language FROM training_activities WHERE active=1')}
            evidence, reviews = self._evidence(db, user_id)
            due = [dict(row) for row in db.execute("""SELECT r.id,r.activity_id,r.due_at,r.interval_days,a.title,a.primary_skill_id,a.proficiency_level,a.difficulty FROM learning_reviews r
                JOIN training_activities a ON a.id=r.activity_id WHERE r.user_id=? AND r.status='due' AND r.due_at<=? ORDER BY r.due_at""", (user_id, now))]
        units, open_next = [], True
        next_lesson = None
        for number, (title, summary, sequence) in enumerate(UNITS, 1):
            lessons = []
            ids = [f'english-{n:02d}' for n in sequence]
            checkpoint = ids[-1]
            for lesson_id in ids:
                activity = activities.get(lesson_id)
                if not activity:
                    continue
                state = self._state(lesson_id, evidence, reviews)
                is_checkpoint = lesson_id == checkpoint
                entry = {'id': lesson_id, 'skill_id': activity['primary_skill_id'], 'title': activity['title'], 'description': activity['description'], 'level': activity['proficiency_level'],
                         'state': state, 'state_label': STATES[state], 'attempts': evidence.get(lesson_id, {}).get('attempts', 0),
                         'checkpoint': is_checkpoint, 'locked': not open_next and not is_checkpoint, 'can_do': self._can_do(lesson_id, evidence)}
                lessons.append(entry)
                if next_lesson is None and open_next and state in {'not_started', 'practising'}:
                    next_lesson = entry
            shown = sum(entry['state'] not in {'not_started', 'practising'} for entry in lessons)
            units.append({'number': number, 'title': title, 'summary': summary, 'unlocked': open_next, 'shown': shown, 'total': len(lessons), 'lessons': lessons})
            open_next = evidence.get(checkpoint, {}).get('passed', False)
        workplace = []
        for activity in sorted((a for a in activities.values() if not a['training_language']), key=lambda a: a['title']):
            state = self._state(activity['id'], evidence, reviews)
            workplace.append({'id': activity['id'], 'skill_id': activity['primary_skill_id'], 'title': activity['title'], 'description': activity['description'], 'level': activity['difficulty'],
                              'state': state, 'state_label': STATES[state], 'attempts': evidence.get(activity['id'], {}).get('attempts', 0), 'locked': False, 'checkpoint': False,
                              'can_do': self._can_do(activity['id'], evidence)})
        everything = [lesson for unit in units for lesson in unit['lessons']] + workplace
        counts = {key: sum(lesson['state'] == key for lesson in everything) for key in ('independent_today', 'transferred', 'retained_later')}
        return {'units': units, 'workplace': workplace, 'next': next_lesson, 'due_reviews': due, 'counts': counts,
                'note': 'This path shows what you demonstrated in Hikari. Finishing lessons does not establish a CEFR level or permanent mastery.'}
