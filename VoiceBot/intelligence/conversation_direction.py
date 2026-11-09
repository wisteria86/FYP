"""Local floor decisions and bounded replies; no extra provider call to select a speaker."""
import re


def addressed_people(text, people):
    """Recognize vocatives, not third-person mentions (including punctuation-free ASR)."""
    text = text.casefold().strip()
    found = []
    for person in people:
        name = re.escape(person['name'].casefold())
        # 'Okay Sam ...', 'Thanks, Sam ...', 'Could you explain, Sam?',
        # 'Sam why ...', 'let Sam explain'. 'Why did Sam ...' is a mention.
        patterns = [
            rf'^(?:(?:okay|ok|well|hey|hi|hello|thanks|thank you|sorry|right|so|please)[,\s]+)*{name}\b(?!\s+(?:said|says|thinks|told|has|keeps|changed|is|was)\b)',
            rf'\b(?:ask|let)\s+{name}\b',
            rf'[,!?]\s*{name}\s*[,!?]\s*(?:can|could|would|will|why|what|how|tell|do|did|are|please)\b',
            rf'\b(?:you|your)\b[^.!?]*\b{name}\s*[.!?]*$',
            rf'\b(?:tell|explain|go ahead|over to)\b[^.!?]*\b{name}\s*[.!?]*$',
        ]
        if re.search(rf'\b(?:about|with|from|of)\s+{name}\s*[.!?]*$',text) and not re.search(rf',\s*{name}\s*[.!?]*$',text):continue
        if any(re.search(pattern, text) for pattern in patterns):found.append(person)
    return found


def is_followup(text):
    return bool(re.search(r"\b(tell me more|tell me about (?:it|this|that)|more about|explain|what.*talking about|why did you|why did (?:that|they)|what do you mean|say that again|repeat|go on)\b",text,re.I))


def action_owner(definition, text):
    """Resolve a consequential action only from authored, ID-bound ownership."""
    if not re.search(r'\b(why|who|did|changed|changing|change|moved|moving|do it|done)\b',text,re.I):return None
    actions=definition.get('actions',[])
    matched=[a for a in actions if any(re.search(r'\b'+re.escape(k)+r'\b',text,re.I) for k in a.get('references',[]))]
    if not matched and re.search(r'\b(?:why did you|why did that|why.*do it)\b',text,re.I) and len(actions)==1:matched=actions
    owners={a['participant_id'] for a in matched}
    return next(iter(owners)) if len(owners)==1 else None


def choose_speakers(definition, state, history):
    people = [p for p in definition['participants'] if p['kind'] == 'ai']
    text = state.get('latest_input', '').casefold()
    addressed = state.get('addressed', [])
    explicit = [p for p in people if p['id'] in addressed]
    if not explicit:explicit = addressed_people(text,people)
    if explicit:
        if len({p['name'].casefold() for p in explicit})<len(explicit) and not addressed:
            return [{**explicit[0], '_purpose':'Two participants share that name. Ask which role the learner means; do not answer the substantive question.', '_ambiguous':True}]
        return [{**p, '_directed': True, '_purpose': 'Respond to the learner who addressed you.'} for p in explicit[:2]]
    spoken = [h['participant_id'] for h in history if h.get('participant_id') in {p['id'] for p in people}]
    last = spoken[-1] if spoken else people[0]['id']
    others = [p for p in people if p['id'] != last]
    if others and re.search(r'\b(other (?:person|participant|speaker|colleague|one)|someone else|they (?:will|can|should)|let them)\b', text):
        return [{**others[0], '_directed': True, '_purpose': 'The learner invited you to contribute. Supply the details you own; do not ask the learner to invent them.'}]
    owner=action_owner(definition,text)
    if owner in {p['id'] for p in people}:
        return [{**next(p for p in people if p['id']==owner), '_purpose':'Answer for your own action. If the learner repeats why, address the decision or communication concern behind it instead of repeating dates and the same justification. Distinguish your reason from whether you handled the change properly. Do not invent another cause.'}]
    focus=next((p for p in people if p['id']==state.get('conversation_focus')),None)
    if is_followup(text):
        person=focus or next(p for p in people if p['id']==last)
        return [{**person,'_purpose':'Continue the same conversation. Explain the specific point in simpler words; do not repeat your previous sentences or invent new details.'}]
    question = state.get('responding_to') or state.get('pending_question') or {}
    invited=addressed_people(question.get('text',''),[p for p in people if p['id']!=question.get('participant_id')])
    acknowledgement=bool(re.fullmatch(r'(?:okay|ok|yes|right|sure|go on|uh huh)[.! ]*',text))
    if invited and acknowledgement:
        return [{**invited[0], '_purpose':'Answer the question your colleague just addressed to you. The learner has yielded space; do not ask them to answer for you.'}]
    if acknowledgement and others:
        return [{**others[0], '_purpose':'React briefly to the previous point from your own perspective. Add one unresolved concern or a practical next step, without inventing agreement or asking the learner to repeat facts.'}]
    words = set(re.findall(r'\w+', text))
    scores = {p['id']: len(words & set(p.get('topics', []))) for p in people}
    relevant = max(people, key=lambda p: scores[p['id']])
    first = relevant if scores[relevant['id']] else next((p for p in people if p['id']==question.get('participant_id')), focus or next(p for p in people if p['id']==last))
    unsure = bool(re.search(r"\b(not (?:really )?(?:that )?(?:sure|certain)|don't know|do not know|what (?:plan|goal)|what.*accomplish)\b", text))
    if unsure and others:
        first = next((p for p in others if p.get('initial_contribution')), others[0])
    selected = [{**first, '_purpose': 'Explain your part of the shared case and respond to the learner.'}]
    # A previously unheard stakeholder contributes their assigned concern at an
    # open invitation. Participation is tied to the scene, never a turn modulo.
    invitation = bool(re.search(r'\b(everyone|both|each|views|plan|goal|priority|priorities|consider|accomplish)\b', text))
    collective=bool(re.search(r'\b(everyone|both|each|you two)\b',text))
    second = next((p for p in people if p['id']!=first['id'] and (collective or p['id'] not in spoken)), None)
    if second and invitation and not unsure:
        selected.append({**second, '_purpose': 'Briefly add your distinct concern or proposal, reacting to the preceding speaker. Do not restate their contribution. Leave the decision with the learner.'})
    return selected


def reply_handoff(definition, speaker, text, history=()):
    """A named question belongs to that colleague, not automatically to the learner."""
    others=[p for p in definition['participants'] if p['kind']=='ai' and p['id']!=speaker['id']]
    questions=re.findall(r'[^.!?]*\?',text)
    invited=addressed_people(questions[-1],others) if questions else []
    if questions and not invited:invited=addressed_people(text,others)
    if len(invited)==1:
        return {**invited[0], '_purpose':f"Answer {speaker['name']}'s just-spoken question directly in one short contribution. Speak to that colleague; then leave room for the learner."}
    # A directly affected colleague can react to the first explanation of an
    # authored action, without being forced to speak after every learner turn.
    own_actions=[a for a in definition.get('actions',[]) if a['participant_id']==speaker['id']]
    if own_actions and re.search(r"\bI (?:moved|changed|adjusted)\b",text,re.I):
        affected=next((p for p in others if re.search(r'\b'+re.escape(p['name'])+r'\b',text,re.I)
            and sum(h['participant_id']==p['id'] for h in history)<=1),None)
        if affected:
            return {**affected,'_purpose':f"React briefly to {speaker['name']}'s explanation because it affects your work. State your distinct concern directly to them in one sentence; do not interview the learner."}
    return None


def proactive_reaction(definition, state, speaker, text, history, planning=False):
    """Give an affected or quiet colleague space after a substantive contribution.

    This is a reaction to actual content, not a fixed speaker rotation. It is
    considered only after the selected speaker has answered the learner.
    """
    others=[p for p in definition['participants'] if p['kind']=='ai' and p['id']!=speaker['id']]
    if not others or speaker.get('_ambiguous') or (state.get('completed') and not state.get('extra_practice')):return None
    latest=state.get('latest_input','')
    # Personal questions and communication repair deserve an uninterrupted answer.
    if re.search(r'\b(who are you|your name|introduce yourself|repeat|say (?:that|it) again|what do you mean|what.*talking about|only you|just you|let .* finish|one at a time)\b',latest,re.I):return None
    if re.search(r'\b(what do you mean|could you (?:clarify|repeat)|didn.t (?:catch|understand)|which part|are you asking|before you.ve finished)\b',text,re.I):return None
    if not planning and len(re.findall(r'\w+',text))<8:return None
    words=set(re.findall(r'\w+',latest.casefold()+' '+text.casefold()))
    stop={'the','and','that','with','your','this','from','have','will','what','would','could','should','about','before','after','their','them','they','into','only','first','using','supplied','facts','role','situation'}
    def score(person):
        concerns=' '.join(person.get('topics',[])+person.get('goals',[])+[person['role']])
        relevant={w for w in re.findall(r'\w+',concerns.casefold()) if len(w)>3 and w not in stop}
        overlap=len(words & relevant)
        last=next((i for i in range(len(history)-1,-1,-1) if history[i]['participant_id']==person['id']),-1)
        quiet=min(12,len(history)-last)
        # Relevance breaks ordinary ties, but cannot permanently silence a
        # colleague whose remit uses different vocabulary from the main topic.
        return quiet>=6,2*min(overlap,4)+quiet,quiet
    person=max(others,key=score)
    return {**person,'_brief':True,'_purpose':
        f"Join the exchange now, speaking directly to {speaker['name']} about their last point. "
        'Add one distinct concern, trade-off, practical suggestion or relevant question from your own role. '
        'Do not echo agreement or repeat what was already said. Lead with what you can add or do, not what the other person already said. '
        'Use one or two short sentences for one point; a question, if needed, belongs to your colleague, not automatically to the learner. Then yield to the learner.'}


_UNITS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
_TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))


def numeric_text(text):
    """Normalize spoken numbers without changing or storing the ASR transcript."""
    words = set(_UNITS)|set(_TENS)|{'hundred','thousand','million','and'}
    pattern = r'\b(?:'+ '|'.join(sorted(words,key=len,reverse=True))+r')(?:[ -]+(?:'+ '|'.join(sorted(words,key=len,reverse=True))+r'))*\b'
    def number(match):
        phrase = match.group().split()
        if all(w=='and' for w in phrase):return match.group()
        total = current = 0
        for word in re.split(r'[ -]+',match.group()):
            if word in _UNITS:current += _UNITS[word]
            elif word in _TENS:current += _TENS[word]
            elif word=='hundred':current = max(1,current)*100
            elif word in {'thousand','million'}:total += max(1,current)*({'thousand':1000,'million':1000000}[word]);current=0
        return str(total+current)
    return re.sub(pattern,number,text.casefold()).replace(',','')


def grounded_reply(definition, state, speaker):
    """Only reply locally when identity or explicit package facts determine the answer.

    This never grants semantic achievement or records a binding agreement.
    """
    text = state.get('latest_input','')
    if speaker.get('_ambiguous'):
        matches=[p for p in definition['participants'] if p['kind']=='ai' and p['name']==speaker['name']]
        return 'Do you mean '+ ' or '.join(p['role'].lower() for p in matches)+'?'
    if re.search(r'\b(who (?:are|is) you|who are you|your (?:name|role)|introduce yourself)\b',text,re.I):
        return f"I'm {speaker['name']}, the {speaker['role'].lower()}. " + (
            "I represent the supplier, and you're buying training for your team." if speaker.get('party')=='seller'
            else "I'm here to discuss the situation with you.")
    if re.search(r'\bif i (?:do|did|take|try) (?:this|that)\s*[.!?]*$',text,re.I):
        return "What action are you considering? I don't want to assume you've agreed before you've finished explaining."
    if definition['activity_id']=='english-20' and any('basic product task' in fact for fact in definition['facts']) and re.search(r'\b(?:accomplish|achieve|goal|purpose)\b',text,re.I):
        return "The goal is for each new colleague to complete one basic product task independently and know where to ask for help. We can check that during the paired practice."
    if definition['activity_id']=='english-20' and len(definition.get('facts',[]))>1 and re.search(r'\b(other (?:person|participant)|they (?:will|can)|let them)\b',text,re.I):
        if speaker['role']=='Training facilitator':
            return "I suggest a 20-minute demonstration followed by 40 minutes of paired practice. I can prepare those materials; that leaves 30 minutes for introductions and questions."
        if speaker['role']=='Project coordinator':
            return "My proposed agenda is 15 minutes of introductions, 20 for the demonstration, 40 for paired practice and 15 for questions. I can arrange the room and circulate the agenda."
    case = definition.get('negotiation')
    if not case or speaker.get('party')!='seller':return None
    responding_to=(state.get('responding_to') or {}).get('text','')
    if re.fullmatch(r'(?:yes|yes[, ]+(?:i can|i am|i would|please)|sure|okay)[.! ]*',text.strip(),re.I) and re.search(r'\bor\b',responding_to,re.I):
        return "Do you mean you'd like the quoted package, or that you'd like to change its terms? Let's confirm the package before either of us commits."
    if re.fullmatch(r'(?:yes|yes[, ]+(?:i can|i am|i would|please)|sure|okay)[.! ]*',text.strip(),re.I) and re.search(r'\b(trade|willing|open|discuss|closer)\b',responding_to,re.I):
        public=case['public'];floor=speaker.get('private_knowledge',{}).get('minimum')
        if floor and speaker.get('can_finalize'):
            return f"Let's compare a concrete option: I can offer {public['seats']} seats, delivery in {public['delivery_days']} days and {public['support_months']} months of support for USD {floor:,.0f}. Would you prefer that package or the alternative you mentioned?"
    numeric = numeric_text(text)
    seats = re.search(r'\b(\d+)\s+(seats?|seeds?)\b',numeric)
    public = case['public']
    if seats and int(seats.group(1)) != public['seats'] and not re.search(r'\b(alternative|other supplier|competitor)\b',text,re.I):
        return f"Are you asking to buy {seats.group(1)} seats? Our current quote covers {public['seats']} seats; we would need a separate quote for a different group size."
    price = re.search(r'\b(?:for|at|offer|pay|price of)\s+(?:usd\s*|\$)?(\d+(?:\.\d+)?)\b',numeric)
    if not price or re.search(r'\b(alternative|other supplier|competitor|not|cannot|wouldn.t|example)\b',numeric):return None
    amount = float(price.group(1))
    if amount < 100 or any(word in numeric for word in ('if ', 'support', 'delivery', 'days')):return None
    own = speaker.get('private_knowledge', {})
    floor = own.get('minimum')
    if floor is None:return None
    package = f"{public['seats']} seats, delivery in {public['delivery_days']} days and {public['support_months']} months of support"
    if amount >= floor and speaker.get('can_finalize'):
        return f"USD {amount:,.0f} works for the quoted package. Are you proposing that price for {package}?"
    counter = max(floor, public['list_price']-1000)
    return f"I can't offer the quoted package at USD {amount:,.0f}. I can propose USD {counter:,.0f} for {package}; how does that compare with your priorities?"
