import unittest
from unittest.mock import Mock,patch
from modules.stt_router import SpeechRecognitionRouter
from services.recognition_quality import compare_transcripts,session_vocabulary


class RecognitionQualityTests(unittest.TestCase):
    def result(self,original,text,confidence=.8):return compare_transcripts(original,{'text':text,'confidence':confidence})

    def test_small_acoustic_correction_retains_original(self):
        result=self.result('I would like ten seeds please','I would like ten seats please.')
        self.assertFalse(result['needs_retry'])
        self.assertIn('seeds',result['original_text'])
        self.assertEqual(result['final_pass'],'whisper')

    def test_numbers_negation_and_large_changes_require_review(self):
        for first,second in [('I offer ten thousand','I offer two thousand'),
                ('I can accept this offer','I cannot accept this offer'),
                ('Tell Sam about the plan','Sell them all the land'),
                ('I accept','I do not accept')]:
            with self.subTest(first=first):self.assertTrue(self.result(first,second)['needs_retry'])

    def test_confidence_empty_and_deliberate_short_answers(self):
        self.assertTrue(self.result('some words','some words',.2)['needs_retry'])
        self.assertTrue(self.result('some words','')['needs_retry'])
        self.assertFalse(self.result('yes','Yes.')['needs_retry'])
        self.assertFalse(self.result('I offer ten seats','I offer 10 seats')['needs_retry'])

    def test_vocabulary_uses_public_facts_not_private_preparation_or_documents(self):
        definition={'participants':[{'name':'Sam','private_knowledge':{'secret':'Cobalt'}}],
                    'facts':['Training seats include support.','There is no established vulnerability.'],'preparation':{'walkaway':'Helium'},'documents':['Xenon']}
        words=session_vocabulary(definition)
        self.assertIn('Sam',words);self.assertIn('seats',words)
        for private in ['Cobalt','Helium','Xenon','vulnerability']:self.assertNotIn(private,words)
        self.assertLessEqual(len(session_vocabulary({'facts':['Vocabulary '*1000]})),500)

    def test_explicit_final_pass_uses_audio_and_cached_local_model(self):
        primary=Mock(device='cuda');router=SpeechRecognitionRouter(primary,allow_fallback=False)
        with patch('modules.stt_whisper.WhisperSTT') as factory:
            factory.return_value.transcribe_detailed.return_value={'text':'Ten seats please','confidence':.8}
            for _ in range(2):
                result=router.transcribe_final(b'actual audio','en','Sam, seats','Ten seeds please')
            factory.assert_called_once()
            self.assertTrue(factory.call_args.kwargs['local_files_only'])
            factory.return_value.transcribe_detailed.assert_called_with(b'actual audio','en','Sam, seats')
            primary.transcribe_detailed.assert_not_called()
            self.assertFalse(result['needs_retry'])

    def test_verifier_failure_keeps_live_text_and_requires_review(self):
        router=SpeechRecognitionRouter(Mock(device='cuda'),allow_fallback=False)
        with patch('modules.stt_whisper.WhisperSTT',side_effect=RuntimeError('not installed')):
            result=router.transcribe_final(b'audio','en',None,'Ten seats please')
        self.assertEqual(result['text'],'Ten seats please')
        self.assertTrue(result['needs_retry'])
        self.assertEqual(result['final_pass'],'unavailable')
