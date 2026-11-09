"""Engine-independent conversation metrics.

A transcript is a list of ``{'role': 'learner'|'ai', 'speaker': str, 'text': str}``,
optionally with a director ``move``. These numbers detect observable failures.
They do not establish naturalness, teaching value or learning.
"""
import re
from difflib import SequenceMatcher

_UNITS = ('day', 'week', 'month', 'hour', 'minute', 'percent', 'seat', 'people', 'person', 'usd', 'dollar', 'thousand', 'million')
_WORDS = dict(zip('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(1, 20)))
_TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
_NUMBER_WORD = '|'.join(sorted({*_WORDS, *_TENS, 'hundred', 'thousand', 'million'}, key=len, reverse=True))
_WORD_RUN = re.compile(rf'\b(?:{_NUMBER_WORD})(?:(?:[ -]|\s+and\s+)(?:{_NUMBER_WORD}))*\b', re.I)

CONFUSION = re.compile(
    r"\b(i (?:still |really |just )?(?:do not|don't|didn't|did not) (?:really |quite )?(?:understand|get it|follow|know what)|i'?m (?:confused|lost)|"
    r"what (?:is|'s) (?:even )?(?:happening|going on)|what (?:are|am) i (?:supposed|meant) to|what (?:do|should) i (?:say|do|tell)|"
    r"what (?:are|is) (?:you|we|this) (?:even )?(?:talking about|about)|what do you mean|i have no idea|no idea what)\b", re.I)


def _spoken_value(match):
    total = current = 0
    for word in re.split(r'[ -]+|\s+and\s+', match.group().lower()):
        if word in _WORDS:
            current += _WORDS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == 'hundred':
            current = max(1, current) * 100
        elif word in {'thousand', 'million'}:
            total += max(1, current) * (1000 if word == 'thousand' else 1000000)
            current = 0
    return str(total + current)


def normalise_numbers(text):
    return _WORD_RUN.sub(_spoken_value, text).replace(',', '')


def numbers(text):
    return {float(n) for n in re.findall(r'\d+(?:\.\d+)?', normalise_numbers(text))}


def checked_numbers(text):
    """Figures that assert something: any number with a unit, or any bare number above 12."""
    text = normalise_numbers(text)
    found = set()
    for match in re.finditer(r'(?:usd\s*|\$)?(\d+(?:\.\d+)?)(\s*%|[ -]+(?:\w+[ -]+)?(\w+))?', text, re.I):
        value = float(match.group(1))
        suffix = (match.group(0) or '').lower()
        has_unit = '$' in suffix or 'usd' in suffix or '%' in suffix or any(unit in suffix for unit in _UNITS)
        if value > 12 or (has_unit and value > 1):
            found.add(value)
    return found


def _normal(text):
    return ' '.join(re.findall(r"[\w']+", text.casefold()))


def is_confused(text):
    return bool(CONFUSION.search(text))


def turns_after(transcript, index):
    replies = []
    for turn in transcript[index + 1:]:
        if turn['role'] == 'learner':
            break
        replies.append(turn)
    return replies


def evaluate(transcript, *, known_facts=(), private_numbers=(), ai_names=(), forbidden=()):
    """Return raw counts and rates for one transcript."""
    ai = [t for t in transcript if t['role'] == 'ai']
    learner = [t for t in transcript if t['role'] == 'learner']
    known = set()
    for fact in known_facts:
        known |= numbers(fact)
    private = set(float(n) for n in private_numbers)
    invented, leaked, heard = [], [], set(known)
    for turn in transcript:
        if turn['role'] == 'learner':
            heard |= numbers(turn['text'])
            continue
        for value in checked_numbers(turn['text']):
            if value in private and value not in heard:
                leaked.append({'value': value, 'text': turn['text']})
            elif value not in heard and value not in private and not turn.get('authorised'):
                invented.append({'value': value, 'text': turn['text']})
        heard |= numbers(turn['text'])

    addressing = 0
    names = [n for n in ai_names if n]
    for turn in ai:
        others = [n for n in names if n != turn.get('speaker')]
        if any(re.match(rf"\s*(?:(?:thanks|thank you|well|okay|right|so|but),?\s+)?{re.escape(n)}\b[,:]?", turn['text'], re.I) for n in others):
            addressing += 1

    duplicates = 0
    previous = []
    for turn in ai:
        text = _normal(turn['text'])
        if len(text.split()) >= 5 and any(SequenceMatcher(None, text, old).ratio() > .84 for old in previous):
            duplicates += 1
        previous.append(text)

    question_counts = {}
    for turn in ai:
        for question in re.findall(r'[^.!?]*\?', turn['text']):
            key = _normal(question)
            if len(key.split()) >= 3:
                question_counts[key] = question_counts.get(key, 0) + 1

    confusion_total = confusion_ignored = 0
    for index, turn in enumerate(transcript):
        if turn['role'] != 'learner' or not is_confused(turn['text']):
            continue
        confusion_total += 1
        replies = turns_after(transcript, index)
        move = replies[0].get('move') if replies else None
        if move:
            handled = move in {'rephrase_simple', 'orient', 'call_coach', 'answer'}
        else:
            others = [n for n in names if replies and n != replies[0].get('speaker')]
            talks_past = len(replies) > 1 or (bool(replies) and any(re.match(rf'\s*{re.escape(n)}\b', replies[0]['text'], re.I) for n in others))
            handled = bool(replies) and not talks_past
        confusion_ignored += not handled

    ai_words = sum(len(t['text'].split()) for t in ai)
    learner_words = sum(len(t['text'].split()) for t in learner)
    learner_turns = max(1, len(learner))
    return {
        'learner_turns': len(learner),
        'ai_turns': len(ai),
        'ai_turns_per_learner_turn': round(len(ai) / learner_turns, 2),
        'ai_word_share': round(ai_words / max(1, ai_words + learner_words), 2),
        'ai_to_ai_exchanges': addressing,
        'ai_to_ai_per_3_learner_turns': round(addressing * 3 / learner_turns, 2),
        'invented_numbers': invented,
        'private_leaks': leaked,
        'says_learner': sum(bool(re.search(r'\blearner\b', t['text'], re.I)) for t in ai),
        'forbidden_claims': sum(any(re.search(p, t['text'], re.I) for p in forbidden) for t in ai),
        'near_duplicates': duplicates,
        'near_duplicate_rate': round(duplicates / max(1, len(ai)), 3),
        'max_repeated_question': max(question_counts.values(), default=0),
        'confusion_turns': confusion_total,
        'confusion_ignored': confusion_ignored,
    }


GATES = {
    'invented_numbers': lambda r: not r['invented_numbers'],
    'private_leaks': lambda r: not r['private_leaks'],
    'says_learner': lambda r: r['says_learner'] == 0,
    'forbidden_claims': lambda r: r['forbidden_claims'] == 0,
    'confusion_ignored': lambda r: r['confusion_ignored'] == 0,
    'ai_to_ai': lambda r: r['ai_to_ai_per_3_learner_turns'] <= 1,
    'near_duplicates': lambda r: r['near_duplicate_rate'] < .03,
    'repeated_question': lambda r: r['max_repeated_question'] < 3,
}


def failed_gates(result):
    return [name for name, check in GATES.items() if not check(result)]


def summarise(results):
    """Aggregate per-transcript results for a before/after comparison."""
    count = max(1, len(results))
    return {
        'transcripts': len(results),
        'passing_all_gates': sum(not failed_gates(r) for r in results),
        'gate_failures': {name: sum(not check(r) for r in results) for name, check in GATES.items()},
        'avg_ai_turns_per_learner_turn': round(sum(r['ai_turns_per_learner_turn'] for r in results) / count, 2),
        'avg_ai_word_share': round(sum(r['ai_word_share'] for r in results) / count, 2),
        'invented_numbers': sum(len(r['invented_numbers']) for r in results),
        'private_leaks': sum(len(r['private_leaks']) for r in results),
        'confusion_turns': sum(r['confusion_turns'] for r in results),
        'confusion_ignored': sum(r['confusion_ignored'] for r in results),
    }
