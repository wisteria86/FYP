"""Hardware-aware recognition selection with lazy multilingual Whisper fallback."""
import logging
import threading
from config import Config
from core.interfaces import ISTTModel

logger=logging.getLogger(__name__)


class SpeechRecognitionRouter(ISTTModel):
    def __init__(self,primary=None,fallback_factory=None,reason=None):
        self.primary=primary
        self._fallback=None
        self._fallback_factory=fallback_factory
        self._lock=threading.Lock()
        self.fallback_reason=reason

    @property
    def fallback(self):
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
                logger.warning('Nemotron recognition failed; retrying with Whisper: %s',exc)
        return self.fallback.transcribe_detailed(audio_data,language,initial_prompt)

    def transcribe(self,audio_data):
        return self.transcribe_detailed(audio_data,'en')['text']

    def runtime_info(self):
        if self.primary:
            return {**self.primary.runtime_info(),'fallback':'whisper',
                    'fallback_model':Config.WHISPER_MODEL_SIZE,'fallback_loaded':self._fallback is not None}
        return {**self.fallback.runtime_info(),'engine':'whisper','streaming':False,
                'fallback_reason':self.fallback_reason}

    def close(self):
        for model in (self.primary,self._fallback):
            if model and hasattr(model,'close'):model.close()
        self.primary=None;self._fallback=None


def create_stt(*,cuda_available=None,nemotron_factory=None,whisper_factory=None,engine=None,device=None,strict=False):
    engine=engine or Config.STT_ENGINE
    device=device or Config.STT_DEVICE
    if cuda_available is None:
        import torch
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
    if (cuda_available or device=='cpu') and engine in {'auto','nemotron'}:
        try:
            if nemotron_factory is None:
                from modules.stt_nemotron import NemotronSTT
                nemotron_factory=lambda:NemotronSTT(Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR,resolved,Config.STT_CPU_THREADS)
            primary=nemotron_factory()
        except Exception as exc:
            if strict:raise
            reason=f'Nemotron unavailable: {exc}'
            logger.warning('%s; using Whisper',reason)
    router=SpeechRecognitionRouter(primary,whisper_factory,reason)
    if primary is None:
        _=router.fallback  # Fail early if both providers are unavailable.
    return router
