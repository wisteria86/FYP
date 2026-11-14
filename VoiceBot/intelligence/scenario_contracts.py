"""Prepare bounded fictional cases before speaking, not during an exchange."""
from domain.conversation import Participant, Objective, ScenarioDefinition
from intelligence.case_library import compile_case

NAMES = ['Alex', 'Maya', 'Sam', 'Robin', 'Jordan', 'Casey']


def compile_definition(preview):
    # A company case is built around the learner's own document, so the passage joins the facts.
    excerpts = preview.get('knowledge_evidence') or []
    extra = [{'id': f"doc{i}", 'text': f"The company document {item['name']} says: {item['text'][:700]}"} for i, item in enumerate(excerpts)]
    authored = compile_case(preview['activity_id'], preview.get('variant', 0), preview.get('difficulty'), extra)
    if authored:
        definition, shown = authored
        if preview.get('skill_id') != 'company-knowledge':
            preview['situation'] = shown['situation']
            preview['opening'] = shown['opening']
        preview['learner_role'] = shown['learner_role']
        preview['objectives'] = [o['description'] for o in definition['objectives']]
        preview['success_criteria'] = preview['objectives']
        preview['participant_specs'] = [{'id': p['id'], 'type': p['kind'], 'displayName': p['name'], 'role': p['role'], 'team': p['team']} for p in definition['participants']]
        preview['brief'] = definition['brief']
        # The opening speaker comes first among AI participants in the session record.
        opener = shown.get('opening_speaker')
        preview['participant_specs'].sort(key=lambda spec: 0 if spec['type'] == 'learner' else 1 if spec['id'] == opener else 2)
        return definition
    specs = preview['participant_specs']
    people = []
    sequence = preview.get('sequence_number')
    names = (['Maya', 'Alex', 'Sam', 'Robin'] if sequence == 2 else NAMES)
    offset = preview.get('variant', 0) % len(names)
    names = names[offset:] + names[:offset]
    if sequence == 27:
        names = ['Alex', 'Sam', 'Robin', 'Maya']
    ai_index = 0
    for index, spec in enumerate(specs):
        learner = spec.get('type') == 'learner'
        name = 'You' if learner else names[ai_index % len(names)]
        person = Participant(id=f'p{index}', name=name, role=spec.get('role', 'Learner'),
            kind='learner' if learner else 'ai', team=spec.get('team', 'participant'),
            goals=preview['objectives'] if learner else [f"Fulfil your role as {spec.get('role', 'partner')} in the supplied situation"],
            relationship=f"{spec.get('role', 'Learner')} in {preview['title']}", voice_index=ai_index,
            style='Patient and concise' if preview['difficulty'] == 'beginner' else 'Respectful; ask specific, relevant follow-ups')
        people.append(person)
        if not learner:
            ai_index += 1
        spec.update(id=person.id, displayName=name)
    design = preview.get('learning_design') or {}
    objectives = design.get('targets') or [{'name': x} for x in preview['objectives']]
    rubric = [Objective(id=f'o{i+1}', description=item['name'],
        evidence=f"The learner performs '{item['name']}' appropriately in this scene; a mention or promise is insufficient.",
        alternatives=['Accept equivalent paraphrases and culturally appropriate alternatives.']) for i, item in enumerate(objectives)]
    facts = [preview['situation']]
    actions = []
    unknown_quantities = []
    if sequence == 27:
        alex,sam = [p for p in people if p.kind=='ai'][:2]
        alex.role='Delivery coordinator'
        alex.relationship=f'Colleague of {sam.name}; affected by the unannounced plan change'
        alex.style='Direct and a little frustrated, but fair. Use everyday language, not corporate speeches.'
        alex.topics=['notice','agreement','communication','client','approval','plan']
        alex.goals=['Get advance notice and joint approval before changes affect other people; hear Sam out without abandoning this concern.']
        alex.initial_contribution='Explain that you had already arranged the team around the agreed plan. You did not change it. Ask Sam how changes will be discussed before they happen.'
        sam.role='Testing coordinator'
        sam.relationship=f'Colleague of {alex.name}; made the unannounced plan change'
        sam.style='Practical and initially defensive; own the communication mistake without giving a formal apology speech.'
        sam.topics=['testing','check','reason','changed','changing','schedule']
        sam.goals=['Keep a missing end-to-end check in the plan; agree a change process with Alex.']
        sam.initial_contribution='Explain your own reason for moving the internal review, acknowledge not telling Alex first, and discuss a workable change process.'
        facts=[
            'The learner is chairing a short meeting between two colleagues about changes to a shared project plan.',
            f'{sam.name} moved the internal review from Tuesday to Thursday after noticing the agreed plan left out an end-to-end test.',
            f'{sam.name} edited the shared plan before discussing the change with {alex.name}. {alex.name} did not change the plan.',
            f'{alex.name} had already arranged the team around Tuesday. The main disagreement is changing an agreed plan without notice, not opposition to testing.',
            'The duration of the missing test, the final delivery date and any spare schedule buffer have not been confirmed. Nobody can promise the change leaves delivery unaffected.',
            'There is no established security patch, vulnerability, data migration or new risk assessment in this case. Do not present any as a reason for the change.',
            'A revised review date and a rule for approving future changes are still open. The learner helps both colleagues reach a fair next step.',
        ]
        actions=[dict(id='changed-plan',participant_id=sam.id,description='moved the internal review from Tuesday to Thursday without discussing it first',
            reason='the agreed plan left out an end-to-end test',references=['plan','review','schedule','timeline'])]
        unknown_quantities=[dict(subject='test duration and schedule buffer',units=['minute','hour','day','week'],
            clarification="We haven't estimated the test time yet, so I can't say how much extra time we need.")]
        preview['situation']='Chair a meeting about Sam changing the agreed project plan without telling Alex. Hear both sides and agree how future changes will be approved.'
        preview['learner_role']='Meeting chair'
        preview['opening']=f"{sam.name} moved our review from Tuesday to Thursday without checking with me. I'd already arranged the team around Tuesday."
    if sequence == 20:
        facts = ['Plan a 90-minute onboarding workshop for 12 new colleagues next Friday.',
            'The workshop goal is for new colleagues to complete one basic product task independently and know where to ask for help.',
            'The meeting room is available from 09:00 to 11:00 and has one projector.',
            'The workshop must include a product demonstration, paired practice and questions. The agreed spending limit is USD 300.']
        preview['situation'] = 'You chair a planning meeting. Agree an agenda, task owners and preparation steps for the onboarding workshop.'
        ai = [p for p in people if p.kind=='ai']
        ai[0].role='Project coordinator';ai[0].topics=['goal','goals','accomplish','schedule','time','agenda','deadline']
        ai[0].initial_contribution='Propose an agenda that fits the room booking and gives new colleagues time to practise.'
        ai[1].role='Training facilitator';ai[1].topics=['tasks','demo','demonstration','practice','participants','plan','materials']
        ai[1].initial_contribution='Propose a short demonstration followed by paired practice; volunteer to prepare the demonstration.'
        for p in ai:p.goals=[p.initial_contribution]
        preview['opening']=f"I'm {ai[0].name}, the project coordinator, and {ai[1].name} is our training facilitator. We're planning a 90-minute onboarding workshop for 12 colleagues next Friday; let's agree what they should be able to do afterward."
    for p in people:
        if p.kind=='ai' and not p.initial_contribution:
            p.initial_contribution=f"Contribute the perspective of your role, {p.role}, using the supplied facts; ask for clarification only when a missing fact matters."
            p.topics=p.topics or (['scope','goal','decision','priority'] if p.voice_index==0 else ['risk','details','tasks','concerns','delivery'])
    negotiation = None
    if preview['skill_id'] == 'negotiation' or sequence == 24:
        outcomes = [
            ('Prepare justified targets, alternatives and walk-away limits','Private preparation with reasons; disclosure to the counterpart is not required.'),
            ('Discover and accurately summarize interests','Relevant questions and confirmation of actual priorities, not generic phrases.'),
            ('Evaluate feasible multi-issue offers','Use supplied benchmarks and rationale; explain when no feasible trade exists.'),
            ('Use conditional, disciplined concessions','Link a change to a requested return, or explain why further concessions would breach limits.'),
            ('Respect confidentiality and decision authority','Identify who can approve; do not fabricate evidence, authority or disclose private team limits.'),
            ('Close with executable terms or a justified no-deal decision','Mutually confirm price, scope, timing, responsibilities and approvals; or justify a respectful walk-away against the alternative.'),
        ]
        rubric = [Objective(id=f'n{i+1}',description=title,evidence=evidence,alternatives=['Accept equivalent wording and a well-justified no-deal outcome.']) for i,(title,evidence) in enumerate(outcomes)]
        no_zopa = preview.get('variant', 0) % 2 == 1
        negotiation = {
            'case': 'no_zopa' if no_zopa else 'multi_issue', 'currency': 'USD',
            'public': {'product': 'Fictional staff training package', 'seats': 20,
                'list_price': 12000, 'delivery_days': 30, 'support_months': 3,
                'benchmark': 'Fictional prior package: USD 11000, 20 seats, 30 days, 3 months support.',
                'terms_required': ['price', 'currency', 'seats', 'delivery_days', 'support_months']},
            'buyer': {'target': 8500 if no_zopa else 9500, 'maximum': 9000 if no_zopa else 11500,
                'alternative': 'A fictional alternative supplier offers 20 seats for USD 8500 in 45 days with 1 month support.',
                'priorities': ['20 seats', 'delivery within 30 days', 'affordable price']},
            'seller': {'minimum': 10500 if no_zopa else 10000, 'target': 12000,
                'alternative': 'Allocate capacity to another fictional customer.',
                'priorities': ['price', 'longer lead time', 'limited support']},
            'feasibility': {'minimum_delivery_days':21,'maximum_support_months':6,
                'rush_cost':1000,'extra_support_month_cost':500},
        }
        negotiation['public']['service_options'] = 'Delivery can be 21-45 days; support can be 1-6 months. Faster delivery and extended support cost more.'
        facts = ['The fictional staff training package covers 20 seats, lists at USD 12000, and includes delivery in 30 days and 3 months of support.',
            negotiation['public']['benchmark'], negotiation['public']['service_options'],
            'Benchmarks and business details are fictional simulation facts.']
        preview['situation'] = 'Negotiate a fictional staff training package: 20 seats, USD 12000 list price, delivery in 30 days, and 3 months support. Explore priorities and confirm executable terms or explain a justified no-deal decision.'
        for person in people:
            side = 'buyer' if person.kind == 'learner' or person.team == 'learner' else 'seller'
            person.party = side
            person.role = ('Purchasing lead' if person.kind=='learner' else 'Purchasing adviser') if side=='buyer' else ('Supplier representative' if person==next(p for p in people if p.kind=='ai' and p.team!='learner') else 'Supplier delivery specialist')
            person.relationship = f"Represent the {side} in this package negotiation"
            person.initial_contribution = f"Represent the {side}; respond to the actual proposed package, clarify ambiguous terms, and propose a feasible next step."
            person.private_knowledge = negotiation[side]
            person.goals = negotiation[side]['priorities']
            person.authority = 'Approve feasible terms for your party' if person.kind == 'learner' or person == next(p for p in people if p.kind == 'ai' and p.team != 'learner') else 'Recommend terms; final approval belongs to the party decision maker'
            person.can_finalize = person.authority.startswith('Approve')
        preview['opening'] = 'We are offering 20 training seats for USD 12000, delivered in 30 days with three months of support. What matters most to you?'
        preview['learner_role']='Purchasing lead'
    for spec,person in zip(specs,people):
        spec['role']=person.role
    opening_person = next((p for p in people if p.kind == 'ai' and p.team == 'opponent'), next(p for p in people if p.kind == 'ai'))
    # The opening is authored from identity, never used as a source of identity.
    if sequence == 1:
        preview['opening'] = f"Hi! I'm {opening_person.name}, your neighbour. What's your name?"
    elif sequence == 2:
        preview['opening'] = f"Hello, I'm {opening_person.name}, your new classmate. Could you tell me a little about yourself?"
    preview['situation'] += ' Participants: ' + '; '.join(f"{p.name} is the {p.role}" for p in people if p.kind == 'ai') + '.'
    for person in people:
        person.public_knowledge = facts
    return ScenarioDefinition(activity_id=preview['activity_id'], setting=preview['situation'], facts=facts,
        participants=people, objectives=rubric, examples=design.get('examples', []),
        prerequisites=['Understand the briefing; ask the coach for a model if needed.'], negotiation=negotiation, actions=actions,unknown_quantities=unknown_quantities).model_dump()


def learner_definition(definition):
    """Explicit projection: no counterpart private data in previews or session APIs."""
    if not definition:
        return None
    public = {key: definition[key] for key in ('version', 'activity_id', 'setting', 'facts', 'objectives', 'prerequisites', 'examples')}
    public['participants'] = [{key: p[key] for key in ('id', 'name', 'role', 'kind', 'team', 'relationship', 'authority', 'voice_index')} for p in definition['participants']]
    case = definition.get('negotiation')
    public['negotiation'] = {'public': case['public'], 'preparation_brief': case['buyer']} if case else None
    public['actions'] = definition.get('actions',[])
    public['unknown_quantities'] = definition.get('unknown_quantities',[])
    public['brief'] = definition.get('brief')
    public['archetype'] = definition.get('archetype')
    # The scene's steps for the live track: ids and objective ids only. Beat goals, signals and
    # authored lines are written from the characters' side and stay private.
    public['beats'] = [{'id': beat['id'], 'objectives': list(beat.get('objectives', []))} for beat in definition.get('beats', [])]
    return public
