import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from modules.llm_quota import ProviderQuota,QuotaDeferred,seconds,shared_quota
from modules.llm_brain import LLMBrain


class QuotaTests(unittest.TestCase):
    def test_retry_after_is_shared_and_does_not_send_retries(self):
        now=[10.0];gate=ProviderQuota(lambda:now[0])
        gate.observe({'Retry-After':'32'},limited=True)
        with self.assertRaises(QuotaDeferred) as caught:gate.reserve(10)
        self.assertEqual(caught.exception.retry_after,32)
        self.assertEqual(gate.requests,0)
        now[0]=42;gate.reserve(10)
        self.assertEqual(gate.requests,1)
        self.assertIs(shared_quota('https://test','secret','m'),shared_quota('https://test/','secret','m'))
        self.assertIsNot(shared_quota('https://test','secret','m'),shared_quota('https://test','other','m'))

    def test_token_budget_and_background_priority(self):
        now=[10.0];gate=ProviderQuota(lambda:now[0])
        gate.observe({'x-ratelimit-remaining-tokens':'500','x-ratelimit-reset-tokens':'1m2s'})
        gate.reserve(300)
        with self.assertRaises(QuotaDeferred):gate.reserve(300)
        with self.assertRaises(QuotaDeferred):gate.reserve(10,background=True)
        now[0]=23;gate.reserve(10,background=True)
        now[0]=73;gate.reserve(800)

    def test_header_durations_and_missing_headers(self):
        self.assertEqual(seconds('1m2.5s'),62.5)
        self.assertEqual(seconds('125ms'),.125)
        self.assertEqual(seconds('invalid',15),15)
        gate=ProviderQuota();gate.observe({});gate.reserve(500)

    def test_actual_429_suppresses_next_call_and_reads_success_headers(self):
        brain=LLMBrain.__new__(LLMBrain);brain.quota=ProviderQuota()
        brain.client=Mock()
        exc=RuntimeError('limited');exc.status_code=429;exc.response=SimpleNamespace(headers={'retry-after':'30'})
        create=brain.client.chat.completions.with_raw_response.create
        create.side_effect=exc
        with self.assertRaises(RuntimeError):brain._create(messages=[],max_tokens=10)
        with self.assertRaises(QuotaDeferred):brain._create(messages=[],max_tokens=10)
        self.assertEqual(create.call_count,1)

    def test_group_stream_validates_ids_order_and_closes(self):
        brain=LLMBrain.__new__(LLMBrain);brain.model_name='test';brain.base_url='local'
        class Stream:
            closed=False
            def __iter__(self):
                for token in ['{"participant_id":"p1","text":"First."}\n', '{"participant_id":"p2","text":"Second."}']:
                    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=token))])
            def close(self):self.closed=True
        stream=Stream();brain._create=Mock(return_value=stream)
        prompt={'instructions':'test','context':{},'speaker_ids':['p1','p2']}
        self.assertEqual(len(list(brain.generate_group_response(prompt))),2)
        self.assertTrue(stream.closed)
        for bad in [{'participant_id':'learner','text':'Hello'}, {'participant_id':'p2','text':'Hello'}, {'participant_id':'p1','text':''}]:
            with self.assertRaises(ValueError):brain._validate_group_line(bad,['p1','p2'],0)

    def test_diagnostics_keep_quota_numbers_without_organization_identity(self):
        gate=ProviderQuota()
        gate.observe_error('organization org_private on tokens per day (TPD): Limit 200000, Used 199900, Requested 1600. Try again later')
        self.assertEqual(gate.limit_reason['kind'],'tokens per day')
        self.assertNotIn('org_private',str(gate.limit_reason))
