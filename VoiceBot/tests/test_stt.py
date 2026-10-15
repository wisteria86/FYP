import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.stt_whisper import WhisperSTT


class _QuietSpeechModel:
    def __init__(self):
        self.vad_calls = []

    def transcribe(self, _audio, **options):
        self.vad_calls.append(options["vad_filter"])
        if options["vad_filter"]:
            return iter(()), None
        return iter((SimpleNamespace(text=" quiet but valid speech", no_speech_prob=0.2),)), None


class WhisperSTTTests(unittest.TestCase):
    def test_cuda_detection_checks_compute_types_not_device_name(self):
        with patch("ctranslate2.get_supported_compute_types", return_value={"float16", "int8"}):
            self.assertTrue(WhisperSTT._cuda_available())

    def test_quiet_browser_audio_retries_without_second_vad(self):
        stt = WhisperSTT.__new__(WhisperSTT)
        stt.model = _QuietSpeechModel()

        self.assertEqual(stt.transcribe(b"browser-audio"), "quiet but valid speech")
        self.assertEqual(stt.model.vad_calls, [True, False])

    def test_detailed_transcription_forces_lesson_language_and_reports_confidence(self):
        class Model:
            def __init__(self): self.options = None
            def transcribe(self, _audio, **options):
                self.options = options
                segment = SimpleNamespace(text=" my name is Visteria", no_speech_prob=.05, avg_logprob=-.2)
                info = SimpleNamespace(language="en", language_probability=.98)
                return iter((segment,)), info

        stt = WhisperSTT.__new__(WhisperSTT)
        stt.model = Model()
        result = stt.transcribe_detailed(b"browser-audio", "en", "First Greetings")
        self.assertEqual(result["text"], "my name is Visteria")
        self.assertEqual(result["detected_language"], "en")
        self.assertGreater(result["confidence"], .7)
        self.assertEqual(stt.model.options["language"], "en")
        self.assertEqual(stt.model.options["initial_prompt"], "First Greetings")
        self.assertEqual(stt.model.options["task"], "transcribe")
        self.assertEqual(stt.model.options["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()
