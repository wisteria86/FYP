"""Run the scene in code: read the turn, track the stage, choose one move.

The model performs the chosen line. Provisional objective signals only steer the
scene; they never award credit. Credit comes from the evidence review alone.
"""
import re
from difflib import SequenceMatcher

from intelligence.conversation_direction import addressed_people, numeric_text
from intelligence.negotiation_strategy import apply as apply_negotiation, decide as decide_negotiation, new_state as new_negotiation

CONFUSED_TASK = re.compile(
    r"\b(what (?:are|am) i (?:supposed|meant|expected) to|what (?:do|should) i (?:say|do|tell)|what(?:'s| is) (?:even )?(?:happening|going on)|"
    r"what (?:are|is) (?:we|this) (?:even )?(?:doing|about)|i(?:'m| am) (?:confused|lost)|i (?:do not|don't) know what|no idea what|"
    r"what(?:'s| is) my (?:job|role|task)|who am i|what are you (?:even )?talking about|i (?:still |really |just )?(?:do not|don't|didn't|did not) (?:really |quite )?(?:understand|get it|follow)(?: this| what)?)\b", re.I)
CONFUSED_LINE = re.compile(
    r"\b(what do you mean|what does .{1,30} mean|say (?:that|it) again|could you repeat|can you repeat|please repeat|repeat (?:that|please)|"
    r"pardon|didn't (?:catch|hear)|did not (?:catch|hear)|slow(?:er)? down|too fast|in (?:simple|simpler|easy|easier) (?:words|english)|could you explain|can you explain)\b", re.I)
IDENTITY = re.compile(r"\b(who (?:are|r) you|what(?:'s| is) your (?:name|role|job)|introduce yourself)\b", re.I)
ACK = re.compile(r"^(?:okay|ok|yes|yeah|yep|right|sure|uh huh|mm+|go on|i see|fine|no|nope|thanks|thank you)[.!, ]*$", re.I)
QUESTION = re.compile(r"\?\s*$|^\s*(?:what|why|how|when|where|who|which|can you|could you|would you|do you|did you|are you|is (?:it|there|that)|will you|tell me)\b", re.I)
COLLECTIVE = re.compile(r"\b(everyone|both of you|each of you|you two|all of you)\b", re.I)
_FRAGMENT_END = {'the', 'a', 'an', 'and', 'but', 'or', 'so', 'to', 'of', 'in', 'on', 'for', 'with', 'are', 'is', 'am', 'i', 'my', 'your', 'if', 'because', 'that', 'what', 'even'}
STOCK = ('Sorry, I missed that. Could you say it again?', "I didn't quite catch that. Could you say it another way?", 'Sorry, could you repeat that?')

MOVES = {
    'answer': ('Answer what they just asked, directly, in your first sentence, using only what you know. If their question gets at why something matters to you, tell them your real reason now. Do not answer a question with a question. If you do not know, say so plainly.', 45),
    'respond': ('Respond naturally to what they just said, from your own point of view. Move the conversation forward.', 32),
    'probe': ('Ask one specific follow-up question about what they just said. Refer to their actual words.', 25),
    'push_back': ('Push back on what they said, with a specific reason from what you know. Stay fair and in character.', 35),
    'reveal_fact': ('React to what they said, then naturally bring in this fact, in your own words: {fact}', 42),
    'advance_beat': ('React to what they said in a few words, then finish by moving things on. {steer}', 38),
    'create_opportunity': ('React to what they said in a few words, then say something with this meaning: {steer}', 30),
    'rephrase_simple': ('They did not understand your last point. Say the same thing again in simpler, shorter words. Add nothing new.', 22),
    'redirect': ('They went off the subject. Acknowledge it in a few words, then bring them back to this: {steer}', 25),
    'wind_down': ('Accept what they just said, in one short warm sentence. Do not ask anything. Do not push back.', 18),
    'bargain': ('{bargain}', 40),
}
LEVEL_WORD_CAP = {'beginner': 16, 'intermediate': 45, 'advanced': 70}


def new_scene(definition):
    scene = {'beat': 0, 'beat_turns': 0, 'signals': [], 'revealed': [], 'used_lines': [], 'confusion': 0,
             'finished': False, 'moves': [], 'second_done': [], 'read': None, 'reopened': []}
    if definition.get('negotiation'):
        scene['negotiation'] = new_negotiation(definition['negotiation'])
    return scene


def read_local(text, unreliable=False):
    """Classify only what is safe to recognise without a model."""
    stripped = text.strip()
    words = re.findall(r"[\w']+", stripped.lower())
    if unreliable or not words:
        return {'act': 'garbled'}
    if IDENTITY.search(stripped):
        return {'act': 'identity'}
    if CONFUSED_LINE.search(stripped):
        return {'act': 'confused_line'}
    if CONFUSED_TASK.search(stripped):
        return {'act': 'confused_task'}
    if ACK.match(stripped):
        return {'act': 'ack'}
    if len(words) >= 2 and len(set(words)) == 1:
        return {'act': 'garbled'}
    if len(words) <= 4 and words[-1] in _FRAGMENT_END and not stripped.endswith('?'):
        return {'act': 'garbled'}
    return {'act': 'question' if QUESTION.search(stripped) else 'substantive'}


_COMMON = set('the a an and or but so to of in on at for with from by is are am was were be been it this that these those i you we they he she my your our their me us them do does did have has had can could would should will not no yes what why how when where who which there here if then than as about just really very please thanks thank okay ok '
              'think quite difficult situation problem thing things good bad want need know like feel say said tell make made get got see look going work working people time today now first next last want wants maybe sure right well also more most some any all one two try help better important'.split())
# In these lessons the learner brings their own material, so unfamiliar words are expected.
_OWN_MATERIAL = {'interview', 'panel', 'social'}


def is_off_topic(definition, text, recent):
    """True only when a full sentence shares no meaningful word with the scene."""
    if definition.get('archetype') in _OWN_MATERIAL or re.search(r'\d|hundred|thousand', text, re.I):
        return False
    if any(re.search(pattern, text, re.I) for beat in definition['beats'] for pattern in beat['signals']):
        return False
    words = {w for w in re.findall(r"[a-z']+", text.casefold()) if w not in _COMMON and len(w) > 2}
    if len(re.findall(r'\w+', text)) < 3 or not words:
        return False
    known = ' '.join([definition['setting'], *[f['text'] for f in definition['ledger']], *(definition['brief'].get(k, '') for k in ('situation', 'task', 'you_are')),
                      *[o['description'] for o in definition['objectives']], *[b['goal'] for b in definition['beats']], *[line for b in definition['beats'] for line in b['opportunity']],
                      *[p['role'] for p in definition['participants']], *[p['name'] for p in definition['participants']], *[t for p in definition['participants'] for t in p.get('topics', [])], *recent])
    vocabulary = {w[:5] for w in re.findall(r"[a-z']+", known.casefold())}
    return not any(w[:5] in vocabulary for w in words)


def needs_router(read, text):
    """Only ambiguous, substantial turns justify spending tokens on a reading."""
    return read['act'] in {'substantive', 'question'} and len(text.split()) >= 4


def router_context(definition, scene, text, recent):
    beat = definition['beats'][scene['beat']]
    objectives = {o['id']: o for o in definition['objectives']}
    return {'setting': definition['setting'], 'current_goal': beat['goal'],
            'objectives': [{'id': oid, 'description': objectives[oid]['description']} for oid in beat['objectives'] if oid in objectives],
            'recent': recent[-3:], 'latest': text}


def merge_reading(local, reading, beat):
    if not isinstance(reading, dict):
        return local
    act = reading.get('act')
    merged = dict(local)
    if act in {'answer', 'question', 'proposal', 'off_topic', 'agreement', 'refusal', 'confused'}:
        merged['detail'] = act
        if act == 'off_topic':
            merged['act'] = 'off_topic'
        elif act == 'confused':
            merged['act'] = 'confused_task'
    signals = reading.get('objectives_shown')
    if isinstance(signals, list):
        merged['signals'] = [s for s in signals if s in beat['objectives']]
    return merged


def _next_line(scene, lines):
    for line in lines:
        if line not in scene['used_lines']:
            scene['used_lines'].append(line)
            return line
    return None


def _direction(person, move, purpose=None, words=None, line=None, **extra):
    template, default_words = MOVES.get(move, ('', 30))
    return {**person, '_move': move, '_purpose': purpose or template, '_max_words': words or default_words, '_line': line, **extra}


def _available_facts(definition, scene, person_id):
    order = {beat['id']: index for index, beat in enumerate(definition['beats'])}
    facts = []
    for fact in definition['ledger']:
        if fact['owner'] not in {'public', person_id}:
            continue
        start = fact.get('available_from')
        if start is None or order.get(start, 0) <= scene['beat']:
            facts.append(fact)
    return facts


def visible_facts(definition, scene, person_id):
    return [fact['text'] for fact in _available_facts(definition, scene, person_id)]


def _people(definition):
    return [p for p in definition['participants'] if p['kind'] == 'ai']


def _choose_speaker(definition, state, scene, text, history):
    people = _people(definition)
    by_id = {p['id']: p for p in people}
    addressed = state.get('addressed') or []
    explicit = [by_id[pid] for pid in addressed if pid in by_id]
    if not explicit:
        # The last sentence decides: "So Alex needs notice. Maya, what do you need?" is for Maya.
        lowered = text.casefold()
        told_to_start = [p for p in people if re.search(rf"\b{re.escape(p['name'].casefold())}\b[,\s]+(?:please\s+)?(?:go ahead|go first|you first|start|begin|first)\b", lowered)]
        told_to_wait = {p['id'] for p in people if re.search(rf"\b{re.escape(p['name'].casefold())}\b[,\s]+(?:please\s+)?(?:hold on|wait|you are next|you're next|next)\b", lowered)}
        if told_to_start:
            return told_to_start[:1], True
        sentences = [part for part in re.split(r'(?<=[.!?])\s+', lowered) if part.strip()]
        for sentence in reversed(sentences):
            # "Alex will redo the rota" talks about Alex. It does not ask Alex anything.
            explicit = [p for p in addressed_people(sentence, people) if p['id'] not in told_to_wait
                        and not re.search(rf"\b{re.escape(p['name'].casefold())}\s+(?:will|would|can|should|needs?|wants?|gets?|has|had|does|redoes|takes|owns|sends|may|might|must)\b", sentence)]
            if explicit:
                break
    if explicit:
        return explicit, True
    words = set(re.findall(r'\w+', text.casefold()))
    scored = sorted(people, key=lambda p: len(words & {t.casefold() for t in p.get('topics', [])}), reverse=True)
    if len(people) > 1 and len(words & {t.casefold() for t in scored[0].get('topics', [])}) > len(words & {t.casefold() for t in scored[1].get('topics', [])}):
        return [scored[0]], False
    question = state.get('responding_to') or {}
    if question.get('participant_id') in by_id:
        return [by_id[question['participant_id']]], False
    return [by_id[definition['beats'][scene['beat']]['driver']]], False


def _coach_due(scene):
    return scene['confusion'] >= 3


def direct(definition, state, reading, history):
    """Advance the scene for one learner turn and return who speaks and how."""
    scene = state['scene']
    beats = definition['beats']
    text = state.get('latest_input', '')
    act = reading.get('act', 'substantive')
    if act in {'substantive', 'question'} and is_off_topic(definition, text, [h.get('text', '') for h in history[-4:]]):
        act = 'off_topic'
    scene['read'] = act
    people = {p['id']: p for p in _people(definition)}
    beat = beats[scene['beat']]
    level = definition.get('level', 'intermediate')
    cap = LEVEL_WORD_CAP.get(level, 45)
    last_speaker = next((h['participant_id'] for h in reversed(history) if h.get('participant_id') in people), beat['driver'])

    def finish(directions):
        for item in directions:
            item['_max_words'] = min(item.get('_max_words', 30), cap)
            scene['moves'] = (scene['moves'] + [item['_move']])[-20:]
        state['directions'] = [{k: v for k, v in item.items()} for item in directions]
        return directions

    # Confusion is a signal about the learner, never scene content.
    # Asking for clarification is itself the skill in some stages (L6), not a failure.
    if act == 'confused_line' and any(re.search(pattern, text, re.I) for pattern in beat['signals']):
        act = scene['read'] = 'substantive'
    if act in {'confused_task', 'confused_line'}:
        scene['confusion'] += 1
        if act == 'confused_line' and scene['confusion'] == 1:
            return finish([_direction(people[last_speaker], 'rephrase_simple')])
        driver = people[beat['driver']]
        if scene['confusion'] == 1 or (act == 'confused_line' and scene['confusion'] == 2):
            return finish([_direction(driver, 'orient', line=beat['orient'], _authored=True)])
        if not _coach_due(scene):
            # Saying the same thing louder does not help: offer one smaller step instead.
            _, _, step = coach_note(definition, state, 2)
            return finish([_direction(driver, 'orient', line=f"Let's make it simple. {step}", _authored=True)])
        patience = _next_line(scene, ["No rush. Take a moment, and tell me when you're ready.", "It's fine, take your time. I'm listening.", "We can pause if you'd like. I'm happy to wait."]) or "I'm listening."
        return finish([_direction(driver, 'orient', line=patience, _authored=True, _call_coach=True)])

    if act == 'garbled':
        line = _next_line(scene, list(STOCK)) or STOCK[0]
        return finish([_direction(people[last_speaker], 'clarify', line=line, _authored=True)])

    if act == 'identity':
        chosen, _ = _choose_speaker(definition, state, scene, text, history)
        person = chosen[0]
        return finish([_direction(person, 'answer', line=f"I'm {person['name']}, the {person['role'].lower()}. {person['relationship']}.", _authored=True)])

    if act != 'ack':
        scene['confusion'] = 0

    if act == 'off_topic':
        # Going off the subject still counts as a turn, so the scene can never stall on it.
        scene['beat_turns'] += 1
        steer = _next_line(scene, beat['opportunity']) or beat['fallback'][0]
        return finish([_direction(people[beat['driver']], 'redirect', MOVES['redirect'][0].format(steer=steer), _fallback=steer)])

    # Provisional signals move the scene along; evidence review decides credit.
    shown = list(reading.get('signals') or [])
    pattern_hit = any(re.search(pattern, text, re.I) for pattern in beat['signals'])
    if pattern_hit:
        shown += [oid for oid in beat['objectives'] if oid not in shown]
    scene['signals'] = sorted(set(scene['signals']) | set(shown))
    scene['beat_turns'] += 1

    # Bargaining positions are decided here, whatever the current stage.
    case = definition.get('negotiation')
    bargaining = None
    if case and 'negotiation' in scene:
        bargaining = decide_negotiation(case, scene['negotiation'], text, state.get('preferences', {}).get('challenge', 'intermediate'),
                                        (state.get('responding_to') or {}).get('text', ''))
        if bargaining:
            apply_negotiation(scene['negotiation'], bargaining)
            if bargaining['action'] in {'accept', 'respect_no_deal', 'impasse'}:
                scene['beat'] = len(beats) - 1
                scene['beat_turns'] = 0
            elif scene['beat'] == 0:
                scene['beat'] = min(1, len(beats) - 1)
                scene['beat_turns'] = 0
            speaker = next(p for p in _people(definition) if p.get('can_finalize')) if any(p.get('can_finalize') for p in _people(definition)) else people[beats[scene['beat']]['driver']]
            state['ledger_action'] = bargaining.get('ledger')
            exact = bargaining.get('exact')
            return finish([_direction(speaker, 'bargain', bargaining['purpose'], bargaining['max_words'], line=bargaining['fallback'] if exact else None, _authored=bool(exact),
                _authorised=bargaining['authorised'], _fallback=bargaining['fallback'], _bargain=bargaining['action'],
                _must_say=[bargaining['authorised'][1]] if bargaining['action'] == 'counter' else [])])

    chosen, directed = _choose_speaker(definition, state, scene, text, history)
    first = chosen[0]
    beat_done = bool(beat['objectives']) and set(beat['objectives']) <= set(scene['signals'])
    beat_done = beat_done or (not beat['objectives'] and pattern_hit)
    # A minimum length keeps a stage from being rushed past, but never holds back a learner
    # who has shown this stage and has already moved on to doing the next one.
    next_beat = beats[scene['beat'] + 1] if scene['beat'] + 1 < len(beats) else None
    ahead = bool(next_beat and next_beat['objectives'] and any(re.search(pattern, text, re.I) for pattern in next_beat['signals']))
    beat_done = beat_done and (scene['beat_turns'] >= beat.get('min_turns', 1) or ahead)
    is_question = act == 'question'
    directions = []

    # Advance when the stage goal has been shown, or when it has stalled: never loop.
    stalled = scene['beat_turns'] >= beat['stall_turns']
    if directed and not is_question and not (beat_done and scene['beat'] == len(beats) - 1):
        # The learner told someone to speak: that person speaks. The scene can move on next turn.
        return finish([_body_move(definition, state, scene, first, text, False, act, beat, directed=True)])
    if (beat_done or (stalled and not _next_unused(scene, beat))) and scene['beat'] < len(beats) - 1:
        scene['beat'] += 1
        scene['beat_turns'] = 0
        beat = beats[scene['beat']]
        while beat['objectives'] and any(re.search(pattern, text, re.I) for pattern in beat['signals']):
            scene['signals'] = sorted(set(scene['signals']) | set(beat['objectives']))
            if scene['beat'] == len(beats) - 1:
                scene['finished'] = True
                break
            scene['beat'] += 1
            beat = beats[scene['beat']]
        if scene['finished']:
            return finish([_direction(people[beat['driver']], 'wind_down', _fallback=definition.get('closing_line') or beat['fallback'][-1])])
        steer = _next_line(scene, beat['opportunity']) or beat['fallback'][0]
        driver = people[beat['driver']]
        if is_question:
            directions.append(_direction(first, 'answer', _fallback=beat['fallback'][0]))
            if first['id'] == driver['id']:
                directions[0]['_purpose'] += f' Then move things on with something meaning: {steer}'
        else:
            directions.append(_direction(driver, 'advance_beat', MOVES['advance_beat'][0].format(steer=f'Say something with this meaning: {steer}'), _fallback=steer))
    elif beat_done and scene['beat'] == len(beats) - 1:
        scene['finished'] = True
        directions.append(_direction(first, 'answer' if is_question else 'wind_down', _fallback=definition.get('closing_line') or beat['fallback'][-1]))
    elif stalled and not is_question:
        steer = _next_line(scene, beat['opportunity'])
        scene['beat_turns'] = 0
        if steer:
            directions.append(_direction(people[beat['driver']], 'create_opportunity', MOVES['create_opportunity'][0].format(steer=steer), _fallback=steer))
    if not directions:
        directions.append(_body_move(definition, state, scene, first, text, is_question, act, beat))

    # A second voice needs a reason. It never follows a very short or confused turn.
    long_enough = len(text.split()) >= 5
    if len(directions) == 1 and long_enough:
        collective = bool(COLLECTIVE.search(text))
        others = [p for p in _people(definition) if p['id'] != directions[0]['id']]
        if collective and others:
            directions.append(_direction(others[0], 'respond', 'They asked everyone. Give your own view briefly, without repeating the previous speaker.', 28))
        elif beat.get('second_speaker') and beat['id'] not in scene['second_done'] and beat['second_speaker'] != directions[0]['id']:
            scene['second_done'].append(beat['id'])
            directions.append(_direction(people[beat['second_speaker']], 'interject', line=beat['second_line'], _authored=True))
        elif len(chosen) > 1 and directed:
            directions.append(_direction(chosen[1], 'answer'))
    return finish(directions)


def _next_unused(scene, beat):
    return next((line for line in beat['opportunity'] if line not in scene['used_lines']), None)


def _body_move(definition, state, scene, person, text, is_question, act, beat, directed=False):
    fallback = next((line for line in beat['fallback'] if line not in scene['used_lines']), beat['fallback'][0])
    if is_question:
        return _direction(person, 'answer', _fallback=fallback)
    if act == 'ack':
        steer = _next_line(scene, beat['opportunity'])
        if steer:
            return _direction(person, 'create_opportunity', MOVES['create_opportunity'][0].format(steer=steer), _fallback=steer)
        return _direction(person, 'respond', _fallback=fallback)
    unrevealed = [f for f in _available_facts(definition, scene, person['id']) if f['owner'] == person['id'] and f['id'] not in scene['revealed']]
    if unrevealed and (directed or len(scene['moves']) % 2 == 0):
        fact = unrevealed[0]
        scene['revealed'].append(fact['id'])
        return _direction(person, 'reveal_fact', MOVES['reveal_fact'][0].format(fact=fact['text']), _fallback=fallback)
    words = len(text.split())
    challenge = state.get('preferences', {}).get('intensity', 'gentle')
    if words < 6:
        return _direction(person, 'probe', _fallback=fallback)
    if challenge != 'gentle' and 'push_back' not in scene['moves'][-2:]:
        return _direction(person, 'push_back', _fallback=fallback)
    return _direction(person, 'respond', _fallback=fallback)


def reopen_for_unmet(definition, state, met):
    """After the scene finishes, return to the first beat whose objective lacks evidence."""
    scene = state.get('scene')
    if not scene or not scene.get('finished'):
        return False
    for index, beat in enumerate(definition['beats']):
        if beat['objectives'] and not set(beat['objectives']) <= met and beat['id'] not in scene['reopened']:
            scene['reopened'].append(beat['id'])
            scene.update(beat=index, beat_turns=0, finished=False)
            scene['signals'] = [s for s in scene['signals'] if s in met]
            return True
    return False


_UNIT = r'(?:days?|weeks?|months?|hours?|minutes?|percent|%|seats?|people|persons?|usd|dollars?|thousand|million)'


def _figures(text):
    text = numeric_text(text)
    found = set()
    for match in re.finditer(rf'(?:usd\s*|\$)?(\d+(?:\.\d+)?)(\s*%|[ -]+(?:\w+[ -]+)?{_UNIT}\b)?', text, re.I):
        value = float(match.group(1))
        prefixed = re.match(r'(?:usd\s*|\$)', match.group(0), re.I)
        if value > 12 or prefixed or (match.group(2) and value > 1):
            found.add(value)
    return found


def _all_numbers(text):
    return {float(n) for n in re.findall(r'\d+(?:\.\d+)?', numeric_text(text))}


def check_sentence(definition, state, speaker, text, heard_text, own_previous):
    """Accept, repair or drop one generated sentence using data, not case-specific rules.

    Returns the sentence to speak, or '' to drop it.
    """
    text = re.sub(r'^\s*[A-Z][a-z]+:\s*', '', text).strip()
    text = re.sub(r'\b[Ll]earner\b,?\s*', '', text).strip()
    if not text or not re.search(r'\w', text):
        return ''
    if re.search(r'\b(stupid|idiot|making excuses|your grammar is|you should say)\b', text, re.I):
        return ''
    if re.search(r"\b(say so|ask them|tell them|confirm those complete terms|your (?:next )?line|in character|stage of the scene|as an ai|system prompt|my instructions)\b", text, re.I):
        return ''
    if speaker.get('_move') == 'wind_down' and '?' in text:
        return ''
    for pattern in definition.get('forbidden_claims', []):
        if re.search(pattern, text, re.I):
            return ''
    introduced = re.search(r"\b(?:my name is|I'm|I am)\s+([A-Z][a-z]+)\b", text)
    names = {p['name'] for p in definition['participants'] if p['kind'] == 'ai'} - {speaker['name']}
    if introduced and introduced.group(1) in names:
        return ''
    allowed = set(float(n) for n in speaker.get('_authorised', []) if isinstance(n, (int, float)))
    allowed |= _all_numbers(heard_text)
    for fact in visible_facts(definition, state['scene'], speaker['id']):
        allowed |= _all_numbers(fact)
    if _figures(text) - allowed:
        return ''
    # Numbers and order codes such as #A123456 that nobody supplied are invented details.
    for code in re.findall(r'#\s*[A-Z0-9-]*\d[A-Z0-9-]*', text):
        if code.replace('#', '').strip().casefold() not in heard_text.casefold():
            return ''
    case = definition.get('negotiation')
    if case and not any(o.get('status') == 'accepted' for o in state.get('offers', [])) and speaker.get('_bargain') != 'accept':
        if re.search(r"\b(we have a deal|deal is (?:done|final)|agreement is final|we have agreed|it's a deal|let'?s lock in)\b", text, re.I):
            return ''
    if speaker.get('_move') != 'rephrase_simple':
        normal = ' '.join(re.findall(r"[\w']+", text.casefold()))
        if text.rstrip().endswith('?') and any(normal == ' '.join(re.findall(r"[\w']+", question.casefold()))
                                               for line in own_previous for question in re.findall(r'[^.!?]*\?', line)):
            return ''
        if len(normal.split()) >= 5:
            for line in own_previous:
                for sentence in re.findall(r'[^.!?]+[.!?]?', line):
                    other = ' '.join(re.findall(r"[\w']+", sentence.casefold()))
                    if SequenceMatcher(None, normal, other).ratio() > .84:
                        return ''
    return text


def fallback_line(definition, state, speaker):
    """An authored line for when the model is out of quota or every sentence was dropped."""
    scene = state['scene']
    beat = definition['beats'][scene['beat']]
    preferred = speaker.get('_fallback')
    if preferred and preferred not in scene['used_lines']:
        scene['used_lines'].append(preferred)
        line = preferred
    else:
        line = _next_line(scene, beat['fallback']) or _next_line(scene, beat['opportunity']) or beat['orient']
    # A prepared line cannot answer a question, so it should not pretend that it has.
    return f'Let me come back to that. {line}' if speaker.get('_move') == 'answer' else line


def coach_note(definition, state, level):
    """Authored, objective-specific help for the current stage of the scene."""
    scene = state['scene']
    beat = definition['beats'][scene['beat']]
    evaluation = state.get('evaluation') or state.get('last_evaluation') or {}
    met = {c['objective_id'] for c in evaluation.get('criteria', []) if c.get('met')}
    target = next((oid for oid in beat['objectives'] if oid not in met), None)
    target = target or next((o['id'] for o in definition['objectives'] if o['id'] not in met), definition['objectives'][0]['id'])
    note = definition['expert_notes'][target]
    objective = next(o for o in definition['objectives'] if o['id'] == target)
    text = [note['micro_lesson'], f"Here is one way to say it. Adapt it, don't copy it: {note['model']}", note['smaller_step'],
            'You can try again, pause, or leave. Everything you have shown so far is saved.'][level]
    return target, objective['description'], text
