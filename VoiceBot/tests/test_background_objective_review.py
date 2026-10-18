import asyncio
import unittest
from unittest.mock import Mock, patch

from services.training_orchestrator import TrainingOrchestrator


class BackgroundObjectiveReviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = {'skill_id': 'english', 'turns': [{'role': 'user'}]}
        self.training = Mock()
        self.training.session.return_value = self.session
        self.training.completion_review_prompt.return_value = 'snapshot'
        self.metrics = Mock()
        self.llm = Mock()
        self.engine = TrainingOrchestrator(self.training, self.llm, None, self.metrics, 24000, 'kokoro')
        self.future = asyncio.get_running_loop().create_future()
        self.executor = patch.object(asyncio.get_running_loop(), 'run_in_executor', return_value=self.future)
        self.submit = self.executor.start()

    async def asyncTearDown(self):
        self.executor.stop()
        self.engine._objective_reviews.pop((id(self.training), 'session'), None)
        if not self.future.done():
            self.future.cancel()
        await asyncio.sleep(0)

    async def test_review_never_blocks_or_saves_mid_turn(self):
        self.engine._start_objective_review('session')
        self.assertFalse(self.future.done())
        self.engine._consume_objective_review('session', self.session)
        self.training.save_completion_review.assert_not_called()
        other = TrainingOrchestrator(self.training, self.llm, None, self.metrics, 24000, 'kokoro')
        other._start_objective_review('session')
        self.submit.assert_called_once()
        self.future.set_result(({'criteria': []}, 120))
        self.training.save_completion_review.assert_not_called()
        other._consume_objective_review('session', self.session)
        self.training.save_completion_review.assert_called_once_with('session', {'criteria': []}, 1)
        self.assertEqual(self.metrics.record.call_args.args[2], 120)

    async def test_stale_review_is_discarded(self):
        self.engine._start_objective_review('session')
        self.future.set_result(({'criteria': []}, 120))
        self.session['turns'].append({'role': 'user'})
        self.engine._consume_objective_review('session', self.session)
        self.training.save_completion_review.assert_not_called()
        self.assertNotIn((id(self.training), 'session'), self.engine._objective_reviews)

    async def test_failed_review_retains_local_checks(self):
        self.engine._start_objective_review('session')
        self.future.set_exception(RuntimeError('offline'))
        self.engine._consume_objective_review('session', self.session)
        self.training.save_completion_review.assert_not_called()
        self.assertFalse(self.metrics.record.call_args.args[3])
