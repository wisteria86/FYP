import io
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np
from modules import tts_english as module


class EnglishTTSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / 'voice'
        self.directory.mkdir()
        self.runtime = Mock(sample_rate=22050, num_speakers=8)
        self.runtime.generate.return_value = types.SimpleNamespace(
            samples=np.ones(2205), sample_rate=22050)
        self.config = Mock()
        self.config.validate.return_value = True
        self.sherpa = types.SimpleNamespace(
            OfflineTtsVitsModelConfig=Mock(), OfflineTtsKittenModelConfig=Mock(),
            OfflineTtsModelConfig=Mock(), OfflineTtsConfig=Mock(return_value=self.config),
            OfflineTts=Mock(return_value=self.runtime))

    def tearDown(self):
        self.temp.cleanup()

    def build(self, engine):
        with patch.dict('sys.modules', {'sherpa_onnx': self.sherpa}), patch.object(module, 'ensure_model', return_value=self.directory):
            return module.EnglishOnnxTTS(engine)

    def test_both_models_generate_float32_at_native_rate(self):
        for name in ('piper', 'kitten'):
            with self.subTest(engine=name):
                engine = self.build(name)
                self.assertEqual(engine.output_sample_rate, 22050)
                stream = engine.synthesize('Hello there.', speed=1.2)
                pcm = next(stream)
                self.assertIsInstance(pcm, bytes)
                self.assertEqual(np.frombuffer(pcm, dtype=np.float32).size, 2205)
                self.assertEqual(pcm.tts_timing['engine'], name)
                self.runtime.generate.assert_called_with('Hello there.', sid=0, speed=1.2)
                self.assertEqual(engine.runtime_info()['device'], 'cpu')
        self.sherpa.OfflineTtsVitsModelConfig.assert_called_once()
        self.sherpa.OfflineTtsKittenModelConfig.assert_called_once()

    def test_long_reply_is_lazy_and_bounded(self):
        engine = self.build('kitten')
        stream = engine.synthesize('Hello world. ' * 40)
        self.runtime.generate.assert_not_called()
        next(stream)
        self.assertEqual(self.runtime.generate.call_count, 1)
        list(stream)
        self.assertTrue(all(len(call.args[0]) <= 180 for call in self.runtime.generate.call_args_list))

    def test_empty_input_and_empty_output(self):
        engine = self.build('piper')
        self.assertEqual(list(engine.synthesize(' ')), [])
        self.runtime.generate.return_value.samples = []
        with self.assertRaisesRegex(RuntimeError, 'no audio'):
            list(engine.synthesize('Hello'))

    def test_native_failures_propagate(self):
        engine = self.build('kitten')
        self.runtime.generate.side_effect = RuntimeError('native error')
        with self.assertRaisesRegex(RuntimeError, 'native error'):
            list(engine.synthesize('Hello'))

    def test_incomplete_custom_model_never_downloads(self):
        with patch.dict('os.environ', {'PIPER_MODEL_DIR': str(self.directory)}), patch.object(module.urllib.request, 'urlopen') as download:
            with self.assertRaises(FileNotFoundError):
                module.ensure_model('piper')
            download.assert_not_called()

    def test_download_validates_and_publishes_package(self):
        package, model = module.PACKAGES['kitten']
        content = io.BytesIO()
        with tarfile.open(fileobj=content, mode='w:bz2') as archive:
            folder = tarfile.TarInfo(package + '/espeak-ng-data')
            folder.type = tarfile.DIRTYPE
            archive.addfile(folder)
            for name in (model, 'tokens.txt', 'voices.bin'):
                member = tarfile.TarInfo(package + '/' + name)
                member.size = 4
                archive.addfile(member, io.BytesIO(b'test'))
        destination = Path(self.temp.name) / package
        with patch.object(module, 'model_directory', return_value=destination), patch.dict('os.environ', {}, clear=True), patch.object(module.urllib.request, 'urlopen', return_value=io.BytesIO(content.getvalue())) as download:
            self.assertEqual(module.ensure_model('kitten'), destination)
            self.assertTrue(module.installed('kitten', destination))
            module.ensure_model('kitten')
            download.assert_called_once()

    def test_archive_traversal_rejected(self):
        content = io.BytesIO()
        with tarfile.open(fileobj=content, mode='w:bz2') as archive:
            member = tarfile.TarInfo('../escape')
            archive.addfile(member)
        with patch.object(module, 'model_directory', return_value=Path(self.temp.name)/'bad'), patch.dict('os.environ', {}, clear=True), patch.object(module.urllib.request, 'urlopen', return_value=io.BytesIO(content.getvalue())):
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                module.ensure_model('piper')
        self.assertFalse((Path(self.temp.name)/'escape').exists())
