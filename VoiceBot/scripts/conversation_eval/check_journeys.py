"""Whole learner journeys over the real HTTP API. Use only against the evaluation server.

    python scripts/conversation_eval/serve.py --port 8000 --full
    python -m scripts.conversation_eval.check_journeys

Each journey reports pass, fail or a note. Live model replies vary, so read the printed lines too.
"""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PASSWORD = 'Local-eval-only-7391!'
results = []


def check(name, passed, detail=''):
    results.append((name, bool(passed), detail))
    print(f"{'PASS' if passed else 'FAIL'}  {name}{f'  [{detail}]' if detail else ''}", flush=True)


def account(base, label):
    client = httpx.Client(base_url=base, timeout=120)
    email = f'{label}.{uuid.uuid4().hex[:8]}@example.test'
    client.post('/api/auth/register', json={'name': label.title(), 'organization': f'{label} org {uuid.uuid4().hex[:6]}', 'email': email, 'password': PASSWORD}).raise_for_status()
    return client


def start(client, skill, activity, difficulty='intermediate', **options):
    preview = client.post('/api/scenarios/preview', json={'skill_id': skill, 'difficulty': difficulty, 'activity_id': activity, **options})
    preview.raise_for_status()
    body = preview.json()
    session = client.post('/api/sessions', json={'skill_id': skill, 'difficulty': difficulty, 'activity_id': activity, 'preview_id': body['preview_id']})
    session.raise_for_status()
    return body, session.json()


def say(client, sid, text, delay):
    response = client.post(f'/api/sessions/{sid}/turn', json={'text': text, 'synthesize_audio': False, 'request_id': uuid.uuid4().hex})
    response.raise_for_status()
    body = response.json()
    for reply in body['responses']:
        print(f"    {reply['speaker']} [{reply.get('move')}/{reply.get('response_mode')}]: {reply['text']}", flush=True)
    time.sleep(delay)
    return body


def action(client, sid, kind, data=None):
    return client.post(f'/api/sessions/{sid}/actions', json={'action': kind, 'request_id': uuid.uuid4().hex, 'data': data or {}})


def journey_negotiation(base, delay):
    print('\n== Negotiation with private preparation', flush=True)
    client = account(base, 'buyer')
    preview, session = start(client, 'negotiation', 'activity-negotiation')
    sid = session['id']
    public = json.dumps(preview.get('runtime_definition', {})) if False else ''
    check('Session uses the new engine', session['runtime'].get('scene') is not None)
    view = json.dumps(session)
    check('Session response hides private character data', 'private_knowledge' not in view and '"directions"' not in view)
    prep = action(client, sid, 'prepare', {'target': '9500 because of last year', 'alternative': 'The other supplier at 8500 with 45 days', 'walk_away': 'Above 11500 the alternative is better', 'reason': 'Our budget and the benchmark'})
    check('Private preparation is saved', prep.status_code == 200, str(prep.status_code))
    for line in ('What matters most to you on this deal, and why does delivery timing matter?', 'The earlier package sold for USD 11000, so I can offer USD 9500 because of our budget.',
                 'If you can do USD 10500, I can accept delivery in 45 days.'):
        say(client, sid, line, delay)
    final = say(client, sid, 'I accept. To confirm: USD 10500, 20 seats, delivery in 45 days and 3 months of support.', delay)
    offers = final['runtime']['offers']
    check('A spoken acceptance reaches the ledger', any(o['status'] == 'accepted' for o in offers), str([(o['terms']['price'], o['status']) for o in offers]))
    assessment = client.post(f'/api/sessions/{sid}/complete?end_attempt=true').json()
    print('    scores', assessment.get('scores'), flush=True)
    check('Decision quality is scored apart from language', any(key.startswith('decision_') for key in assessment.get('scores', {})))
    leaked = [word for word in ('minimum', '10000') if word in ' '.join(assessment.get('improvements', []))]
    check('Debrief keeps the supplier limit private', not leaked, str(leaked))


def journey_document(base, delay):
    print('\n== Company document', flush=True)
    client = account(base, 'staff')
    blocked = client.post('/api/scenarios/preview', json={'skill_id': 'company-knowledge', 'difficulty': 'intermediate', 'activity_id': 'activity-company-knowledge'})
    check('A company lesson with no document gives a clear message', blocked.status_code >= 400, blocked.text[:90])
    text = 'Annual leave policy. Employees must request annual leave at least 10 working days in advance using the HR portal. A line manager must approve the request before travel is booked. Requests with less notice need written approval from the department head.'
    upload = client.post('/api/documents', files={'file': ('leave-policy.txt', text.encode(), 'text/plain')})
    check('A document uploads', upload.status_code == 200, upload.text[:100] if upload.status_code != 200 else '')
    if upload.status_code != 200:
        return
    identifier = upload.json().get('id')
    preview, session = start(client, 'company-knowledge', 'activity-company-knowledge', document_ids=[identifier])
    sid = session['id']
    check('The lesson is built from the document', '10 working days' in json.dumps(session), preview['situation'][:80])
    first = say(client, sid, 'According to the document, what does the leave rule require here?', delay)
    print('    sources', [s['name'] for s in first.get('sources', [])], flush=True)
    wrong = 'The policy says you only need 2 days of notice, so you can book it today.'
    say(client, sid, wrong, delay)
    assessment = client.post(f'/api/sessions/{sid}/complete?end_attempt=true').json()
    joined = ' '.join(assessment.get('improvements', []) + assessment.get('evidence', []))
    print('    policy lines', [line[:140] for line in assessment.get('evidence', []) if line.startswith('Policy check')], flush=True)
    check('A wrong policy claim earns no credit for the rule', 'State what the document actually requires: not shown yet' in joined or 'does not support' in joined)
    other = account(base, 'outsider')
    documents = other.get('/api/documents').json()
    check('Another organization cannot see the document', all(d.get('id') != identifier for d in documents))


def journey_organization(base):
    print('\n== Organization and trainer view', flush=True)
    owner, learner = account(base, 'owner'), account(base, 'learner')
    denied = learner.get('/api/organization/team')
    invite = owner.post('/api/organization/invites', json={'role': 'trainer'}).json()
    joined = learner.post('/api/organization/join', json={'code': invite['code']})
    check('A person joins with an invite code', joined.status_code == 200, joined.text[:90])
    again = account(base, 'late').post('/api/organization/join', json={'code': invite['code']})
    check('An invite code works only once', again.status_code == 404, str(again.status_code))
    team = learner.get('/api/organization/team')
    check('A trainer sees the team summary', team.status_code == 200 and len(team.json()['members']) == 2)
    check('Owners of a one-person organization see only themselves first', denied.status_code == 200 and len(denied.json()['members']) == 1)
    learner_two = account(base, 'plain')
    code = owner.post('/api/organization/invites', json={'role': 'learner'}).json()['code']
    learner_two.post('/api/organization/join', json={'code': code}).raise_for_status()
    check('A plain learner cannot view the team', learner_two.get('/api/organization/team').status_code == 403)
    check('A plain learner cannot invite', learner_two.post('/api/organization/invites', json={'role': 'learner'}).status_code == 403)


def journey_access(base):
    print('\n== Access rules', flush=True)
    anonymous = httpx.Client(base_url=base, timeout=30)
    for method, path in (('get', '/api/monitor/snapshot'), ('get', '/api/learning-path'), ('get', '/api/goals'), ('get', '/api/organization'), ('get', '/api/dashboard')):
        check(f'Signed-out {path} is refused', getattr(anonymous, method)(path).status_code == 401)
    first, second = account(base, 'alice'), account(base, 'bob')
    _, session = start(first, 'english-speaking', 'english-02', 'beginner')
    check("Another learner cannot read a session", second.get(f"/api/sessions/{session['id']}").status_code in {401, 403, 404})
    check('A learner is not an administrator', first.get('/api/admin/catalog').status_code == 403)


def journey_path(base, delay):
    print('\n== Goals, path and an honest partial attempt', flush=True)
    client = account(base, 'path')
    path = client.get('/api/learning-path').json()
    check('A new learner starts at lesson 1', path['next']['id'] == 'english-01')
    check('All 30 English lessons appear in units', sum(len(u['lessons']) for u in path['units']) == 30)
    goal = client.post('/api/goals', json={'title': 'Get better at interviews', 'skill_id': 'interviews'})
    check('A goal is saved', goal.status_code == 200 and len(client.get('/api/goals').json()) == 1)
    _, session = start(client, 'english-speaking', 'english-01', 'beginner')
    sid = session['id']
    say(client, sid, 'Hi, I am Abdul.', delay)
    assessment = client.post(f"/api/sessions/{sid}/complete?end_attempt=true").json()
    print('    scores', assessment.get('scores'), 'overall', assessment.get('overall'), flush=True)
    check('A partial attempt is not scored 100', assessment.get('overall', 100) < 100)
    path = client.get('/api/learning-path').json()
    lesson = next(l for u in path['units'] for l in u['lessons'] if l['id'] == 'english-01')
    check('The attempt shows as practising', lesson['state'] == 'practising', lesson['state'])
    dashboard = client.get('/api/dashboard').json()
    check('Goal skill is in the plan', any(item.get('skill_id') == 'interviews' for item in dashboard['plan']), str([item.get('skill_id') for item in dashboard['plan']]))
    reflected = action(client, sid, 'reflect', {'text': 'I should say goodbye next time.'})
    check('Reflection saves after the lesson', reflected.status_code == 200, str(reflected.status_code))
    next_preview = client.post('/api/scenarios/preview', json={'skill_id': 'english-speaking', 'difficulty': 'beginner', 'activity_id': 'english-01'}).json()
    print('    next attempt:', next_preview.get('adaptation_reason'), flush=True)
    check('The next attempt names the missed objective', 'not shown yet last time' in next_preview.get('adaptation_reason', ''))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--delay', type=float, default=15)
    parser.add_argument('--only')
    args = parser.parse_args()
    base = f'http://localhost:{args.port}'
    journeys = {'access': lambda: journey_access(base), 'organization': lambda: journey_organization(base), 'path': lambda: journey_path(base, args.delay),
                'document': lambda: journey_document(base, args.delay), 'negotiation': lambda: journey_negotiation(base, args.delay)}
    for name, run in journeys.items():
        if args.only and name not in args.only.split(','):
            continue
        try:
            run()
        except Exception as exc:
            check(f'Journey {name} finished', False, f'{type(exc).__name__}: {str(exc)[:220]}')
    failed = [row for row in results if not row[1]]
    print(f'\n{len(results) - len(failed)} of {len(results)} checks passed.', flush=True)
    for name, _, detail in failed:
        print(' FAILED:', name, detail, flush=True)


if __name__ == '__main__':
    main()
