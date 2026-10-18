import threading
import unittest
from unittest.mock import Mock,patch
import numpy as np
from modules.stt_nemotron import NemotronSTT


class NemotronRateTests(unittest.TestCase):
    def setUp(self):
        self.model=NemotronSTT.__new__(NemotronSTT)
        self.model._lock=threading.Lock()
        self.model.recognizer=Mock()
        self.model.recognizer.create_stream.side_effect=lambda:Mock()
        self.model.recognizer.is_ready.return_value=False
        self.model.recognizer.get_result.return_value='Hello neighbour.'

    def test_browser_rates_are_preserved_in_final_padding(self):
        for rate in (16000,44100,48000):
            with self.subTest(rate=rate):
                stream=self.model.create_stream()
                self.model.accept_audio(stream,np.zeros(4096,dtype=np.float32),rate)
                result=self.model.finish_stream(stream)
                calls=stream.native.accept_waveform.call_args_list
                self.assertEqual([call.args[0] for call in calls],[rate,rate])
                self.assertEqual(len(calls[-1].args[1]),rate)
                self.assertTrue(result['final'])

    def test_rate_change_is_rejected_before_native_call(self):
        stream=self.model.create_stream()
        self.model.accept_audio(stream,np.zeros(4096,dtype=np.float32),48000)
        with self.assertRaisesRegex(ValueError,'cannot change'):
            self.model.accept_audio(stream,np.zeros(4096,dtype=np.float32),16000)
        self.assertEqual(stream.native.accept_waveform.call_count,1)

    def test_interleaved_captures_do_not_share_rates(self):
        streams=[self.model.create_stream(),self.model.create_stream()]
        for stream,rate in zip(streams,(44100,48000)):
            self.model.accept_audio(stream,np.zeros(4096,dtype=np.float32),rate)
        for stream,rate in zip(streams,(44100,48000)):
            self.model.finish_stream(stream)
            self.assertEqual(stream.native.accept_waveform.call_args.args[0],rate)

    def test_empty_capture_and_duplicate_finish_are_safe(self):
        stream=self.model.create_stream()
        self.model.finish_stream(stream)
        with self.assertRaisesRegex(ValueError,'already finalized'):
            self.model.finish_stream(stream)
        with self.assertRaisesRegex(ValueError,'already finalized'):
            self.model.accept_audio(stream,np.zeros(10),16000)
        stream.native.input_finished.assert_called_once()

    def test_shorter_padding_preserves_capture_rate_and_exposes_decoding(self):
        self.model.final_padding_seconds=0.5
        stream=self.model.create_stream()
        self.model.accept_audio(stream,np.zeros(4096,dtype=np.float32),48000)
        self.model.recognizer.is_ready.side_effect=[True,True,False,False]
        result=self.model.finish_stream(stream)
        self.assertEqual(len(stream.native.accept_waveform.call_args.args[1]),24000)
        timing=result['finalize_timing']
        self.assertEqual(timing['decode_steps'],2)
        self.assertEqual(timing['padding_seconds'],0.5)
        self.assertEqual(timing['sample_rate'],48000)
        for name in ('lock_wait_ms','padding_and_finish_ms','decode_ms','result_ms'):
            self.assertGreaterEqual(timing[name],0)
        self.assertEqual(result['text'],'Hello neighbour.')

    def test_audio_diagnostics_exclude_synthetic_padding(self):
        stream=self.model.create_stream()
        self.model.accept_audio(stream,np.full(16000,0.25,dtype=np.float32),16000)
        result=self.model.finish_stream(stream)
        self.assertEqual(result['input_audio'],{'duration_ms':1000.0,'rms':0.25,'peak':0.25})

    def test_nonfinite_audio_rejected_before_native_call(self):
        stream=self.model.create_stream()
        with self.assertRaisesRegex(ValueError,'non-finite'):
            self.model.accept_audio(stream,np.array([float('nan')]),16000)
        stream.native.accept_waveform.assert_not_called()

    def test_recorded_audio_uses_bounded_chunks_like_known_speech_check(self):
        import sys
        import types
        audio=types.ModuleType('faster_whisper.audio')
        audio.decode_audio=Mock(return_value=np.ones(10000,dtype=np.float32)*0.1)
        native=Mock()
        self.model.recognizer.create_stream.side_effect=lambda:native
        with patch.dict(sys.modules,{'faster_whisper.audio':audio}):
            result=self.model.transcribe_detailed(b'encoded recording','en')
        lengths=[len(call.args[1]) for call in native.accept_waveform.call_args_list]
        self.assertEqual(lengths,[4096,4096,1808,16000])
        audio.decode_audio.assert_called_once()
        self.assertEqual(result['input_audio']['duration_ms'],625.0)
        self.assertEqual(result['text'],'Hello neighbour.')

    def test_empty_short_speech_gets_extra_padding_before_finish(self):
        stream=self.model.create_stream()
        self.model.accept_audio(stream,np.ones(16000,dtype=np.float32)*0.1,16000)
        self.model.recognizer.get_result.side_effect=['','','','Hello','Hello']
        result=self.model.finish_stream(stream)
        self.assertEqual(result['text'],'Hello')
        self.assertGreater(result['finalize_timing']['padding_seconds'],1.0)
        self.assertLessEqual(result['finalize_timing']['padding_seconds'],3.0)
        stream.native.input_finished.assert_called_once()

    def test_silence_does_not_trigger_extended_flush(self):
        self.model.recognizer.get_result.return_value=''
        stream=self.model.create_stream()
        self.model.accept_audio(stream,np.zeros(16000,dtype=np.float32),16000)
        result=self.model.finish_stream(stream)
        self.assertEqual(result['finalize_timing']['padding_seconds'],1.0)

    def test_empty_result_flush_is_bounded(self):
        self.model.recognizer.get_result.return_value=''
        stream=self.model.create_stream()
        self.model.accept_audio(stream,np.ones(16000,dtype=np.float32)*0.1,16000)
        result=self.model.finish_stream(stream)
        self.assertEqual(result['text'],'')
        self.assertAlmostEqual(result['finalize_timing']['padding_seconds'],3.0)
