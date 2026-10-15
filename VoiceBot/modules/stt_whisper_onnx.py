"""Actual multilingual Whisper INT8 ONNX inference, not CTranslate2."""
import io
import threading
from pathlib import Path
import numpy as np
from core.interfaces import ISTTModel


class WhisperOnnxSTT(ISTTModel):
    streaming=False

    def __init__(self,model_size,cache_dir,device='cpu',cpu_threads=4):
        if model_size not in {'small','medium'}:raise ValueError('Unsupported Whisper ONNX size')
        from modules.onnx_runtime import prepare_sherpa
        sherpa_onnx,self._dll_handles=prepare_sherpa(device)
        directory=Path(cache_dir)/model_size
        paths={key:str(directory/f'{model_size}-{suffix}') for key,suffix in {
            'encoder':'encoder.int8.onnx','decoder':'decoder.int8.onnx','tokens':'tokens.txt',
        }.items()}
        for path in paths.values():
            if not Path(path).is_file():raise FileNotFoundError(f'Missing ONNX model: {path}. Run scripts/setup_whisper_onnx.py.')
        self.recognizer=sherpa_onnx.OfflineRecognizer.from_whisper(
            **paths,language='',task='transcribe',provider=device,
            num_threads=max(1,min(6,cpu_threads)),decoding_method='greedy_search',
        )
        self._lock=threading.Lock()
        self.model_size=model_size;self.device=device;self.engine=f'whisper_{model_size}_onnx'

    def transcribe_detailed(self,audio_data,language=None,initial_prompt=None):
        from faster_whisper.audio import decode_audio
        audio=decode_audio(io.BytesIO(audio_data),sampling_rate=16000)
        if not len(audio) or np.max(np.abs(audio))<.0005:
            return {'text':'','confidence':None,'detected_language':language}
        texts=[];detected=language
        with self._lock:
            # Update decoder language per capture under the same lock, without
            # allocating a separate model for every lesson language.
            self.recognizer.config.model_config.whisper.language=language or ''
            self.recognizer.recognizer.set_config(self.recognizer.config)
            for start in range(0,len(audio),16000*28):
                stream=self.recognizer.create_stream()
                stream.accept_waveform(16000,audio[start:start+16000*28])
                self.recognizer.decode_stream(stream)
                texts.append(stream.result.text.strip())
                detected=getattr(stream.result,'lang',None) or detected
        return {'text':' '.join(text for text in texts if text),'confidence':None,
                'detected_language':detected,'language_probability':None,'engine':self.engine}

    def transcribe(self,audio_data):return self.transcribe_detailed(audio_data)['text']

    def runtime_info(self):
        return {'engine':self.engine,'model':f'Whisper {self.model_size} ONNX',
                'device':self.device,'compute_type':'int8 ONNX','streaming':False,'task':'transcribe'}

    def close(self):self.recognizer=None
