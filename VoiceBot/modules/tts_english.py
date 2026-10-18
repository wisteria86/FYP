"""English Piper and Kitten voices using Sherpa-ONNX's CPU TTS runtime."""
import logging
import os
from pathlib import Path
import re
import tarfile
import tempfile
import threading
import time
import urllib.request

import numpy as np
from core.interfaces import ITTSModel

logger = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent.parent
PACKAGES = {
    'piper': ('vits-piper-en_US-amy-low', 'en_US-amy-low.onnx'),
    'kitten': ('kitten-nano-en-v0_8-int8', 'model.int8.onnx'),
}
_download_lock = threading.Lock()


def model_directory(engine):
    default = BASE / 'models' / 'tts' / PACKAGES[engine][0]
    path = Path(os.getenv(f'{engine.upper()}_MODEL_DIR', str(default))).expanduser()
    return path if path.is_absolute() else BASE / path


def installed(engine, directory=None):
    directory = directory or model_directory(engine)
    required = [PACKAGES[engine][1], 'tokens.txt']
    if engine == 'kitten':
        required.append('voices.bin')
    return (all((directory / name).is_file() and (directory / name).stat().st_size > 0 for name in required)
            and (directory / 'espeak-ng-data').is_dir())


def ensure_model(engine):
    directory = model_directory(engine)
    with _download_lock:
        if installed(engine, directory):
            return directory
        if os.getenv(f'{engine.upper()}_MODEL_DIR'):
            raise FileNotFoundError(f'Incomplete {engine} model directory: {directory}')
        package = PACKAGES[engine][0]
        directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory.parent) as temporary:
            stage = Path(temporary)
            archive = stage / 'model.tar.bz2'
            url = f'https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/{package}.tar.bz2'
            logger.info('Downloading %s model: %s', engine, url)
            with urllib.request.urlopen(url, timeout=60) as source, archive.open('wb') as target:
                import shutil
                shutil.copyfileobj(source, target)
            with tarfile.open(archive, 'r:bz2') as bundle:
                # Only ordinary files/directories inside the expected package.
                for member in bundle.getmembers():
                    path = Path(member.name)
                    if (path.is_absolute() or '..' in path.parts or not path.parts
                            or path.parts[0] != package or not (member.isfile() or member.isdir())):
                        raise ValueError('Unsafe model archive entry')
                bundle.extractall(stage, filter='data')
            extracted = stage / package
            if not installed(engine, extracted):
                raise RuntimeError(f'{engine} archive is missing required model files')
            if directory.exists():
                raise RuntimeError(f'Incomplete model cache at {directory}; remove it and retry')
            extracted.rename(directory)
    return directory


class TimedAudio(bytes):
    def __new__(cls, data, timing):
        instance = super().__new__(cls, data)
        instance.tts_timing = timing
        return instance


class EnglishOnnxTTS(ITTSModel):
    def __init__(self, engine):
        if engine not in PACKAGES:
            raise ValueError('Unknown English TTS engine')
        import sherpa_onnx as sherpa
        self.engine = engine
        self.threads = int(os.getenv(f'{engine.upper()}_CPU_THREADS', '2'))
        self.speaker = int(os.getenv(f'{engine.upper()}_SPEAKER_ID', '0'))
        if self.threads < 1 or self.speaker < 0:
            raise ValueError('TTS threads must be positive and speaker ID nonnegative')
        directory = ensure_model(engine)
        common = dict(model=str(directory / PACKAGES[engine][1]),
                      tokens=str(directory / 'tokens.txt'), data_dir=str(directory / 'espeak-ng-data'))
        if engine == 'piper':
            model = dict(vits=sherpa.OfflineTtsVitsModelConfig(**common))
        else:
            model = dict(kitten=sherpa.OfflineTtsKittenModelConfig(
                **common, voices=str(directory / 'voices.bin')))
        config = sherpa.OfflineTtsConfig(model=sherpa.OfflineTtsModelConfig(
            **model, provider='cpu', num_threads=self.threads), max_num_sentences=1)
        if not config.validate():
            raise RuntimeError(f'Invalid {engine} TTS configuration: {directory}')
        self.tts = sherpa.OfflineTts(config)
        if self.speaker >= self.tts.num_speakers:
            raise ValueError(f'{engine} speaker ID must be below {self.tts.num_speakers}')
        self._lock = threading.Lock()

    @property
    def output_sample_rate(self):
        return self.tts.sample_rate

    def runtime_info(self):
        return dict(engine=self.engine, backend='sherpa-onnx', device='cpu',
                    model=PACKAGES[self.engine][0], cpu_threads=self.threads, speaker_id=self.speaker)

    def synthesize(self, text, speed=1.0):
        if speed <= 0:
            raise ValueError('Speech speed must be positive')
        # Keep inference units bounded while preserving complete short replies.
        remaining = text.strip()
        while remaining:
            split = len(remaining)
            if split > 180:
                boundaries = [m.start() for m in re.finditer(r'(?<=[.!?;])\s+', remaining[:181]) if m.start() >= 90]
                split = boundaries[-1] if boundaries else remaining.rfind(' ', 0, 181)
                if split <= 0:
                    split = 180
            chunk, remaining = remaining[:split], remaining[split:].lstrip()
            started = time.perf_counter()
            with self._lock:
                acquired = time.perf_counter()
                audio = self.tts.generate(chunk, sid=self.speaker, speed=speed)
                elapsed = (time.perf_counter() - acquired) * 1000
            samples = np.asarray(audio.samples, dtype=np.float32)
            if not samples.size:
                raise RuntimeError(f'{self.engine} returned no audio')
            timing = dict(engine=self.engine, synthesis_ms=round(elapsed, 2),
                          lock_wait_ms=round((acquired-started)*1000, 2), chars=len(chunk),
                          audio_seconds=round(len(samples)/audio.sample_rate, 3))
            logger.info('English TTS timing %s', timing)
            yield TimedAudio(samples.tobytes(), timing)
