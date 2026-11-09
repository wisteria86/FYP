"""Score real stored transcripts read-only. Uses no LLM tokens.

    python -m scripts.conversation_eval.baseline_from_db --output tmp/eval/baseline-db.json
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.conversation_eval.metrics import evaluate, failed_gates, summarise


def private_numbers(definition):
    values = []
    for person in definition['participants']:
        if person['kind'] != 'ai':
            continue
        for key in ('minimum', 'maximum', 'target'):
            value = person.get('private_knowledge', {}).get(key)
            if isinstance(value, (int, float)):
                values.append(value)
    return values


def main(database, output, minimum_turns=3):
    db = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    report = []
    for row in db.execute('SELECT session_id,definition_json FROM conversation_runtime'):
        definition = json.loads(row['definition_json'])
        turns = db.execute("SELECT role,speaker_name,text FROM turns WHERE session_id=? AND text!='' ORDER BY id", (row['session_id'],)).fetchall()
        transcript = [{'role': 'learner' if t['role'] == 'user' else 'ai', 'speaker': t['speaker_name'], 'text': t['text']} for t in turns]
        if sum(t['role'] == 'learner' for t in transcript) < minimum_turns:
            continue
        people = [p for p in definition['participants'] if p['kind'] == 'ai']
        result = evaluate(transcript, known_facts=definition['facts'], private_numbers=private_numbers(definition), ai_names=[p['name'] for p in people])
        report.append({'activity': definition['activity_id'], 'failed': failed_gates(result), **result})
    payload = {'source': 'stored transcripts', 'summary': summarise(report), 'sessions': report}
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(payload['summary'], indent=2))
    for item in report:
        print(item['activity'], 'turns', item['learner_turns'], 'failed:', ', '.join(item['failed']) or 'none')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=ROOT / 'data' / 'hikari.db')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    main(args.database, args.output)
