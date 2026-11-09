"""The scene engine's guarantees, checked without a model or any network access."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.training_service import TrainingService
from domain.conversation import ScenarioDefinition
from intelligence.case_library import available_cases, compile_case, variant_count
from intelligence import negotiation_strategy as strategy, scene_director as director
from scripts.conversation_eval.metrics import evaluate, failed_gates, is_confused
from scripts.conversation_eval.personas import STRONG
from scripts.conversation_eval.run import run_case, SKILLS
from services.training_orchestrator import TrainingOrchestrator
from api.schemas import RoleplayTurn


class PlainProvider:
    """A well-behaved model: says something short that adds no invented facts."""
    def generate_contextual_response(self, prompt):
        yield 'I hear you, and I have a point of my own here.'


class TestCasePacks(unittest.TestCase):
    def test_every_pack_and_variant_is_valid(self):
        self.assertGreaterEqual(len(available_cases()), 4)
        for activity in available_cases():
            for variant in range(variant_count(activity)):
                definition, shown = compile_case(activity, variant)
                self.assertEqual(definition['version'], 3)
                self.assertTrue(shown['opening'])

    def test_pack_rejects_generic_character_and_stage_directions(self):
        definition, _ = compile_case('english-19')
        person = next(p for p in definition['participants'] if p['kind'] == 'ai')
        person['card']['want'] = 'Fulfil your role as Customer in the supplied situation'
        with self.assertRaises(ValueError):
            ScenarioDefinition(**definition)
        definition, _ = compile_case('english-19')
        definition['ledger'][0]['text'] = 'Practice focus: comprehension.'
        with self.assertRaises(ValueError):
            ScenarioDefinition(**definition)

    def test_pack_rejects_a_limit_written_into_a_readable_fact(self):
        definition, _ = compile_case('activity-negotiation', 0)
        definition['ledger'][0]['text'] = 'The supplier will not go below USD 10000.'
        with self.assertRaises(ValueError):
            ScenarioDefinition(**definition)

    def test_case_facts_contain_no_stage_directions(self):
        for activity in available_cases():
            definition, _ = compile_case(activity)
            self.assertFalse(any('Practice focus' in fact for fact in definition['facts']))


class TestDirector(unittest.TestCase):
    def state(self, activity='english-28', variant=0, **extra):
        definition, _ = compile_case(activity, variant)
        return definition, {'scene': director.new_scene(definition), 'preferences': {'intensity': 'gentle', 'challenge': 'intermediate'},
                            'latest_input': '', 'addressed': [], 'offers': [], **extra}

    def turn(self, definition, state, text, history=()):
        state['latest_input'] = text
        return director.direct(definition, state, director.read_local(text), list(history))

    def test_reading_recognises_confusion_fragments_and_short_real_answers(self):
        self.assertEqual(director.read_local('And what am I supposed to tell you')['act'], 'confused_task')
        self.assertEqual(director.read_local('I do not understand')['act'], 'confused_task')
        self.assertEqual(director.read_local('What do you mean?')['act'], 'confused_line')
        self.assertEqual(director.read_local('Zap zap')['act'], 'garbled')
        self.assertEqual(director.read_local('What are')['act'], 'garbled')
        self.assertEqual(director.read_local('Abdul')['act'], 'substantive')
        self.assertEqual(director.read_local('Okay')['act'], 'ack')
        self.assertEqual(director.read_local('Who are you?')['act'], 'identity')

    def test_task_confusion_gets_an_authored_orientation_from_one_speaker(self):
        definition, state = self.state()
        directions = self.turn(definition, state, 'What is even happening here')
        self.assertEqual(len(directions), 1)
        self.assertEqual(directions[0]['_move'], 'orient')
        self.assertIn('chair', directions[0]['_line'].lower())

    def test_third_confusion_calls_the_coach_and_substance_resets_it(self):
        definition, state = self.state()
        for _ in range(2):
            self.assertFalse(self.turn(definition, state, 'I do not understand')[0].get('_call_coach'))
        self.assertTrue(self.turn(definition, state, 'I do not understand')[0].get('_call_coach'))
        self.turn(definition, state, 'The purpose of this meeting is to hear your concerns.')
        self.assertEqual(state['scene']['confusion'], 0)

    def test_unclear_line_is_rephrased_by_the_person_who_said_it(self):
        definition, state = self.state()
        history = [{'participant_id': 'p2', 'text': 'A regression run takes a full day.'}]
        directions = self.turn(definition, state, 'What do you mean?', history)
        self.assertEqual(directions[0]['id'], 'p2')
        self.assertEqual(directions[0]['_move'], 'rephrase_simple')

    def test_floor_stays_with_the_learner_after_short_or_confused_turns(self):
        definition, state = self.state()
        for line in ('I do not understand', 'Okay', 'Zap zap', 'Yes', 'Who should start'):
            self.assertEqual(len(self.turn(definition, state, line)), 1, line)

    def test_shown_objective_moves_the_scene_on(self):
        definition, state = self.state()
        directions = self.turn(definition, state, 'The purpose of this meeting is to hear your concerns.')
        self.assertEqual(state['scene']['beat'], 1)
        self.assertEqual(directions[0]['_move'], 'advance_beat')

    def test_a_stalled_scene_uses_each_prompt_once_then_moves_on_rather_than_looping(self):
        definition, state = self.state()
        steers = []
        for _ in range(12):
            directions = self.turn(definition, state, 'I think that this is quite a difficult situation for us')
            steers.append(directions[0].get('_fallback'))
            if state['scene']['beat'] > 0:
                break
        self.assertGreater(state['scene']['beat'], 0)
        used = state['scene']['used_lines']
        self.assertEqual(len(used), len(set(used)))

    def test_second_speaker_comes_from_the_beat_only_once(self):
        definition, state = self.state()
        first = self.turn(definition, state, 'The purpose of this meeting is to hear your concerns.')
        self.assertEqual([d['id'] for d in first], ['p1', 'p2'])
        self.assertEqual(first[1]['_move'], 'interject')
        second = self.turn(definition, state, 'I would like to think carefully about the other matters here too')
        self.assertEqual(len(second), 1)

    def test_an_answer_that_covers_the_next_stage_is_not_asked_for_again(self):
        definition, state = self.state('english-22')
        state['scene'].update(beat=1, signals=['o2'], beat_turns=1)
        directions = self.turn(definition, state, 'Complaints fell by 30 percent in three months, as the ticket system measured.')
        self.assertTrue(state['scene']['finished'])
        self.assertEqual(directions[0]['_move'], 'wind_down')

    def test_off_topic_is_recognised_locally_without_flagging_real_answers(self):
        definition, _ = self.state('english-27')
        self.assertTrue(director.is_off_topic(definition, 'My cat is very funny and fluffy.', []))
        self.assertFalse(director.is_off_topic(definition, 'It sounds like you both want a reliable release.', ['We need a reliable release']))
        self.assertFalse(director.is_off_topic(definition, 'Hello', []))
        self.assertFalse(director.is_off_topic(definition, 'I think this is quite a difficult situation for us', []))
        interview, _ = self.state('english-22')
        self.assertFalse(director.is_off_topic(interview, 'Our warehouse robots kept jamming on the conveyor.', []))
        deal, _ = self.state('activity-negotiation')
        self.assertFalse(director.is_off_topic(deal, 'Okay I will take it for ten thousand', []))

    def test_a_stage_minimum_never_holds_back_a_learner_who_has_moved_on(self):
        definition, state = self.state()
        state['scene'].update(beat=1, signals=['o2'], beat_turns=1)
        directions = self.turn(definition, state, 'We will start two weeks later, and Alex will redo the rota by next Friday.')
        self.assertTrue(state['scene']['finished'])
        self.assertEqual(directions[0]['_move'], 'wind_down')
        definition, state = self.state()
        state['scene'].update(beat=1, signals=['o2'], beat_turns=1)
        self.turn(definition, state, 'I would like to think carefully about the other matters here too')
        self.assertEqual(state['scene']['beat'], 1, 'Without moving on, the minimum still applies')

    def test_talking_about_someone_is_not_addressing_them(self):
        definition, state = self.state()
        state['scene'].update(beat=1, signals=['o2'], beat_turns=2)
        directions = self.turn(definition, state, 'We will start two weeks later. Alex will redo the rota by next Friday, and Maya will get one extra person.')
        self.assertTrue(state['scene']['finished'])
        self.assertEqual(directions[0]['_move'], 'wind_down')

    def test_clarifying_counts_as_the_skill_where_the_stage_teaches_it(self):
        definition, state = self.state('english-10')
        state['scene'].update(beat=1)
        self.turn(definition, state, 'What do you mean? Could you say that again?')
        self.assertEqual(state['scene']['confusion'], 0)
        self.assertIn('o2', state['scene']['signals'])

    def test_named_person_answers(self):
        definition, state = self.state()
        directions = self.turn(definition, state, 'Maya, what do you need for testing?')
        self.assertEqual(directions[0]['id'], 'p2')

    def test_the_person_told_to_go_ahead_speaks_not_the_one_told_to_wait(self):
        definition, state = self.state()
        self.turn(definition, state, 'The purpose of this meeting is to hear your concerns.')
        directions = self.turn(definition, state, 'Alex, go ahead with your concern first. Maya, you are next, so hold on a moment.')
        self.assertEqual([d['id'] for d in directions], ['p1'])
        self.assertEqual(state['scene']['beat'], 1, 'A rich discussion stage needs more than one turn')

    def test_winding_down_never_asks_and_stage_directions_are_never_spoken(self):
        definition, state = self.state('english-19')
        customer = next(p for p in definition['participants'] if p['kind'] == 'ai')
        calm = {**customer, '_move': 'wind_down'}
        self.assertEqual(director.check_sentence(definition, state, calm, 'And when exactly will that happen?', '', []), '')
        talking = {**customer, '_move': 'respond'}
        self.assertEqual(director.check_sentence(definition, state, talking, 'Say so, and ask them to confirm those complete terms.', '', []), '')

    def test_the_last_sentence_decides_who_is_being_asked(self):
        definition, state = self.state()
        directions = self.turn(definition, state, 'So Alex needs two weeks of notice. Maya, what do you need for testing?')
        self.assertEqual(directions[0]['id'], 'p2')

    def test_confusion_help_changes_each_time_instead_of_repeating(self):
        definition, state = self.state()
        lines = [self.turn(definition, state, 'I do not understand')[0]['_line'] for _ in range(4)]
        self.assertEqual(len(lines), len(set(lines)))

    def test_private_fact_is_visible_only_to_its_owner_and_from_its_stage(self):
        definition, state = self.state('english-19')
        customer = next(p for p in definition['participants'] if p['kind'] == 'ai')
        need = next(f['text'] for f in definition['ledger'] if f['id'] == 'f4')
        self.assertNotIn(need, director.visible_facts(definition, state['scene'], customer['id']))
        state['scene']['beat'] = 1
        self.assertIn(need, director.visible_facts(definition, state['scene'], customer['id']))
        definition, state = self.state()
        alex = next(f['text'] for f in definition['ledger'] if f['owner'] == 'p1')
        self.assertNotIn(alex, director.visible_facts(definition, state['scene'], 'p2'))

    def test_unsupported_figures_codes_and_labels_are_dropped(self):
        definition, state = self.state('english-19')
        customer = next(p for p in definition['participants'] if p['kind'] == 'ai')
        speaker = {**customer, '_move': 'respond'}
        check = lambda text, heard='': director.check_sentence(definition, state, speaker, text, heard, [])
        self.assertEqual(check('It will take 14 days to fix this.'), '')
        self.assertEqual(check('My order number is #A123456.'), '')
        self.assertEqual(check('My order is on hold.'), 'My order is on hold.')
        self.assertEqual(check('You said it takes 14 days.', 'It takes 14 days.'), 'You said it takes 14 days.')
        self.assertNotIn('Learner', check('Learner, could you clarify that for me?'))
        self.assertEqual(check('Dana: I want a refund.'), 'I want a refund.')

    def test_exact_repeated_question_is_dropped_but_a_rephrase_may_repeat(self):
        definition, state = self.state('english-19')
        customer = next(p for p in definition['participants'] if p['kind'] == 'ai')
        said = ['So what happens now, and when exactly?']
        self.assertEqual(director.check_sentence(definition, state, {**customer, '_move': 'respond'}, said[0], '', said), '')
        self.assertTrue(director.check_sentence(definition, state, {**customer, '_move': 'rephrase_simple'}, said[0], '', said))


class TestNegotiationStrategy(unittest.TestCase):
    def play(self, lines, variant=0, challenge='intermediate'):
        definition, _ = compile_case('activity-negotiation', variant)
        case = definition['negotiation']
        neg = strategy.new_state(case)
        results = []
        for line in lines:
            decision = strategy.decide(case, neg, line, challenge)
            if decision:
                strategy.apply(neg, decision)
            results.append(decision)
        return case, neg, results

    def test_unreasoned_offer_earns_no_movement(self):
        _, neg, results = self.play(['I will offer 11000'])
        self.assertEqual(results[0]['action'], 'hold')
        self.assertEqual(neg['ask'], 12000)

    def test_repeating_a_number_with_because_earns_one_move_only(self):
        _, neg, results = self.play(['9000 because of our budget', '9000 because of our budget', '9000 because it is our budget'])
        self.assertEqual(results[0]['action'], 'counter')
        self.assertNotEqual(results[1]['action'], 'counter')
        self.assertNotEqual(results[2]['action'], 'counter')

    def test_concessions_shrink_and_never_cross_the_true_floor(self):
        case, neg, results = self.play(['8000 because of budget', '8100 because of budget', '8200 because of budget', '8300 because of budget', '8400 because of budget', '8500 because of budget'])
        asks = [r['authorised'][1] for r in results if r['action'] == 'counter']
        drops = [a - b for a, b in zip([12000] + asks, asks)]
        self.assertEqual(drops, sorted(drops, reverse=True))
        self.assertGreaterEqual(min(asks), case['seller']['minimum'])

    def test_floor_is_never_authorised_before_the_learner_reaches_it(self):
        case, _, results = self.play(['8000', 'yes', 'okay', '8000 because of budget', 'yes'])
        floor = case['seller']['minimum']
        for decision in filter(None, results):
            self.assertNotIn(floor, decision['authorised'])
            self.assertNotIn(str(floor), decision['purpose'].replace(',', ''))

    def test_acknowledgement_before_any_bargaining_is_not_about_terms(self):
        definition, _ = compile_case('activity-negotiation', 0)
        case = definition['negotiation']
        self.assertIsNone(strategy.decide(case, strategy.new_state(case), 'Okay'))

    def test_the_proposed_figure_is_read_rather_than_the_benchmark(self):
        terms = strategy.parse_terms('The earlier package sold for USD 11000, so based on that I can offer USD 9500 because of our budget.')
        self.assertEqual(terms['price'], 9500)
        self.assertEqual(strategy.parse_terms('I will pay ten thousand')['price'], 10000)
        self.assertEqual(strategy.parse_terms('To confirm: USD 10600, 20 seats, delivery in 45 days')['price'], 10600)

    def test_accepting_one_term_is_not_accepting_the_deal(self):
        _, _, results = self.play(['9000 because of budget', '10500 because the benchmark was 11000 and I accept 45 days delivery'])
        self.assertNotEqual(results[1]['action'], 'accept')

    def test_vague_yes_needs_complete_confirmation(self):
        _, neg, results = self.play(['9000 because of budget', 'yes', 'I accept'])
        self.assertEqual(results[1]['action'], 'clarify')
        self.assertEqual(results[2]['action'], 'accept')
        self.assertEqual(results[2]['ledger'], {'kind': 'accept'})

    def test_later_delivery_is_a_real_trade(self):
        case, _, results = self.play(['9000 because of budget', 'If you can do 9800 I can accept 45 days'])
        self.assertEqual(strategy.floor_for(case, {'delivery_days': 45}), 9500)
        self.assertIn(results[1]['action'], {'counter', 'confirm_terms'})

    def test_no_zopa_case_reaches_impasse_without_crossing_the_floor(self):
        case, neg, results = self.play(['9000 because of budget', '9000 because of budget', '9000 because of budget', '9000', '9000'], variant=1, challenge='beginner')
        lines = ['8500 because of budget', '8600 because of budget', '8700 because of budget', '8800 because of budget', '8900 because of budget', '9000 because of budget', '9000', '9000', '9000']
        case, neg, results = self.play(lines, variant=1, challenge='beginner')
        actions = [r['action'] for r in results]
        self.assertIn('final_position', actions)
        self.assertIn('impasse', actions)
        self.assertGreaterEqual(neg['ask'], case['seller']['minimum'])

    def test_binding_terms_are_spoken_exactly_not_paraphrased(self):
        _, _, results = self.play(['9000 because of budget', 'I accept'])
        self.assertTrue(results[1].get('exact'))
        self.assertIn('USD', results[1]['fallback'])
        self.assertIn('20 seats', results[1]['fallback'])

    def test_accepting_a_figure_that_was_not_offered_is_corrected(self):
        _, _, results = self.play(['9000 because of budget', 'I accept. To confirm: USD 10000, 20 seats.'])
        self.assertEqual(results[1]['action'], 'clarify')
        self.assertIn('not USD 10,000', results[1]['fallback'])

    def test_walk_away_is_respected_with_no_new_offer(self):
        _, _, results = self.play(['No deal. We will go with the other supplier.'])
        self.assertEqual(results[0]['action'], 'respect_no_deal')
        self.assertEqual(results[0]['authorised'], [])

    def test_alternative_earns_a_comparison_not_a_discount(self):
        _, neg, results = self.play(['Another supplier offers USD 8500 for 45 days.'])
        self.assertEqual(results[0]['action'], 'compare')
        self.assertEqual(neg['ask'], 12000)


class TestSceneThroughTheEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'scene.db')
        self.runtime = self.training.context.runtime

    def tearDown(self):
        self.temp.cleanup()

    async def test_gates_hold_for_every_persona_with_a_plain_model(self):
        others = ('garbled', 'terse', 'off_topic', 'adversarial')
        for index, activity in enumerate(available_cases()):
            # Every lesson meets confusion, and all the other learner types are covered in rotation.
            for persona in ('confused', others[index % 4]):
                _, metrics, _ = await run_case(PlainProvider(), activity, persona, training=self.training)
                failed = [gate for gate in failed_gates(metrics) if gate != 'near_duplicates']
                self.assertEqual(failed, [], f'{activity}/{persona}: {metrics}')

    async def test_a_strong_learner_can_reach_the_end_of_every_lesson(self):
        stuck = []
        for activity in available_cases():
            _, _, sid = await run_case(PlainProvider(), activity, 'strong', training=self.training)
            definition, state = self.runtime.read(sid)
            if state['scene']['beat'] != len(definition['beats']) - 1:
                stuck.append((activity, state['scene']['beat']))
        self.assertEqual(stuck, [])

    async def test_company_case_is_built_around_the_learners_own_document(self):
        definition, _ = compile_case('activity-company-knowledge', 0, None, [{'id': 'doc0', 'text': 'The company document Leave Policy says: Annual leave needs 10 days of notice.'}])
        customer = next(p for p in definition['participants'] if p['kind'] == 'ai')
        state = {'scene': director.new_scene(definition), 'offers': []}
        self.assertTrue(any('10 days' in fact for fact in director.visible_facts(definition, state['scene'], customer['id'])))
        speaker = {**customer, '_move': 'answer'}
        self.assertTrue(director.check_sentence(definition, state, speaker, 'So that needs 10 days of notice?', '', []))
        self.assertEqual(director.check_sentence(definition, state, speaker, 'I heard it needs 30 days of notice.', '', []), '')

    async def test_private_limits_never_reach_the_prompt_or_public_view(self):
        session = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')
        sid = session['id']
        definition, _ = self.runtime.read(sid)
        floor = str(int(definition['negotiation']['seller']['minimum']))
        captured = []

        class Spy(PlainProvider):
            def generate_contextual_response(self, prompt):
                captured.append(json.dumps(prompt['messages']))
                yield 'What did you have in mind?'
        runner = TrainingOrchestrator(self.training, Spy(), None, Mock(), 24000, 'none')
        for line in ('What matters most to you here, and why?', 'I can offer 9500 because of our budget.', 'If you can do 9800 I can accept 45 days.'):
            result = await runner.run_turn(sid, RoleplayTurn(text=line, synthesize_audio=False))
            public = json.dumps(result['runtime'])
            self.assertNotIn('private_knowledge', public)
            self.assertNotIn('"directions"', public)
            self.assertNotIn('"negotiation": {"ask"', public)
        self.assertTrue(captured)
        for prompt in captured:
            self.assertNotIn(f'USD {floor}', prompt)
            self.assertNotIn(f'USD {int(floor):,}', prompt)
            self.assertNotIn('private_knowledge', prompt)
            self.assertNotIn('"maximum"', prompt)
            self.assertNotIn('"minimum"', prompt)

    async def test_spoken_acceptance_reaches_the_ledger_only_when_feasible(self):
        session = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')
        sid = session['id']
        runner = TrainingOrchestrator(self.training, PlainProvider(), None, Mock(), 24000, 'none')
        for line in ('I can offer 9500 because of our budget.', 'I accept.'):
            await runner.run_turn(sid, RoleplayTurn(text=line, synthesize_audio=False))
        offers = self.runtime.view(sid)['offers']
        self.assertTrue(any(o['status'] == 'accepted' for o in offers))
        accepted = next(o for o in offers if o['status'] == 'accepted')
        self.assertEqual(accepted['terms']['seats'], 20)

    async def test_agreeing_terms_first_offered_with_a_condition_completes_the_deal(self):
        session = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')
        sid = session['id']
        runner = TrainingOrchestrator(self.training, PlainProvider(), None, Mock(), 24000, 'none')
        for line in ('I can offer USD 9500 because of our budget.', 'If you can do USD 10500, I can accept delivery in 45 days.', 'I accept. To confirm: USD 10500, 20 seats, delivery in 45 days and 3 months of support.'):
            result = await runner.run_turn(sid, RoleplayTurn(text=line, synthesize_audio=False))
        offers = self.runtime.view(sid)['offers']
        accepted = [o for o in offers if o['status'] == 'accepted']
        self.assertEqual(len(accepted), 1)
        self.assertEqual((accepted[0]['terms']['price'], accepted[0]['terms']['delivery_days']), (10500, 45))
        self.assertIn('To confirm', result['text'])

    async def test_character_never_confirms_a_package_the_ledger_refuses(self):
        session = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')
        sid = session['id']
        runner = TrainingOrchestrator(self.training, PlainProvider(), None, Mock(), 24000, 'none')
        # 11800 is above the buyer's own approved limit, so the ledger must refuse the deal.
        for line in ('I can offer USD 11800 because of our budget.', 'I accept. To confirm: USD 11800, 20 seats, delivery in 30 days and 3 months of support.'):
            result = await runner.run_turn(sid, RoleplayTurn(text=line, synthesize_audio=False))
        self.assertFalse(any(o['status'] == 'accepted' for o in self.runtime.view(sid)['offers']))
        self.assertIn("don't work as they stand", result['text'])

    async def test_a_prepared_line_does_not_pretend_to_answer_a_question(self):
        class Down:
            def generate_contextual_response(self, prompt):
                raise RuntimeError('down')
                yield ''
        session = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')
        result = await TrainingOrchestrator(self.training, Down(), None, Mock(), 24000, 'none').run_turn(session['id'], RoleplayTurn(text='What matters most to you on this deal?', synthesize_audio=False))
        self.assertTrue(result['text'].startswith('Let me come back to that.'))

    async def test_review_is_told_what_it_must_return(self):
        negotiation = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')['id']
        self.assertIn('discovery', self.runtime.evaluation_context(negotiation)['required_dimensions'])
        document = self.training.add_document('demo', 'Policy', 'Annual leave requires ten working days of notice for all staff members in the company.')
        company = self.training.create_session('demo', 'company-knowledge', 'intermediate', 'activity-company-knowledge', document_ids=[document['id']])['id']
        self.assertTrue(self.runtime.evaluation_context(company)['policy_check_required'])

    async def test_authored_lines_serve_when_the_model_breaks_every_rule(self):
        class Rogue:
            def generate_contextual_response(self, prompt):
                yield 'The budget of 90000 is confirmed, and it takes 77 days.'
        session = self.training.create_session('demo', 'english-speaking', 'advanced', 'english-28')
        runner = TrainingOrchestrator(self.training, Rogue(), None, Mock(), 24000, 'none')
        result = await runner.run_turn(session['id'], RoleplayTurn(text='I would like to begin with a thought about the schedule', synthesize_audio=False))
        self.assertNotIn('90000', result['text'])
        self.assertTrue(result['responses'])
        self.assertEqual(result['responses'][0]['response_mode'], 'scripted')


class TestSceneAssessment(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'assess.db')
        self.runtime = self.training.context.runtime

    def tearDown(self):
        self.temp.cleanup()

    def start(self, text='Hi, my name is Sara.'):
        session = self.training.create_session('demo', 'english-speaking', 'beginner', 'english-01')
        sid = session['id']
        self.runtime.start(sid, SimpleNamespace(text=text, duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        return sid

    def review(self, sid, met, level=3):
        context = self.runtime.evaluation_context(sid)
        turn = next(t for t in context['transcript'] if t['role'] == 'user')
        criteria = [{'objective_id': o['id'], 'met': o['id'] in met, 'quotes': [turn['text']] if o['id'] in met else [], 'turn_ids': [turn['id']] if o['id'] in met else []} for o in context['rubric']]
        dims = {name: {'status': 'developing', 'level': level, 'reason': 'Understandable.', 'quotes': [turn['text']]} for name in ('grammar', 'vocabulary', 'comprehension_relevance', 'interaction')}
        self.assertTrue(self.runtime.save_evaluation(sid, context['revision'], {'criteria': criteria, 'dimensions': dims}))

    def test_partial_attempt_scores_honestly_and_is_recorded(self):
        sid = self.start()
        self.review(sid, {'o1', 'o2'}, level=2)
        assessment = self.training.assess(sid)
        self.assertEqual(assessment['scores']['task_achievement'], 66.7)
        self.assertEqual(assessment['scores']['grammar'], 50)
        self.assertNotEqual(assessment['overall'], 100)
        self.assertLess(assessment['overall'], 100)
        self.assertIn('Some objectives are not demonstrated', assessment['feedback'])

    def test_language_quality_is_separate_from_task_completion(self):
        sid = self.start()
        self.review(sid, {'o1', 'o2', 'o3'}, level=2)
        assessment = self.training.assess(sid)
        self.assertEqual(assessment['scores']['task_achievement'], 100)
        self.assertEqual(assessment['scores']['vocabulary'], 50)
        self.assertLess(assessment['overall'], 100)

    def test_unassessed_language_stays_absent_rather_than_zero(self):
        sid = self.start()
        context = self.runtime.evaluation_context(sid)
        self.runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': 'o1', 'met': False, 'quotes': [], 'turn_ids': []}]})
        assessment = self.training.assess(sid)
        self.assertNotIn('grammar', assessment['scores'])

    def test_negotiation_subskills_update_only_from_matching_evidence(self):
        session = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')
        sid = session['id']
        self.runtime.start(sid, SimpleNamespace(text='What matters most to you and why is delivery important?', duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        context = self.runtime.evaluation_context(sid)
        turn = next(t for t in context['transcript'] if t['role'] == 'user')
        criteria = [{'objective_id': o['id'], 'met': o['id'] == 'n2', 'quotes': [turn['text']] if o['id'] == 'n2' else [], 'turn_ids': [turn['id']] if o['id'] == 'n2' else []} for o in context['rubric']]
        self.runtime.save_evaluation(sid, context['revision'], {'criteria': criteria})
        self.training.assess(sid)
        with self.training.context.runtime.connect() as db:
            rows = {r['subskill']: r['score'] for r in db.execute("SELECT subskill,score FROM subskill_proficiency WHERE user_id='demo' AND skill_id='negotiation'")}
        self.assertEqual(rows.get('discovery'), 85)
        self.assertEqual(rows.get('closing'), 35)
        self.assertEqual(rows.get('anchoring'), 50, 'Unobserved subskills keep their starting value')

    def test_debrief_quote_must_be_the_learners_own_words(self):
        sid = self.start()
        self.review(sid, {'o1'})
        invented = {'debrief': {'did_well': {'quote': 'I am an expert negotiator', 'why': 'Very impressive.'}, 'change': {'quote': 'never said this', 'why': 'x', 'better': 'y'}, 'try_next': 'Say goodbye next time.'}}
        assessment = self.training.assess(sid, invented)
        self.assertFalse(any('expert negotiator' in item for item in assessment['strengths']))
        self.assertFalse(any('never said this' in item for item in assessment['improvements']))
        self.assertIn('Say goodbye next time.', assessment['feedback'])

    def test_next_attempt_adapts_to_what_the_last_one_showed(self):
        first = self.training.context.scenario.scenario_preview('demo', 'english-speaking', 'beginner', 'english-01')
        self.assertEqual(first['runtime_definition']['adaptation']['intensity'], 'gentle')
        sid = self.start()
        self.review(sid, {'o1', 'o2'}, level=1)
        self.training.assess(sid)
        weak = self.training.context.scenario.scenario_preview('demo', 'english-speaking', 'beginner', 'english-01')
        self.assertEqual(weak['runtime_definition']['adaptation']['focus'], 'o3')
        self.assertIn('close the conversation politely', weak['adaptation_reason'])
        self.assertNotEqual(first['variant'], weak['variant'], 'A retry should be a different case')
        sid = self.start()
        self.review(sid, {'o1', 'o2', 'o3'}, level=4)
        self.training.assess(sid)
        strong = self.training.context.scenario.scenario_preview('demo', 'english-speaking', 'beginner', 'english-01')
        self.assertEqual(strong['runtime_definition']['adaptation']['intensity'], 'challenging')
        self.assertIsNone(strong['runtime_definition']['adaptation']['focus'])

    def test_debrief_uses_authored_notes_without_a_model(self):
        sid = self.start()
        self.review(sid, {'o1', 'o2'})
        assessment = self.training.assess(sid)
        self.assertTrue(any('goodbye' in item.lower() for item in assessment['improvements']))

    def test_corrected_transcript_invalidates_evidence_quoted_from_it(self):
        sid = self.start()
        self.review(sid, {'o1', 'o2'})
        from domain.conversation import SessionAction
        turn = next(t for t in self.runtime.evaluation_context(sid)['transcript'] if t['role'] == 'user')
        self.runtime.action(sid, SessionAction(action='correct', data={'turn_id': turn['id'], 'text': 'Hello there.'}, request_id='c1'))
        self.assertEqual(self.runtime.read(sid)[1]['met_evidence'], {})

    def test_reopens_a_stage_when_review_disagrees_with_the_provisional_signal(self):
        sid = self.start()
        with self.runtime.connect() as db:
            definition, state = self.runtime.read(sid, db)
            state['scene'].update(beat=2, finished=True)
            db.execute('UPDATE conversation_runtime SET state_json=? WHERE session_id=?', (json.dumps(state), sid))
        self.review(sid, {'o1', 'o3'})
        _, state = self.runtime.read(sid)
        self.assertFalse(state['scene']['finished'])
        self.assertEqual(state['scene']['beat'], 0)


class TestOrganization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'org.db')
        self.org = self.training.context.organization
        with self.org.connect() as db:
            for user, org, role in (('owner', 'o1', 'owner'), ('member', 'o2', 'owner'), ('other', 'o3', 'owner')):
                db.execute("INSERT INTO organizations(id,name,slug,created_at,updated_at) VALUES (?,?,?,'now','now')", (org, f'Org {org}', org))
                db.execute("INSERT INTO users(id,name,role,organization,created_at) VALUES (?,?,'Learner','Org','now')", (user, user.title()))
                db.execute("INSERT INTO organization_memberships VALUES (?,?,?,'now')", (org, user, role))

    def tearDown(self):
        self.temp.cleanup()

    def test_invite_is_single_use_stored_hashed_and_moves_the_member(self):
        from domain.errors import DomainError
        invite = self.org.create_invite('owner', 'learner')
        with self.org.connect() as db:
            stored = db.execute('SELECT code_hash FROM organization_invites').fetchone()[0]
        self.assertNotEqual(stored, invite['code'])
        self.assertEqual(self.org.join('member', invite['code'])['role'], 'learner')
        self.assertEqual(self.org.membership('member')['organization_id'], 'o1')
        with self.assertRaises(DomainError):
            self.org.join('other', invite['code'])

    def test_only_managers_invite_and_only_trainers_see_the_team(self):
        from domain.errors import DomainError
        self.org.join('member', self.org.create_invite('owner', 'learner')['code'])
        with self.assertRaises(DomainError):
            self.org.create_invite('member')
        with self.assertRaises(DomainError):
            self.org.team_progress('member')
        self.org.join('other', self.org.create_invite('owner', 'trainer')['code'])
        self.assertEqual(len(self.org.team_progress('other')['members']), 3)

    def test_team_view_contains_summaries_and_no_conversation_content(self):
        with self.org.connect() as db:
            db.execute("""INSERT INTO sessions(id,user_id,skill_id,difficulty,title,situation,counterpart,objectives,status,created_at,completed_at,activity_id)
                VALUES ('s1','owner','negotiation','intermediate','T','S','C','[]','completed','now','now','activity-negotiation')""")
            db.execute("INSERT INTO turns(session_id,role,text,duration_seconds,created_at) VALUES ('s1','user','PRIVATE LEARNER WORDS',0,'now')")
            db.execute("INSERT INTO assessments VALUES ('a1','s1',70,'{}','[]','[]','[\"PRIVATE EVIDENCE\"]','F','now')")
        report = json.dumps(self.org.team_progress('owner'))
        self.assertIn('70', report)
        self.assertNotIn('PRIVATE', report)


class TestFyp1Gaps(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'gaps.db')
        self.runtime = self.training.context.runtime

    def tearDown(self):
        self.temp.cleanup()

    def test_goal_skill_comes_first_in_the_plan_and_can_be_closed(self):
        progress = self.training.context.progress
        goal = progress.add_goal('demo', 'Get better at interviews', 'interviews', '2027-01-15')
        self.assertEqual(progress.goals('demo')[0]['skill_id'], 'interviews')
        session = self.training.create_session('demo', 'english-speaking', 'beginner', 'english-01')
        with self.runtime.connect() as db:
            db.execute("INSERT INTO assessments VALUES ('a1',?,50,'{}','[]','[]','[]','F','now')", (session['id'],))
            self.training.context.adaptive.update_training_plan(db, 'demo', 'a1', session)
            top = [r[0] for r in db.execute("SELECT a.primary_skill_id FROM training_plan_activities p JOIN training_activities a ON a.id=p.activity_id WHERE p.status='upcoming' ORDER BY p.position")]
        self.assertEqual(top[1], 'interviews')
        progress.close_goal('demo', goal['id'])
        self.assertEqual(progress.goals('demo'), [])
        with self.assertRaises(ValueError):
            progress.add_goal('demo', 'Bad', 'no-such-skill')

    def test_unsupported_policy_claim_is_reported_with_the_learners_words(self):
        document = self.training.add_document('demo', 'Leave Policy', 'Annual leave requires 10 working days notice and line manager approval before travel is booked. This policy applies to all staff.')
        sid = self.training.create_session('demo', 'company-knowledge', 'intermediate', 'activity-company-knowledge', document_ids=[document['id']])['id']
        definition, _ = self.runtime.read(sid)
        self.assertTrue(any('10 working days' in fact for fact in definition['facts']))
        line = 'The policy says you only need 2 days of notice.'
        self.runtime.start(sid, SimpleNamespace(text=line, duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        context = self.runtime.evaluation_context(sid)
        turn = next(t for t in context['transcript'] if t['role'] == 'user')
        self.assertTrue(self.runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': 'o1', 'met': False, 'quotes': [], 'turn_ids': []}],
            'policy_check': [{'quote': line, 'supported': False, 'reason': 'It requires 10 working days.'}, {'quote': 'I never said this', 'supported': True, 'reason': 'x'}]}))
        assessment = self.training.assess(sid)
        self.assertTrue(any('does not support' in item for item in assessment['improvements']))
        self.assertFalse(any('I never said this' in item for item in assessment['evidence']))

    def test_all_objectives_already_proven_does_not_report_a_failed_review(self):
        sid = self.training.create_session('demo', 'english-speaking', 'beginner', 'english-01')['id']
        self.runtime.start(sid, SimpleNamespace(text='Hi, my name is Sara, goodbye.', duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        with self.runtime.connect() as db:
            _, state = self.runtime.read(sid, db)
            state['met_evidence'] = {'o1': {'objective_id': 'o1', 'met': True, 'quotes': ['Hi'], 'turn_ids': [1], 'support': 'independent'}}
            db.execute('UPDATE conversation_runtime SET state_json=? WHERE session_id=?', (json.dumps(state), sid))
        revision = self.runtime.read(sid)[1]['evidence_revision']
        self.assertTrue(self.runtime.save_evaluation(sid, revision, {'criteria': []}))

    def test_every_resource_has_real_guidance(self):
        with self.runtime.connect() as db:
            for row in db.execute('SELECT id,content_text,description FROM resources'):
                self.assertGreater(len(row['content_text']), 200, row['id'])


class TestSceneVoiceFlow(unittest.IsolatedAsyncioTestCase):
    """The same path a voice call uses: sentences stream, and playback is acknowledged."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'voice.db')
        self.runtime = self.training.context.runtime
        self.runner = TrainingOrchestrator(self.training, PlainProvider(), None, Mock(), 24000, 'none')

    def tearDown(self):
        self.temp.cleanup()

    def meeting(self):
        return self.training.create_session('demo', 'english-speaking', 'advanced', 'english-28')['id']

    async def test_each_sentence_streams_with_identity_and_is_heard_only_after_acknowledgement(self):
        sid = self.training.create_session('demo', 'english-speaking', 'beginner', 'english-01')['id']
        spoken = []
        result = await self.runner.run_turn(sid, RoleplayTurn(text='Hello there, my name is Sara.', synthesize_audio=False), sentence_callback=lambda text, speaker, meta: spoken.append((text, speaker, meta)))
        self.assertTrue(spoken)
        text, speaker, meta = spoken[0]
        self.assertEqual(speaker, 'Alex')
        for key in ('utterance_id', 'segment', 'participant_id', 'generation_id', 'voice_index'):
            self.assertIn(key, meta)
        with self.runtime.connect() as db:
            row = db.execute('SELECT status,delivered_text FROM conversation_utterances WHERE id=?', (meta['utterance_id'],)).fetchone()
        self.assertFalse(row['delivered_text'], 'Nothing counts as heard before playback is acknowledged')
        self.runtime.acknowledge(sid, meta['utterance_id'], meta['segment'])
        with self.runtime.connect() as db:
            row = db.execute('SELECT status,delivered_text FROM conversation_utterances WHERE id=?', (meta['utterance_id'],)).fetchone()
        self.assertIn(text, row['delivered_text'])
        self.assertEqual(result['responses'][0]['move'], 'advance_beat')

    async def test_second_voice_waits_for_the_first_to_be_heard(self):
        sid = self.meeting()
        spoken = []
        def on_sentence(text, speaker, meta):
            spoken.append(speaker)
            # The browser reports each sentence as played a moment later.
            self.runtime.acknowledge(sid, meta['utterance_id'], meta['segment'])
        result = await self.runner.run_turn(sid, RoleplayTurn(text='The purpose of this meeting is to hear your concerns and agree a plan.', synthesize_audio=False), sentence_callback=on_sentence)
        self.assertEqual([r['speaker'] for r in result['responses']], ['Alex', 'Maya'])
        self.assertEqual(spoken[0], 'Alex')
        self.assertEqual(spoken[-1], 'Maya')

    async def test_second_voice_never_speaks_if_the_first_was_interrupted(self):
        from domain.conversation import SessionAction
        sid = self.meeting()
        spoken = []
        def on_sentence(text, speaker, meta):
            spoken.append(speaker)
            if len(spoken) == 1:
                self.runtime.action(sid, SessionAction(action='interrupt', request_id='stop'))
        await self.runner.run_turn(sid, RoleplayTurn(text='The purpose of this meeting is to hear your concerns and agree a plan.', synthesize_audio=False), sentence_callback=on_sentence)
        self.assertNotIn('Maya', spoken)
        with self.runtime.connect() as db:
            statuses = [r[0] for r in db.execute('SELECT status FROM conversation_utterances WHERE session_id=?', (sid,))]
        self.assertTrue(all(status == 'interrupted' for status in statuses), statuses)

    async def test_learner_can_speak_again_after_an_interruption(self):
        from domain.conversation import SessionAction
        sid = self.meeting()
        def on_sentence(text, speaker, meta):
            self.runtime.action(sid, SessionAction(action='interrupt', request_id='stop-2'))
        await self.runner.run_turn(sid, RoleplayTurn(text='The purpose of this meeting is to agree a plan together.', synthesize_audio=False), sentence_callback=on_sentence)
        again = await self.runner.run_turn(sid, RoleplayTurn(text='Sorry, Alex, please go ahead with your concern.', synthesize_audio=False))
        self.assertEqual(again['responses'][0]['speaker'], 'Alex')

    async def test_unreliable_recognition_asks_again_and_cannot_earn_credit(self):
        sid = self.meeting()
        result = await self.runner.run_turn(sid, RoleplayTurn(text='The purpose of this meeting is to agree a plan.', synthesize_audio=False, recognition={'source': 'speech', 'unreliable': True}))
        self.assertEqual(result['responses'][0]['move'], 'clarify')
        self.assertEqual(self.runtime.read(sid)[1]['scene']['signals'], [])


class TestRestartRecovery(unittest.TestCase):
    def test_a_reply_cut_off_by_a_restart_does_not_leave_the_session_stuck(self):
        with tempfile.TemporaryDirectory() as folder:
            training = TrainingService(Path(folder) / 'restart.db')
            runtime = training.context.runtime
            sid = training.create_session('demo', 'english-speaking', 'beginner', 'english-01')['id']
            runtime.start(sid, SimpleNamespace(text='Hello there.', duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
            self.assertTrue(runtime.read(sid)[1]['generation'])
            self.assertEqual(runtime.release_stale_floors(), 1)
            _, state = runtime.read(sid)
            self.assertIsNone(state['generation'])
            self.assertTrue(state['failed_turn_id'])
            self.assertEqual(runtime.release_stale_floors(), 0)


class TestNegotiationDebrief(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'deal.db')
        self.runtime = self.training.context.runtime

    def tearDown(self):
        self.temp.cleanup()

    def test_decision_quality_is_separate_from_language_and_limits_stay_private(self):
        sid = self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')['id']
        definition, _ = self.runtime.read(sid)
        line = 'What matters most to you, and why does delivery timing matter?'
        self.runtime.start(sid, SimpleNamespace(text=line, duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        with self.runtime.connect() as db:
            _, state = self.runtime.read(sid, db)
            base = {'rationale': 'Budget', 'condition': '', 'currency': 'USD', 'seats': 20, 'delivery_days': 30, 'support_months': 3}
            state['offers'] = [{'id': 'a', 'status': 'countered', 'terms': {**base, 'price': 9000}}, {'id': 'b', 'status': 'proposed', 'terms': {**base, 'price': 9200}}]
            db.execute('UPDATE conversation_runtime SET state_json=? WHERE session_id=?', (json.dumps(state), sid))
        context = self.runtime.evaluation_context(sid)
        turn = next(t for t in context['transcript'] if t['role'] == 'user')
        dims = {'discovery': {'status': 'demonstrated', 'level': 3, 'reason': 'You asked why.', 'quotes': [line]}, 'grammar': {'status': 'demonstrated', 'level': 4, 'reason': 'Clear.', 'quotes': [line]}}
        self.runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': 'n2', 'met': True, 'quotes': [line], 'turn_ids': [turn['id']]}], 'dimensions': dims})
        assessment = self.training.assess(sid)
        self.assertEqual(assessment['scores']['decision_discovery'], 75)
        self.assertEqual(assessment['scores']['grammar'], 100)
        text = ' '.join(assessment['improvements'])
        self.assertIn('A trade you did not try', text)
        self.assertIn('without asking for anything in return', text)
        minimum = str(int(definition['negotiation']['seller']['minimum']))
        self.assertNotIn(minimum, text)

    def test_missed_trade_note_appears_with_no_offers_made(self):
        session = self.training.session(self.training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')['id'])
        self.assertEqual(self.training.context.assessment._negotiation_review(self.runtime.read(session['id'])[0], {'offers': []})[:1][0][:5], 'A tra')

    def test_lessons_show_one_useful_correction_by_default(self):
        sid = self.training.create_session('demo', 'english-speaking', 'beginner', 'english-01')['id']
        self.assertEqual(self.runtime.view(sid)['preferences']['correction_style'], 'selective')
        line = 'Hello, I am go to work now.'
        self.runtime.start(sid, SimpleNamespace(text=line, duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        context = self.runtime.evaluation_context(sid)
        self.runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': 'o1', 'met': False, 'quotes': [], 'turn_ids': []}],
            'corrections': [{'original': 'I am go to work', 'improved': 'I am going to work'}]})
        coach = self.runtime.view(sid)['coach']
        self.assertIn('I am go to work', coach[-1]['text'])
        self.assertIn('I am going to work', coach[-1]['text'])


class TestLearningPath(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.training = TrainingService(Path(self.temp.name) / 'path.db')
        self.runtime = self.training.context.runtime
        self.path = self.training.context.learning_path

    def tearDown(self):
        self.temp.cleanup()

    def attempt(self, activity, met_all=True):
        sid = self.training.create_session('demo', 'english-speaking', 'beginner', activity)['id']
        self.runtime.start(sid, SimpleNamespace(text='Hello, here is my complete answer to this.', duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        context = self.runtime.evaluation_context(sid)
        turn = next(t for t in context['transcript'] if t['role'] == 'user')
        self.runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': o['id'], 'met': met_all, 'quotes': [turn['text']] if met_all else [], 'turn_ids': [turn['id']] if met_all else []} for o in context['rubric']]})
        self.training.assess(sid)
        return sid

    def lesson(self, path, lesson_id):
        return next(lesson for unit in path['units'] for lesson in unit['lessons'] if lesson['id'] == lesson_id)

    def test_new_learner_starts_at_the_first_lesson_with_later_units_locked_but_checkpoints_open(self):
        path = self.path.path('demo')
        self.assertEqual(path['next']['id'], 'english-01')
        self.assertTrue(path['units'][0]['unlocked'])
        self.assertFalse(path['units'][1]['unlocked'])
        self.assertTrue(self.lesson(path, 'english-06')['locked'])
        self.assertFalse(self.lesson(path, 'english-10')['locked'], 'A checkpoint can always be attempted')

    def test_a_failed_attempt_is_practising_and_opens_nothing(self):
        self.attempt('english-05', met_all=False)
        path = self.path.path('demo')
        self.assertEqual(self.lesson(path, 'english-05')['state'], 'practising')
        self.assertFalse(path['units'][1]['unlocked'])

    def test_passing_a_checkpoint_opens_the_next_unit_and_shows_evidence_without_mastery_claims(self):
        self.attempt('english-05')
        path = self.path.path('demo')
        self.assertTrue(path['units'][1]['unlocked'])
        lesson = self.lesson(path, 'english-05')
        self.assertEqual(lesson['state'], 'independent_today')
        self.assertTrue(lesson['can_do']['objectives'])
        self.assertIn('does not establish', path['note'])
        self.assertEqual(path['counts']['independent_today'], 1)

    def test_due_review_appears_and_a_fresh_case_records_retention(self):
        self.attempt('english-01')
        with self.runtime.connect() as db:
            db.execute("UPDATE learning_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE interval_days=7")
            review = db.execute("SELECT id FROM learning_reviews WHERE interval_days=7").fetchone()['id']
        path = self.path.path('demo')
        self.assertEqual([item['id'] for item in path['due_reviews']], [review])
        preview = self.training.context.scenario.scenario_preview('demo', 'english-speaking', 'beginner', 'english-01', review_id=review)
        sid = self.training.create_session('demo', 'english-speaking', 'beginner', 'english-01', preview_id=preview['preview_id'])['id']
        self.runtime.start(sid, SimpleNamespace(text='Hello, my name is Sara. Goodbye.', duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
        context = self.runtime.evaluation_context(sid)
        turn = next(t for t in context['transcript'] if t['role'] == 'user')
        self.runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': o['id'], 'met': True, 'quotes': [turn['text']], 'turn_ids': [turn['id']]} for o in context['rubric']]})
        self.assertEqual(self.path.path('demo')['counts']['retained_later'], 1)

    def test_every_workplace_lesson_is_open_and_listed(self):
        path = self.path.path('demo')
        self.assertEqual(len(path['workplace']), 16)
        self.assertFalse(any(lesson['locked'] for lesson in path['workplace']))


class TestPostureAndSpeechSignals(unittest.TestCase):
    def test_too_few_samples_give_no_judgement(self):
        from intelligence.posture_analysis import summarise
        result = summarise([(80, 80, 80, 80)])
        self.assertFalse(result['available'])
        self.assertIn('does not count against you', result['note'])

    def test_trend_and_cue_come_from_the_samples(self):
        from intelligence.posture_analysis import summarise
        result = summarise([(90, 80, 80, 80)] * 4 + [(50, 80, 80, 80)] * 4)
        slouch = next(item for item in result['indicators'] if item['name'] == 'slouching')
        self.assertEqual(slouch['trend'], 'dropped')
        self.assertTrue(slouch['cue'])
        self.assertEqual(result['focus'], 'slouching')
        steady = next(item for item in result['indicators'] if item['name'] == 'head_position')
        self.assertEqual(steady['trend'], 'steady')
        self.assertIsNone(steady['cue'])
        for word in ('confident', 'nervous', 'personality', 'emotion'):
            self.assertNotIn(word, json.dumps(result).lower().replace('not a judgement of you', ''))

    def test_speech_signal_is_labelled_and_never_scored(self):
        with tempfile.TemporaryDirectory() as folder:
            training = TrainingService(Path(folder) / 'speech.db')
            runtime = training.context.runtime
            sid = training.create_session('demo', 'english-speaking', 'beginner', 'english-01')['id']
            for index in range(3):
                generation, _ = runtime.start(sid, SimpleNamespace(text=f'Hello there number {index}', duration_seconds=0, request_id=f'r{index}', expected_revision=None, addressed_participant_ids=[], recognition={'source': 'speech', 'confidence': .8}))
                runtime.finish(sid, generation, {})
            context = runtime.evaluation_context(sid)
            assessment = training.assess(sid)
            self.assertEqual(assessment['speech_signal']['average'], .8)
            self.assertIn('not a pronunciation score', assessment['speech_signal']['note'])
            self.assertNotIn('pronunciation', assessment['scores'])


class TestEvaluationTools(unittest.TestCase):
    def test_kappa_values(self):
        from scripts.evaluation.tools import cohen_kappa
        self.assertEqual(cohen_kappa(['met', 'not_met', 'met', 'not_met'], ['met', 'not_met', 'met', 'not_met']), 1.0)
        self.assertEqual(cohen_kappa(['met', 'met', 'not_met', 'not_met'], ['met', 'not_met', 'met', 'not_met']), 0.0)
        self.assertIsNone(cohen_kappa(['', ''], ['met', '']))

    def test_export_hides_names_and_system_judgements_and_agreement_finds_differences(self):
        import sqlite3
        from scripts.evaluation.tools import agreement, learner_summary, rows_for_raters
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'eval.db'
            training = TrainingService(path)
            runtime = training.context.runtime
            sid = training.create_session('demo', 'english-speaking', 'beginner', 'english-01')['id']
            runtime.start(sid, SimpleNamespace(text='Hello, my name is Sara.', duration_seconds=0, request_id='r1', expected_revision=None, addressed_participant_ids=[], recognition={}))
            context = runtime.evaluation_context(sid)
            turn = next(t for t in context['transcript'] if t['role'] == 'user')
            runtime.save_evaluation(sid, context['revision'], {'criteria': [{'objective_id': 'o1', 'met': True, 'quotes': [turn['text']], 'turn_ids': [turn['id']]}]})
            training.assess(sid)
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            rows, key = rows_for_raters(db)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row['learner'] == 'L001' for row in rows))
            self.assertNotIn('system', rows[0])
            self.assertNotIn('demo', json.dumps(rows))
            truth = {row['item']: row['system'] for row in key}
            met_item = next(item for item, value in truth.items() if value == 'met')
            rated = [{'item': row['item'], 'rater_a': 'not_met', 'rater_b': 'not_met'} for row in rows]
            result = agreement(rated, key)
            self.assertEqual(result['raters_agree_system_differs'], [met_item])
            self.assertEqual(learner_summary(db)['learners']['L001']['attempts'], 1)
            db.close()


class TestUpgradeVisibility(unittest.TestCase):
    def test_every_seeded_lesson_uses_the_new_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            training = TrainingService(Path(folder) / 'upgrade.db')
            activities = training.context.catalog.activities()
            self.assertEqual([a['id'] for a in activities if not a['upgraded']], [])

    def test_older_saved_sessions_can_be_told_apart(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            training = TrainingService(Path(folder) / 'upgrade.db')
            new = training.create_session('demo', 'english-speaking', 'advanced', 'english-28')['id']
            with patch('intelligence.scenario_contracts.compile_case', return_value=None):
                old = training.create_session('demo', 'english-speaking', 'beginner', 'english-02')['id']
            versions = {row['id']: row['engine_version'] for row in training.context.progress.history('demo')}
            self.assertEqual(versions[new], 3)
            self.assertEqual(versions[old], 2)


class TestMetrics(unittest.TestCase):
    def test_metrics_catch_the_recorded_failure(self):
        transcript = [
            {'role': 'ai', 'speaker': 'Alex', 'text': 'Before we accept this decision, we have concerns.'},
            {'role': 'learner', 'speaker': 'You', 'text': 'I do not understand'},
            {'role': 'ai', 'speaker': 'Maya', 'text': 'Alex, Learner, could you quantify the 40 hours of cost?'},
            {'role': 'ai', 'speaker': 'Alex', 'text': 'Maya, I do not have the budget data.'},
        ]
        result = evaluate(transcript, ai_names=['Alex', 'Maya'])
        failed = failed_gates(result)
        for gate in ('invented_numbers', 'says_learner', 'confusion_ignored', 'ai_to_ai'):
            self.assertIn(gate, failed)

    def test_private_number_is_a_leak_unless_the_learner_said_it_first(self):
        said = evaluate([{'role': 'ai', 'speaker': 'A', 'text': 'My limit is USD 10000.'}], private_numbers=[10000])
        self.assertEqual(len(said['private_leaks']), 1)
        echoed = evaluate([{'role': 'learner', 'speaker': 'You', 'text': 'Would you take 10000?'}, {'role': 'ai', 'speaker': 'A', 'text': 'Not at USD 10000.'}], private_numbers=[10000])
        self.assertEqual(echoed['private_leaks'], [])

    def test_confusion_detection(self):
        self.assertTrue(is_confused('And what am I supposed to tell you'))
        self.assertFalse(is_confused('I understand your concern about the rota'))


if __name__ == '__main__':
    unittest.main()
