"""Load authored case packs from content/cases and compile them into definitions.

A pack is one JSON file per activity. ``variants`` hold the details that change
between attempts, so a retry or transfer case keeps the same skill and objectives
but different facts. Placeholders are written ``{{name}}``.
"""
import json
import re
from pathlib import Path

from domain.conversation import ScenarioDefinition

CASE_DIR = Path(__file__).resolve().parents[1] / 'content' / 'cases'
_PLACEHOLDER = re.compile(r'\{\{(\w+)\}\}')
_cache = {}


def _fill(value, variables):
    if isinstance(value, str):
        def replace(match):
            if match.group(1) not in variables:
                raise ValueError(f'Case uses an undefined placeholder: {match.group(1)}')
            return str(variables[match.group(1)])
        return _PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [_fill(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _fill(item, variables) for key, item in value.items()}
    return value


def available_cases():
    return sorted(path.stem for path in CASE_DIR.glob('*.json')) if CASE_DIR.exists() else []


def load_pack(activity_id):
    if activity_id not in _cache:
        path = CASE_DIR / f'{activity_id}.json'
        _cache[activity_id] = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    return _cache[activity_id]


def variant_count(activity_id):
    pack = load_pack(activity_id)
    return len(pack.get('variants') or [{}]) if pack else 0


def compile_case(activity_id, variant=0, level=None, extra_facts=()):
    """Return ``(definition, presentation)`` or ``None`` when no pack is authored."""
    pack = load_pack(activity_id)
    if not pack:
        return None
    variants = pack.get('variants') or [{}]
    chosen = variants[variant % len(variants)]
    data = _fill({key: value for key, value in pack.items() if key != 'variants'}, chosen)
    presentation = data.pop('presentation')
    data['ledger'] = data['ledger'] + list(extra_facts)
    data['version'] = 3
    data['activity_id'] = activity_id
    if level:
        data['level'] = level
    case = chosen.get('negotiation')
    if case:
        data['negotiation'] = case
    negotiation = data.get('negotiation')
    if negotiation:
        for person in data['participants']:
            if person.get('party') and not person.get('private_knowledge'):
                person['private_knowledge'] = negotiation[person['party']]
    public = [fact['text'] for fact in data['ledger'] if fact.get('owner', 'public') == 'public']
    data['facts'] = public
    for person in data['participants']:
        own = [fact['text'] for fact in data['ledger'] if fact.get('owner') == person['id']]
        person['public_knowledge'] = public
        if own:
            person.setdefault('private_knowledge', {})
            person['private_knowledge'] = {**person['private_knowledge'], 'facts': own}
    definition = ScenarioDefinition(**data).model_dump()
    presentation['variant'] = variant % len(variants)
    return definition, presentation
