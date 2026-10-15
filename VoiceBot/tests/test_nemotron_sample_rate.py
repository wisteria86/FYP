import threading
import unittest
from unittest.mock import Mock
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
