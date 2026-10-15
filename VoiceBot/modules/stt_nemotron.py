"""NVIDIA English Nemotron, cache-aware streaming via Sherpa-ONNX CUDA."""
import io
import threading
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from core.interfaces import ISTTModel


@dataclass
class NemotronCapture:
    native: object
    sample_rate: int | None = None
    finished: bool = False


class NemotronSTT(ISTTModel):
    engine='nemotron'
    streaming=True

    def __init__(self, model_dir, device='cuda', cpu_threads=4):
        if device not in {'cuda','cpu'}:raise ValueError('Unsupported recognition device')
        from modules.onnx_runtime import prepare_sherpa
        sherpa_onnx,self._dll_handles=prepare_sherpa(device)
        directory=Path(model_dir)
        paths={key:str(directory/name) for key,name in {
            'encoder':'encoder.int8.onnx','decoder':'decoder.int8.onnx',
            'joiner':'joiner.int8.onnx','tokens':'tokens.txt',
        }.items()}
        for path in paths.values():
            if not Path(path).is_file():
                raise FileNotFoundError(f'Nemotron model missing: {path}. Run scripts/setup_nemotron.py.')
        if device=='cuda' and 'cuda' not in sherpa_onnx.__version__:
            raise RuntimeError('Sherpa-ONNX CUDA runtime is not installed')
        self.recognizer=sherpa_onnx.OnlineRecognizer.from_transducer(
            **paths,provider=device,num_threads=max(1,min(6,cpu_threads)),sample_rate=16000,
            feature_dim=80,decoding_method='greedy_search',enable_endpoint_detection=False,
        )
        self._lock=threading.Lock()
        self.device=device
        self.model_size='nvidia/nemotron-speech-streaming-en-0.6b'
        # Actual decoding at startup detects runtime/DLL failures before a call.
        stream=self.create_stream()
        self.accept_audio(stream,np.zeros(16000,dtype=np.float32),16000)
        self.finish_stream(stream)

    def create_stream(self):
        with self._lock:
            return NemotronCapture(self.recognizer.create_stream())

    def accept_audio(self,stream,samples,sample_rate):
        with self._lock:
            if stream.finished:raise ValueError('Recognition stream is already finalized')
            if sample_rate<=0 or sample_rate>96000:raise ValueError('Invalid capture sample rate')
            if stream.sample_rate is not None and stream.sample_rate!=sample_rate:
                # Reject in Python before the native runtime's fatal rate check.
                raise ValueError('Capture sample rate cannot change within a stream')
            stream.sample_rate=sample_rate
            stream.native.accept_waveform(sample_rate,np.asarray(samples,dtype=np.float32))
            while self.recognizer.is_ready(stream.native):
                self.recognizer.decode_stream(stream.native)
            return self.recognizer.get_result(stream.native).strip()

    def finish_stream(self,stream):
        with self._lock:
            if stream.finished:raise ValueError('Recognition stream is already finalized')
            rate=stream.sample_rate or 16000
            # The recognizer resamples internally. Its input rate must remain
            # unchanged, including the one-second padding used to flush caches.
            stream.native.accept_waveform(rate,np.zeros(rate,dtype=np.float32))
            stream.native.input_finished()
            stream.finished=True
            while self.recognizer.is_ready(stream.native):
                self.recognizer.decode_stream(stream.native)
            return self.result(self.recognizer.get_result(stream.native).strip())

    @staticmethod
    def result(text):
        return {'text':text,'confidence':None,'detected_language':'en',
                'language_probability':None,'engine':'nemotron','final':True}

    def transcribe_detailed(self,audio_data,language=None,initial_prompt=None):
        from faster_whisper.audio import decode_audio
        samples=decode_audio(io.BytesIO(audio_data),sampling_rate=16000)
        stream=self.create_stream()
        self.accept_audio(stream,samples,16000)
        return self.finish_stream(stream)

    def transcribe(self,audio_data):
        return self.transcribe_detailed(audio_data)['text']

    def runtime_info(self):
        return {'engine':self.engine,'model':self.model_size,'device':self.device,
                'compute_type':'int8 ONNX','task':'transcribe','streaming':True,
                'languages':['en'],'chunk_ms':560}

    def close(self):
        self.recognizer=None
