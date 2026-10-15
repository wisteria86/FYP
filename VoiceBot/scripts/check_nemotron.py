"""Exercise actual CUDA recognition using the model package's reference audio."""
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config
from modules.stt_nemotron import NemotronSTT


def main():
    directory=ROOT/Config.NEMOTRON_MODEL_DIR
    started=time.perf_counter()
    model=NemotronSTT(directory)
    loaded=time.perf_counter()
    samples=list((directory/'test_wavs').glob('*.wav'))
    if not samples:raise RuntimeError('Reference audio missing')
    result=model.transcribe_detailed(samples[0].read_bytes(),'en')
    print(json.dumps({'runtime':model.runtime_info(),'reference':samples[0].name,
                      'load_seconds':round(loaded-started,2),
                      'decode_seconds':round(time.perf_counter()-loaded,2),
                      'result':result},indent=2),flush=True)
    if not result['text']:raise RuntimeError('Reference speech was not recognized')

if __name__=='__main__':main()
