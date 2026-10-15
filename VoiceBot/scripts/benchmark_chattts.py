"""Local CUDA benchmark and speaker pitch screening; no application data writes."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from scipy.signal import correlate
from config import Config
from modules.tts_chattts import ChatTTSModel

model = ChatTTSModel(device=Config.CHAT_TTS_DEVICE, model_source=Config.CHAT_TTS_MODEL_SOURCE,
                     cache_dir=Config.CHAT_TTS_CACHE_DIR, max_new_tokens=256)
phrase = 'Hello, it is lovely to meet you. How are you today?'
for dtype in (torch.float32, torch.bfloat16):
    model.chat.gpt.gpt.to(dtype=dtype)
    started = time.perf_counter()
    audio = np.concatenate([np.frombuffer(chunk, np.float32) for chunk in model.synthesize(phrase)])
    print('BENCH', str(dtype), round(time.perf_counter()-started, 2), 'seconds', round(len(audio)/24000, 2), 'audio seconds', flush=True)
for seed in (7, 11, 100, 9001):
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        model.speaker = model.chat.sample_random_speaker()
    audio = np.concatenate([np.frombuffer(chunk, np.float32) for chunk in model.synthesize(phrase)])
    pitches = []
    for start in range(0, len(audio)-1200, 600):
        frame = audio[start:start+1200].astype(float)
        frame -= frame.mean()
        if np.sqrt(np.mean(frame**2)) < .02:
            continue
        c = correlate(frame, frame, mode='full')[1199:]
        lag = 60 + np.argmax(c[60:300])
        if c[lag] > c[0]*.35:
            pitches.append(24000/lag)
    print('VOICE', seed, 'median_hz', round(float(np.median(pitches)),1) if pitches else None, flush=True)
model.close()
