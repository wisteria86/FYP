import unittest
from unittest.mock import Mock,patch
from modules.stt_router import create_stt,SpeechRecognitionRouter


class STTRouterTests(unittest.TestCase):
    def test_decoder_selection_reuses_primary_and_rejects_invalid_methods(self):
        primary=Mock(decoding_method='greedy_search')
        router=SpeechRecognitionRouter(primary)
        self.assertIs(router.decoder_for('greedy_search'),primary)
        with self.assertRaises(ValueError):router.decoder_for('unknown')

    def test_unsupported_native_decoder_is_probed_outside_server_and_cached(self):
        primary=Mock(decoding_method='greedy_search',model_dir='/models',device='cpu',cpu_threads=4)
        router=SpeechRecognitionRouter(primary)
        with patch('subprocess.run',return_value=Mock(returncode=1)) as probe, patch('modules.stt_nemotron.NemotronSTT') as factory:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError,'installed Sherpa'):
                    router.decoder_for('modified_beam_search')
            probe.assert_called_once()
            factory.assert_not_called()

    def test_supported_decoder_is_cached_and_closed_with_router(self):
        primary=Mock(decoding_method='greedy_search',model_dir='/models',device='cpu',cpu_threads=4)
        router=SpeechRecognitionRouter(primary)
        with patch('subprocess.run',return_value=Mock(returncode=0)), patch('modules.stt_nemotron.NemotronSTT') as factory:
            decoder=router.decoder_for('modified_beam_search')
            self.assertIs(router.decoder_for('modified_beam_search'),decoder)
            factory.assert_called_once()
            router.close()
            decoder.close.assert_called_once()

    def test_auto_uses_cpu_whisper_when_torch_is_unavailable(self):
        whisper=Mock(runtime_info=lambda:{'device':'cpu','model':'medium'})
        factory=Mock(return_value=whisper)
        with patch.dict('sys.modules',{'torch':None}):
            router=create_stt(engine='auto',device='auto',whisper_factory=factory)
        self.assertIsNone(router.primary)
        self.assertEqual(router.fallback_reason,'No compatible NVIDIA CUDA GPU')
        factory.assert_called_once()

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

    def test_explicit_nemotron_startup_error_never_loads_whisper(self):
        factory=Mock()
        with self.assertRaisesRegex(RuntimeError, 'broken model'):
            create_stt(engine='nemotron',device='cpu',cuda_available=False,
                       nemotron_factory=Mock(side_effect=RuntimeError('broken model')),
                       whisper_factory=factory)
        factory.assert_not_called()

    def test_explicit_nemotron_decode_error_never_loads_whisper(self):
        primary=Mock(runtime_info=lambda:{"engine":"nemotron"})
        primary.transcribe_detailed.side_effect=RuntimeError('decode failed')
        factory=Mock()
        router=create_stt(engine='nemotron',device='cpu',cuda_available=False,
                          nemotron_factory=lambda:primary,whisper_factory=factory)
        with self.assertRaisesRegex(RuntimeError, 'Whisper fallback disabled'):
            router.transcribe_detailed(b'audio','English')
        factory.assert_not_called()
        self.assertIsNone(router.runtime_info()['fallback'])

    def test_explicit_nemotron_rejects_other_languages_without_whisper(self):
        factory=Mock()
        router=create_stt(engine='nemotron',device='cpu',cuda_available=False,
                          nemotron_factory=Mock(),whisper_factory=factory)
        with self.assertRaisesRegex(RuntimeError, 'English only'):
            router.transcribe_detailed(b'audio','ur')
        factory.assert_not_called()
