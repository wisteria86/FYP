"""Take that back, practice branches, honest evidence and the public reaction label."""
import json
from contextlib import closing
from datetime import datetime, timezone
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import isolated_environment  # noqa: F401  keeps tests away from data/hikari.db
from core.training_service import TrainingService
from domain.errors import DomainError
from intelligence import scene_director as director
from intelligence.scenario_contracts import learner_definition


def turn(text, request_id):
    return SimpleNamespace(text=text, duration_seconds=1, request_id=request_id, expected_revision=None,
                           addressed_participant_ids=[], recognition={})


class RewindTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.training = TrainingService(Path(self.folder.name) / 'rewind.db')
        self.runtime = self.training.context.runtime

    def tearDown(self):
        self.folder.cleanup()

    def finish_reply(self, sid, text='Nice to meet you.'):
        """Stand in for the model: record a reply and give the floor back to the learner."""
        with self.runtime.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            definition, state = self.runtime.read(sid, db)
            ai = next(p for p in definition['participants'] if p['kind'] == 'ai')
            db.execute("INSERT INTO turns(session_id,role,text,duration_seconds,created_at,speaker_name,participant_id) VALUES (?,?,?,?,?,?,?)",
                       (sid, 'assistant', text, 0, datetime.now(timezone.utc).isoformat(), ai['name'], ai['id']))
            db.execute("UPDATE conversation_requests SET status='done',result_json='{}' WHERE session_id=? AND request_id=?", (sid, state['generation']))
            state.update(generation=None, floor='learner')
            self.runtime.emit(db, sid, state, 'response_done', {})

    def session(self, activity='english-02', skill='english-speaking', level='beginner'):
        return self.training.create_session('demo', skill, level, activity)['id']

    def turns(self, sid):
        with closing(sqlite3.connect(Path(self.folder.name) / 'rewind.db')) as db:
            return [row[0] for row in db.execute("SELECT text FROM turns WHERE session_id=? ORDER BY id", (sid,))]

    def test_taking_a_turn_back_restores_the_scene_exactly(self):
        sid = self.session()
        self.runtime.start(sid, turn('Hello, my name is Sara.', 'r1'))
        self.finish_reply(sid)
        _, before = self.runtime.read(sid)
        self.runtime.start(sid, turn('I am from Lahore and I work in sales.', 'r2'))
        self.finish_reply(sid, 'Lahore! What do you do there?')
        restored = self.runtime.rewind(sid)
        self.assertEqual(restored['rewinds'], 1)
        for key in ('scene', 'offers', 'evidence_revision', 'latest_input', 'learner_name', 'support_turns', 'coach'):
            self.assertEqual(restored.get(key), before.get(key), key)
        self.assertEqual(restored['floor'], 'learner')
        self.assertIsNone(restored['generation'])
        self.assertGreater(restored['revision'], before['revision'])
        texts = self.turns(sid)
        self.assertIn('Hello, my name is Sara.', texts)
        self.assertNotIn('I am from Lahore and I work in sales.', texts)
        self.assertNotIn('Lahore! What do you do there?', texts)

    def test_taken_back_turns_stay_on_record_but_out_of_the_assessed_conversation(self):
        sid = self.session()
        self.runtime.start(sid, turn('Hello, I am Sara.', 'r1'))
        self.finish_reply(sid)
        self.runtime.rewind(sid)
        with closing(sqlite3.connect(Path(self.folder.name) / 'rewind.db')) as db:
            withdrawn = db.execute('SELECT role,text,rewind FROM withdrawn_turns WHERE session_id=? ORDER BY id', (sid,)).fetchall()
        self.assertEqual(withdrawn, [('user', 'Hello, I am Sara.', 1), ('assistant', 'Nice to meet you.', 1)])
        detail = self.training.context.session.session(sid)
        self.assertNotIn('Hello, I am Sara.', [item['text'] for item in detail['turns']])
        context = self.runtime.evaluation_context(sid)
        self.assertNotIn('Hello, I am Sara.', json.dumps(context))

    def test_a_turn_cannot_be_taken_back_mid_reply_or_before_there_is_one(self):
        sid = self.session()
        with self.assertRaises(DomainError) as nothing:
            self.runtime.rewind(sid)
        self.assertEqual(nothing.exception.code, 'nothing_to_rewind')
        self.runtime.start(sid, turn('Hello there.', 'r1'))
        with self.assertRaises(DomainError) as busy:
            self.runtime.rewind(sid)
        self.assertEqual(busy.exception.code, 'floor_busy')

    def test_new_turns_after_a_rewind_can_be_taken_back_again(self):
        sid = self.session()
        self.runtime.start(sid, turn('First try.', 'r1'))
        self.finish_reply(sid)
        self.runtime.rewind(sid)
        self.runtime.start(sid, turn('Second try, better.', 'r2'))
        self.finish_reply(sid)
        self.assertEqual(self.runtime.rewind(sid)['rewinds'], 2)
        self.assertNotIn('Second try, better.', self.turns(sid))

    def test_a_practice_branch_starts_from_the_chosen_moment_and_leaves_the_original_alone(self):
        sid = self.session()
        self.runtime.start(sid, turn('Hello, my name is Sara.', 'r1'))
        self.finish_reply(sid)
        self.runtime.start(sid, turn('I am from Karachi.', 'r2'))
        self.finish_reply(sid)
        with closing(sqlite3.connect(Path(self.folder.name) / 'rewind.db')) as db:
            moment = db.execute("SELECT id FROM turns WHERE session_id=? AND text='I am from Karachi.'", (sid,)).fetchone()[0]
        branch = self.training.context.session.branch_session('demo', sid, moment)
        self.assertNotEqual(branch['id'], sid)
        self.assertEqual(branch['status'], 'active')
        branch_texts = self.turns(branch['id'])
        self.assertIn('Hello, my name is Sara.', branch_texts)
        self.assertNotIn('I am from Karachi.', branch_texts)
        self.assertIn('I am from Karachi.', self.turns(sid))
        _, state = self.runtime.read(branch['id'])
        self.assertEqual(state['branch'], {'from': sid, 'turn_id': moment})
        self.assertGreaterEqual(state['rewinds'], 1)
        # The branch can be played on and taken back like any lesson.
        self.runtime.start(branch['id'], turn('I am from Lahore, actually.', 'b1'))
        self.finish_reply(branch['id'])
        self.runtime.rewind(branch['id'])
        with self.assertRaises(ValueError):
            self.training.context.session.branch_session('someone-else', sid, moment)

    def test_lessons_with_retries_never_count_as_shown_independently(self):
        sid = self.session()
        path = self.training.context.learning_path
        with path.connect() as db:
            db.execute("UPDATE sessions SET status='completed',completed_at=datetime('now') WHERE id=?", (sid,))
            db.execute("INSERT INTO assessments(id,session_id,overall,scores,strengths,improvements,evidence,feedback,created_at) VALUES ('a1',?,90,?,'[\"Clear greeting\"]','[]','[]','ok',datetime('now'))",
                       (sid, json.dumps({'task_achievement': 100})))
            evidence, _ = path._evidence(db, 'demo')
        self.assertTrue(evidence['english-02']['passed'])
        with path.connect() as db:
            state = json.loads(db.execute('SELECT state_json FROM conversation_runtime WHERE session_id=?', (sid,)).fetchone()[0])
            state['rewinds'] = 1
            db.execute('UPDATE conversation_runtime SET state_json=? WHERE session_id=?', (json.dumps(state), sid))
            evidence, _ = path._evidence(db, 'demo')
        self.assertFalse(evidence['english-02']['passed'])
        self.assertEqual(evidence['english-02']['retried'], 1)

    def test_deleting_conversation_data_also_removes_snapshots_and_taken_back_turns(self):
        from api.routers.conversation import build_conversation_router
        sid = self.session()
        self.runtime.start(sid, turn('Hello, I am Sara.', 'r1'))
        self.finish_reply(sid)
        self.runtime.rewind(sid)
        router = build_conversation_router(self.training, lambda request, session_id: {'user_id': 'demo'}, lambda: None)
        erase = next(route.endpoint for route in router.routes if route.path.endswith('/conversation-data'))
        erase(sid, None)
        with closing(sqlite3.connect(Path(self.folder.name) / 'rewind.db')) as db:
            for table in ('turn_snapshots', 'withdrawn_turns'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table} WHERE session_id=?', (sid,)).fetchone()[0], 0, table)


class GameTapeTests(RewindTests):
    def test_the_game_tape_marks_evidence_and_never_includes_private_instructions(self):
        sid = self.session('activity-negotiation', 'negotiation', 'intermediate')
        self.runtime.start(sid, turn('What matters most to you on delivery?', 'r1'))
        self.runtime.direct_turn(sid, director.read_local('What matters most to you on delivery?'))
        self.finish_reply(sid, 'Delivery timing matters to us.')
        with self.runtime.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            definition, state = self.runtime.read(sid, db)
            learner = db.execute("SELECT id FROM turns WHERE session_id=? AND role='user'", (sid,)).fetchone()['id']
            state['evaluation'] = {'criteria': [{'objective_id': definition['objectives'][1]['id'], 'met': True, 'quotes': ['What matters most'], 'turn_ids': [learner], 'support': 'independent'}],
                                   'corrections': [{'original': 'on delivery', 'improved': 'about the delivery date'}]}
            self.runtime.emit(db, sid, state, 'reviewed', {})
        tape = self.training.context.assessment.game_tape(sid)
        mine = next(item for item in tape['turns'] if item['id'] == learner)
        kinds = {mark['kind'] for mark in mine['marks']}
        self.assertIn('strong', kinds)
        self.assertIn('correction', kinds)
        self.assertTrue(mine['replayable'])
        self.assertIn('reaction', mine)
        self.assertTrue(tape['expert'])
        text = json.dumps(tape)
        for private in ('directions', '_purpose', 'signals', 'floor'):
            self.assertNotIn(f'"{private}"', text)
        self.assertNotIn(definition['beats'][0]['goal'], text)


class ReactionTests(unittest.TestCase):
    def test_reactions_are_coarse_labels_from_the_characters_move(self):
        self.assertEqual(director.reaction_for({'_bargain': 'hold'}), 'doubtful')
        self.assertEqual(director.reaction_for({'_bargain': 'confirm_terms'}), 'pleased')
        self.assertEqual(director.reaction_for({'_bargain': 'final_position'}), 'firm')
        self.assertEqual(director.reaction_for({'_move': 'rephrase_simple'}), 'encouraging')
        self.assertEqual(director.reaction_for({'_move': 'answer'}, 'off_topic'), 'puzzled')
        self.assertEqual(director.reaction_for({'_move': 'something_new'}), 'neutral')

    def test_a_negotiation_turn_shows_only_labels_and_never_the_private_position(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            training = TrainingService(Path(folder) / 'reaction.db')
            runtime = training.context.runtime
            sid = training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')['id']
            runtime.start(sid, turn('We could pay USD 7000 for the package.', 'r1'))
            runtime.direct_turn(sid, director.read_local('We could pay USD 7000 for the package.'))
            view = runtime.view(sid)
            self.assertTrue(view['reactions'])
            self.assertTrue(set(view['reactions'].values()) <= set(director.REACTIONS))
            definition, state = runtime.read(sid)
            private = json.dumps({k: v for k, v in (definition.get('negotiation') or {}).items() if k not in {'public', 'buyer'}})
            public = json.dumps(view)
            for key in ('directions', 'scene_private', 'floor_price'):
                self.assertNotIn(f'"{key}"', public)
            self.assertNotIn('"seller"', public)
            self.assertTrue(private)

    def test_the_public_definition_lists_steps_without_the_characters_goals(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            training = TrainingService(Path(folder) / 'beats.db')
            sid = training.create_session('demo', 'negotiation', 'intermediate', 'activity-negotiation')['id']
            definition, _ = training.context.runtime.read(sid)
            public = learner_definition(definition)
            self.assertTrue(public['beats'])
            for beat in public['beats']:
                self.assertEqual(set(beat), {'id', 'objectives'})
            self.assertNotIn('signals', json.dumps(public['beats']))
            self.assertNotIn(definition['beats'][0]['goal'], json.dumps(public))


if __name__ == '__main__':
    unittest.main()
