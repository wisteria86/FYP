"""Evaluation tools. They read the database read-only and write CSV or JSON.

    python -m scripts.evaluation.tools export --database data/hikari.db --output tmp/eval/raters.csv
    python -m scripts.evaluation.tools agree --ratings tmp/eval/raters-filled.csv
    python -m scripts.evaluation.tools learners --database data/hikari.db --output tmp/eval/learners.json

Exports use random codes rather than names and emails, and leave out system judgements from
the rater columns, so that raters are not influenced. Give raters the export and keep the key.
"""
import argparse
import csv
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

JUDGED = ('met', 'not_met')
RATER_COLUMNS = ('rater_a', 'rater_b', 'rater_notes')


def _open(path):
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def rows_for_raters(db, seed=7):
    """One row per objective per completed scene session, in random order."""
    sessions = db.execute("""SELECT s.id,s.user_id,s.activity_id,s.title,c.definition_json,c.state_json FROM sessions s JOIN conversation_runtime c ON c.session_id=s.id
        JOIN assessments x ON x.session_id=s.id WHERE s.status='completed'""").fetchall()
    rng = random.Random(seed)
    learners, output, key = {}, [], []
    for session in sessions:
        definition = json.loads(session['definition_json'])
        if definition.get('version') != 3:
            continue
        state = json.loads(session['state_json'])
        code = learners.setdefault(session['user_id'], f'L{len(learners) + 1:03d}')
        turns = db.execute("SELECT role,speaker_name,text FROM turns WHERE session_id=? AND text!='' ORDER BY id", (session['id'],)).fetchall()
        transcript = '\n'.join(f"{'LEARNER' if t['role'] == 'user' else (t['speaker_name'] or 'CHARACTER')}: {t['text']}" for t in turns)
        evaluation = state.get('completed_evaluation') or state.get('evaluation') or state.get('last_evaluation') or {}
        system = {c['objective_id']: c for c in evaluation.get('criteria', [])}
        for objective in definition['objectives']:
            item_id = f'{rng.getrandbits(40):010x}'
            output.append({'item': item_id, 'learner': code, 'lesson': session['title'], 'objective': objective['description'], 'what_counts': objective['evidence'], 'transcript': transcript,
                           **{column: '' for column in RATER_COLUMNS}})
            result = system.get(objective['id'], {})
            key.append({'item': item_id, 'system': 'met' if result.get('met') else 'not_met', 'support': result.get('support', 'unassessed')})
    rng.shuffle(output)
    return output, key


def cohen_kappa(first, second):
    """Agreement beyond chance. Returns None if there is nothing to compare."""
    pairs = [(a, b) for a, b in zip(first, second) if a and b]
    if not pairs:
        return None
    total = len(pairs)
    observed = sum(a == b for a, b in pairs) / total
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[label] * right[label] for label in set(left) | set(right)) / (total * total)
    return 1.0 if expected == 1 else round((observed - expected) / (1 - expected), 3)


def agreement(rated, key):
    """Compare raters with each other, and each rater with the system, on the same items."""
    system = {row['item']: row['system'] for row in key}
    usable = [row for row in rated if row.get('item') in system]
    def column(name):
        return [row.get(name, '').strip().lower().replace(' ', '_') for row in usable]
    a, b, s = column('rater_a'), column('rater_b'), [system[row['item']] for row in usable]
    bad = sorted({value for value in a + b if value and value not in JUDGED})
    disagreements = [row['item'] for row, x, y, z in zip(usable, a, b, s) if x and y and x == y and x != z]
    return {'items': len(usable), 'invalid_labels': bad, 'rater_a_vs_b_kappa': cohen_kappa(a, b), 'rater_a_vs_system_kappa': cohen_kappa(a, s), 'rater_b_vs_system_kappa': cohen_kappa(b, s),
            'raters_agree_system_differs': disagreements,
            'note': 'Small samples make kappa unstable. Report the number of items and review every item where both raters disagree with the system.'}


def learner_summary(db):
    """Pre/post, transfer and retention evidence per learner, using random codes."""
    summary = defaultdict(lambda: {'attempts': 0, 'first_overall': None, 'latest_overall': None, 'passed_lessons': 0, 'transferred': 0, 'retained': 0, 'used_coach_turns': 0})
    codes = {}
    for row in db.execute("""SELECT s.user_id,x.overall,x.scores,c.state_json FROM sessions s JOIN assessments x ON x.session_id=s.id LEFT JOIN conversation_runtime c ON c.session_id=s.id
            WHERE s.status='completed' ORDER BY s.completed_at"""):
        code = codes.setdefault(row['user_id'], f'L{len(codes) + 1:03d}')
        item = summary[code]
        item['attempts'] += 1
        if item['first_overall'] is None:
            item['first_overall'] = row['overall']
        item['latest_overall'] = row['overall']
        if json.loads(row['scores'] or '{}').get('task_achievement', 0) >= 100:
            item['passed_lessons'] += 1
        if row['state_json']:
            item['used_coach_turns'] += len(json.loads(row['state_json']).get('supported_turn_ids', []))
    for row in db.execute('SELECT user_id,status FROM learning_reviews'):
        if row['user_id'] in codes:
            item = summary[codes[row['user_id']]]
            item['transferred'] += row['status'] == 'transferred'
            item['retained'] += row['status'] == 'retained_later'
    return {'learners': dict(summary), 'note': 'Scores are not calibrated. A change here does not by itself show learning: compare with independent human ratings.'}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--database', type=Path, default=Path('data/hikari.db'))
    export.add_argument('--output', type=Path, required=True)
    agree = sub.add_parser('agree')
    agree.add_argument('--ratings', type=Path, required=True)
    agree.add_argument('--key', type=Path)
    learners = sub.add_parser('learners')
    learners.add_argument('--database', type=Path, default=Path('data/hikari.db'))
    learners.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'export':
        rows, key = rows_for_raters(_open(args.database))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = ['item', 'learner', 'lesson', 'objective', 'what_counts', 'transcript', *RATER_COLUMNS]
        with args.output.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fields)
            writer.writeheader()
            writer.writerows(rows)
        args.output.with_suffix('.key.json').write_text(json.dumps(key, indent=2), encoding='utf-8')
        print(f'{len(rows)} items for raters: {args.output}. Keep the .key.json file away from raters.')
    elif args.command == 'agree':
        with args.ratings.open(encoding='utf-8-sig') as handle:
            rated = list(csv.DictReader(handle))
        key_path = args.key or args.ratings.with_name(args.ratings.stem.replace('-filled', '') + '.key.json')
        print(json.dumps(agreement(rated, json.loads(key_path.read_text(encoding='utf-8'))), indent=2))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(learner_summary(_open(args.database)), indent=2), encoding='utf-8')
        print(f'Wrote {args.output}')


if __name__ == '__main__':
    sys.exit(main())
