"""Expand the authored lessons into validated case packs in content/cases.

    python -m scripts.case_authoring.build
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.english_curriculum import ENGLISH_CURRICULUM, _LEARNING_TARGETS
from domain.conversation import ScenarioDefinition
from intelligence.case_library import compile_case, load_pack, _cache
from scripts.case_authoring.lessons_beginner import LESSONS as BEGINNER
from scripts.case_authoring.lessons_intermediate import LESSONS as INTERMEDIATE
from scripts.case_authoring.lessons_advanced import LESSONS as ADVANCED

OUT = ROOT / 'content' / 'cases'


def card(person):
    return {'want': person['want'], 'hidden_need': person['need'], 'attitude': person['attitude'], 'speech': person['speech'], 'tactics': person['tactics'],
            'pressure': {'gentle': 'Patient. Gives the other person time.', 'balanced': 'Pushes back once on anything vague.', 'challenging': 'Keeps pressing for specifics, fairly and without insults.'}}


def build(lesson):
    sequence = int(lesson['lid'].split('-')[1]) if lesson['lid'].startswith('english-') else None
    curriculum = ENGLISH_CURRICULUM[sequence - 1] if sequence else None
    targets = _LEARNING_TARGETS[sequence][3] if sequence else None
    participants = [{'id': 'p0', 'name': 'You', 'role': lesson['role'], 'kind': 'learner', 'team': 'learner', 'relationship': lesson['you_are'],
                     'goals': [lesson['task']], 'voice_index': 0, 'can_finalize': lesson['finalize']}]
    for index, person in enumerate(lesson['ai']):
        participants.append({'id': f'p{index + 1}', 'name': person['name'], 'role': person['role'], 'kind': 'ai', 'team': 'opponent', 'relationship': person['rel'],
                             'voice_index': index, 'topics': person['topics'], 'card': card(person)})
    ledger = []
    for index, fact in enumerate(lesson['facts']):
        text, owner, start = (fact if isinstance(fact, tuple) else (fact, 'public', None)) if not (isinstance(fact, tuple) and len(fact) == 2) else (fact[0], fact[1], None)
        entry = {'id': f'f{index + 1}', 'text': text}
        if owner != 'public':
            entry['owner'] = owner
        if start is not None:
            entry['available_from'] = f'b{start}'
        ledger.append(entry)
    objectives, beats, notes = [], [], {}
    for index, item in enumerate(lesson['objectives']):
        oid = f'o{index + 1}'
        description = item['desc'] or curriculum[5][index]
        objectives.append({'id': oid, 'description': description, 'evidence': item['evidence'], 'alternatives': [item['alt']]})
        signals = [item['signal']] if item['signal'] else [p.replace(r'[^?]*\?', '') for p in targets[index][1]]
        beat = {'id': f'b{index + 1}', 'goal': item['goal'], 'driver': f"p{item['driver']}", 'objectives': [oid], 'signals': signals, 'stall_turns': 3 if len(lesson['ai']) > 1 else 2,
                'min_turns': item['min_turns'], 'opportunity': item['opp'], 'orient': item['orient'], 'fallback': item['opp'][::-1] + ['Please go on.']}
        if item['second']:
            beat['second_speaker'], beat['second_line'] = item['second']
        beats.append(beat)
        notes[oid] = {'good': item['good'], 'common_mistakes': [item['miss']], 'micro_lesson': item['micro'], 'model': item['model'], 'smaller_step': item['step'], 'subskills': [item['sub']]}
    return {'archetype': lesson['arche'], 'level': lesson['level'], 'setting': lesson['setting'],
            'presentation': {'situation': lesson['situation'], 'opening': lesson['opening'], 'opening_speaker': 'p1', 'learner_role': lesson['role']},
            'brief': {'you_are': lesson['you_are'], 'situation': lesson['situation'], 'task': lesson['task'], 'done_looks_like': lesson['done']},
            'participants': participants, 'ledger': ledger, 'objectives': objectives,
            'examples': lesson['examples'] or (_LEARNING_TARGETS[sequence][1] if sequence else [item['model'] for item in lesson['objectives']]),
            'prerequisites': ['Read the briefing.'], 'beats': beats, 'closing_line': lesson['closing'], 'expert_notes': notes, 'variants': lesson['variants']}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for lesson in [*BEGINNER, *INTERMEDIATE, *ADVANCED]:
        path = OUT / f"{lesson['lid']}.json"
        path.write_text(json.dumps(build(lesson), indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
        _cache.pop(lesson['lid'], None)
        load_pack(lesson['lid'])
        for variant in range(len(lesson['variants'])):
            compile_case(lesson['lid'], variant)  # Raises if the pack is invalid.
        made += 1
    print(f'Built and validated {made} packs.')


if __name__ == '__main__':
    main()
