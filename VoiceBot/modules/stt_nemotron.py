"""NVIDIA English Nemotron, cache-aware streaming via Sherpa-ONNX CUDA."""
import io
import os
import time
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
    input_samples: int = 0
    input_sum_squares: float = 0.0
    input_peak: float = 0.0


class NemotronSTT(ISTTModel):
    engine='nemotron'
    streaming=True

    def __init__(self, model_dir, device='cuda', cpu_threads=4, decoding_method='greedy_search', max_active_paths=4):
        if decoding_method not in {'greedy_search','modified_beam_search'}:
            raise ValueError('Unsupported Nemotron decoding method')
        self.decoding_method=decoding_method
        self.model_dir=Path(model_dir).resolve()
        if device not in {'cuda','cpu'}:raise ValueError('Unsupported recognition device')
        self.cpu_threads=max(1,min(6,int(cpu_threads)))
        self.final_padding_seconds=float(os.getenv('NEMOTRON_FINAL_PADDING_SECONDS','1.0'))
        if not 0.1 <= self.final_padding_seconds <= 2.0:
            raise ValueError('NEMOTRON_FINAL_PADDING_SECONDS must be between 0.1 and 2.0')
        self.empty_padding_seconds=float(os.getenv('NEMOTRON_EMPTY_PADDING_SECONDS','3.0'))
        if not self.final_padding_seconds <= self.empty_padding_seconds <= 5.0:
            raise ValueError('NEMOTRON_EMPTY_PADDING_SECONDS must be between final padding and 5.0')
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
            **paths,provider=device,num_threads=self.cpu_threads,sample_rate=16000,
            feature_dim=128,model_type='nemotron',decoding_method=decoding_method,max_active_paths=max_active_paths,enable_endpoint_detection=False,
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
            samples=np.asarray(samples,dtype=np.float32).reshape(-1)
            if not np.isfinite(samples).all():
                raise ValueError('Capture contains non-finite audio samples')
            stream.sample_rate=sample_rate
            stream.input_samples+=samples.size
            stream.input_sum_squares+=float(np.dot(samples.astype(np.float64),samples.astype(np.float64)))
            if samples.size:
                stream.input_peak=max(stream.input_peak,float(np.max(np.abs(samples))))
            stream.native.accept_waveform(sample_rate,samples)
            while self.recognizer.is_ready(stream.native):
                self.recognizer.decode_stream(stream.native)
            return self.recognizer.get_result(stream.native).strip()

    def finish_stream(self,stream):
        started=time.perf_counter()
        with self._lock:
            acquired=time.perf_counter()
            if stream.finished:raise ValueError('Recognition stream is already finalized')
            rate=stream.sample_rate or 16000
            # Keep the capture rate unchanged while flushing the model's caches.
            padding_seconds=getattr(self,'final_padding_seconds',1.0)
            padding_ms=0.0
            decode_ms=0.0
            decode_steps=0
            def pad(seconds):
                nonlocal padding_ms
                before=time.perf_counter()
                stream.native.accept_waveform(rate,np.zeros(round(rate*seconds),dtype=np.float32))
                padding_ms+=(time.perf_counter()-before)*1000
            def decode_ready():
                nonlocal decode_ms,decode_steps
                before=time.perf_counter()
                while self.recognizer.is_ready(stream.native):
                    self.recognizer.decode_stream(stream.native)
                    decode_steps+=1
                decode_ms+=(time.perf_counter()-before)*1000
            pad(padding_seconds)
            decode_ready()
            # Short utterances may still be in the encoder's lookahead cache.
            # Flush further only for non-silent input with no recognized text,
            # and do so BEFORE marking the native stream input as finished.
            maximum=getattr(self,'empty_padding_seconds',3.0)
            while (stream.input_peak>0 and padding_seconds<maximum
                   and not self.recognizer.get_result(stream.native).strip()):
                extra=min(0.56,maximum-padding_seconds)
                pad(extra)
                padding_seconds+=extra
                decode_ready()
            before=time.perf_counter()
            stream.native.input_finished()
            stream.finished=True
            padding_ms+=(time.perf_counter()-before)*1000
            decode_ready()
            decoded=time.perf_counter()
            result=self.result(self.recognizer.get_result(stream.native).strip())
            result['input_audio']={
                'duration_ms':round(stream.input_samples/rate*1000,1),
                'rms':round(float(np.sqrt(stream.input_sum_squares/max(1,stream.input_samples))),6),
                'peak':round(stream.input_peak,6),
            }
            result['finalize_timing']={
                'lock_wait_ms':round((acquired-started)*1000,2),
                'padding_and_finish_ms':round(padding_ms,2),
                'decode_ms':round(decode_ms,2),
                'result_ms':round((time.perf_counter()-decoded)*1000,2),
                'decode_steps':decode_steps,
                'padding_seconds':round(padding_seconds,3),
                'sample_rate':rate,
            }
            return result

    @staticmethod
    def result(text):
        return {'text':text,'confidence':None,'detected_language':'en',
                'language_probability':None,'engine':'nemotron','final':True}

    def transcribe_detailed(self,audio_data,language=None,initial_prompt=None):
        from faster_whisper.audio import decode_audio
        samples=decode_audio(io.BytesIO(audio_data),sampling_rate=16000)
        stream=self.create_stream()
        # Match the known-file check and live transport's bounded submissions.
        for offset in range(0,len(samples),4096):
            self.accept_audio(stream,samples[offset:offset+4096],16000)
        return self.finish_stream(stream)

    def transcribe(self,audio_data):
        return self.transcribe_detailed(audio_data)['text']

    def runtime_info(self):
        return {'engine':self.engine,'model':self.model_size,'device':self.device,
                'compute_type':'int8 ONNX','task':'transcribe','streaming':True,
                'languages':['en'],'chunk_ms':560,'cpu_threads':self.cpu_threads,
                'final_padding_seconds':self.final_padding_seconds,
                'empty_padding_seconds':self.empty_padding_seconds,
                'decoding_method':self.decoding_method}

    def close(self):
        self.recognizer=None
