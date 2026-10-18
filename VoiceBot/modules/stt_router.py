"""Hardware-aware recognition selection with lazy multilingual Whisper fallback."""
import logging
import threading
from config import Config
from core.interfaces import ISTTModel

logger=logging.getLogger(__name__)


class SpeechRecognitionRouter(ISTTModel):
    def __init__(self,primary=None,fallback_factory=None,reason=None,allow_fallback=True):
        self.allow_fallback=allow_fallback
        self.primary=primary
        self._fallback=None
        self._fallback_factory=fallback_factory
        self._lock=threading.Lock()
        self.fallback_reason=reason
        self._decoders={}
        self._decoder_errors={}
        self._decoder_lock=threading.Lock()

    def decoder_for(self,method):
        if method not in {'greedy_search','modified_beam_search'}:
            raise ValueError('Invalid decoding technique')
        if self.primary is None:
            raise RuntimeError('Select Nemotron to choose a decoding technique')
        if getattr(self.primary,'decoding_method','greedy_search')==method:
            return self.primary
        with self._decoder_lock:
            if method in self._decoder_errors:raise RuntimeError(self._decoder_errors[method])
            if method not in self._decoders:
                import subprocess
                import sys
                from pathlib import Path
                # Unsupported native decoders may exit rather than raise.
                try:
                    probe=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/probe_nemotron_decoder.py'),
                        str(self.primary.model_dir),self.primary.device,str(self.primary.cpu_threads),method],
                        capture_output=True,timeout=120)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError('Decoder validation timed out; settings were not applied') from exc
                if probe.returncode:
                    message='This installed Sherpa runtime could not initialize the selected Nemotron decoder. Keep greedy search or install a compatible runtime.'
                    self._decoder_errors[method]=message
                    raise RuntimeError(message)
                from modules.stt_nemotron import NemotronSTT
                self._decoders[method]=NemotronSTT(self.primary.model_dir,self.primary.device,self.primary.cpu_threads,decoding_method=method)
            return self._decoders[method]

    @property
    def fallback(self):
        if not self.allow_fallback:
            raise RuntimeError("Whisper fallback is disabled; Nemotron supports English only")
        with self._lock:
            if self._fallback is None:
                self._fallback=self._fallback_factory()
            return self._fallback

    def supports_streaming(self,language):
        return self.primary is not None and language in {'en','English'}

    def transcribe_detailed(self,audio_data,language=None,initial_prompt=None):
        if self.supports_streaming(language):
            try:
                return self.primary.transcribe_detailed(audio_data,language,initial_prompt)
            except Exception as exc:
                if not self.allow_fallback:
                    raise RuntimeError(f'Nemotron recognition failed (Whisper fallback disabled): {exc}') from exc
                logger.warning('Nemotron recognition failed; retrying with Whisper: %s',exc)
        return self.fallback.transcribe_detailed(audio_data,language,initial_prompt)

    def transcribe(self,audio_data):
        return self.transcribe_detailed(audio_data,'en')['text']

    def runtime_info(self):
        if self.primary:
            return {**self.primary.runtime_info(),'fallback':'whisper' if self.allow_fallback else None,
                    'fallback_model':Config.WHISPER_MODEL_SIZE,'fallback_loaded':self._fallback is not None}
        return {**self.fallback.runtime_info(),'engine':'whisper','streaming':False,
                'fallback_reason':self.fallback_reason}

    def close(self):
        for model in (self.primary,self._fallback,*self._decoders.values()):
            if model and hasattr(model,'close'):model.close()
        self.primary=None;self._fallback=None
        self._decoders.clear()


def create_stt(*,cuda_available=None,nemotron_factory=None,whisper_factory=None,engine=None,device=None,strict=False):
    engine=engine or Config.STT_ENGINE
    device=device or Config.STT_DEVICE
    if cuda_available is None:
        try:
            import torch
        except ImportError:
            cuda_available=False
        else:
            cuda_available=torch.cuda.is_available()
    resolved='cuda' if cuda_available and device!='cpu' else 'cpu'
    if engine in {'whisper_small_onnx','whisper_medium_onnx'}:
        from modules.stt_whisper_onnx import WhisperOnnxSTT
        return WhisperOnnxSTT(engine.split('_')[1],Config.BASE_DIR/Config.WHISPER_ONNX_CACHE_DIR,resolved,Config.STT_CPU_THREADS)
    if whisper_factory is None:
        def whisper_factory():
            from modules.stt_whisper import WhisperSTT
            return WhisperSTT(Config.WHISPER_MODEL_SIZE,Config.WHISPER_CPU_THREADS,
                              Config.WHISPER_WORKERS,'auto' if resolved=='cuda' else 'cpu')
    reason='No compatible NVIDIA CUDA GPU' if not cuda_available else 'Whisper explicitly selected'
    primary=None
    if (cuda_available or device=='cpu' or engine=='nemotron') and engine in {'auto','nemotron'}:
        try:
            if nemotron_factory is None:
                from modules.stt_nemotron import NemotronSTT
                nemotron_factory=lambda:NemotronSTT(Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR,resolved,Config.STT_CPU_THREADS)
            primary=nemotron_factory()
        except Exception as exc:
            if strict or engine=='nemotron':raise
            reason=f'Nemotron unavailable: {exc}'
            logger.warning('%s; using Whisper',reason)
    router=SpeechRecognitionRouter(primary,whisper_factory,reason,allow_fallback=engine!='nemotron')
    if primary is None:
        _=router.fallback  # Fail early if both providers are unavailable.
    return router
