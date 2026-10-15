import unittest
from unittest.mock import Mock,patch
from modules.stt_router import create_stt,SpeechRecognitionRouter


class STTRouterTests(unittest.TestCase):
    def test_explicit_cpu_nemotron_is_allowed_without_cuda(self):
        nvidia=Mock();factory=Mock()
        router=create_stt(cuda_available=False,nemotron_factory=lambda:nvidia,whisper_factory=factory,engine='nemotron',device='cpu')
        self.assertIs(router.primary,nvidia);factory.assert_not_called()

    def test_selected_whisper_onnx_uses_real_adapter_on_cpu(self):
        with patch('modules.stt_whisper_onnx.WhisperOnnxSTT') as factory:
            create_stt(cuda_available=False,engine='whisper_small_onnx',device='auto')
        self.assertEqual(factory.call_args.args[0],'small')
        self.assertEqual(factory.call_args.args[2],'cpu')

    def test_no_gpu_never_initializes_nvidia(self):
        nvidia=Mock()
        whisper=Mock(runtime_info=lambda:{'device':'cpu','model':'medium'})
        factory=Mock(return_value=whisper)
        router=create_stt(cuda_available=False,nemotron_factory=nvidia,whisper_factory=factory)
        nvidia.assert_not_called();factory.assert_called_once()
        self.assertEqual(router.runtime_info()['engine'],'whisper')
        self.assertFalse(router.supports_streaming('English'))

    def test_gpu_english_uses_nvidia_without_loading_whisper(self):
        nvidia=Mock()
        factory=Mock()
        with patch('config.Config.STT_ENGINE','auto'):
            router=create_stt(cuda_available=True,nemotron_factory=lambda:nvidia,whisper_factory=factory)
        router.transcribe_detailed(b'audio','en')
        nvidia.transcribe_detailed.assert_called_once_with(b'audio','en',None)
        factory.assert_not_called()

    def test_other_languages_use_lazy_whisper(self):
        whisper=Mock();factory=Mock(return_value=whisper)
        router=SpeechRecognitionRouter(Mock(),factory)
        router.transcribe_detailed(b'audio','ur')
        router.transcribe_detailed(b'more','ar')
        factory.assert_called_once()
        self.assertEqual(whisper.transcribe_detailed.call_count,2)

    def test_nvidia_startup_failure_keeps_recognition_available(self):
        whisper=Mock()
        with patch('config.Config.STT_ENGINE','auto'):
            router=create_stt(cuda_available=True,nemotron_factory=Mock(side_effect=RuntimeError('missing CUDA DLL')),whisper_factory=lambda:whisper)
        self.assertIsNone(router.primary)
        self.assertIn('missing CUDA DLL',router.fallback_reason)

    def test_nvidia_decode_failure_retries_recording_with_whisper(self):
        nvidia=Mock();nvidia.transcribe_detailed.side_effect=RuntimeError('decoder failed')
        whisper=Mock();whisper.transcribe_detailed.return_value={'text':'Hello.'}
        router=SpeechRecognitionRouter(nvidia,lambda:whisper)
        self.assertEqual(router.transcribe_detailed(b'audio','en')['text'],'Hello.')
