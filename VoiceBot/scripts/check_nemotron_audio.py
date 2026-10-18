"""Check the installed recognizer with the model package's known speech WAV."""
import argparse
import json
from pathlib import Path
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from config import Config
from modules.stt_nemotron import NemotronSTT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wav',type=Path)
    parser.add_argument('--audio',type=Path,help='Test a saved browser recording using the upload decode path')
    parser.add_argument('--sample-rate',type=int,choices=[16000,44100,48000,96000],
                        help='Resample known speech to simulate browser capture')
    parser.add_argument('--chunk-size',type=int,default=4096)
    args=parser.parse_args()
    if args.chunk_size < 1:
        parser.error('--chunk-size must be positive')
    directory=Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR
    if args.audio:
        model=NemotronSTT(directory,device='cpu',cpu_threads=Config.STT_CPU_THREADS)
        try:
            result=model.transcribe_detailed(args.audio.read_bytes(),'en')
            print(json.dumps(result,indent=2))
            if not result['text']:
                raise RuntimeError('Saved microphone audio produced no transcript')
        finally:
            model.close()
        return
    path=args.wav or directory/'test_wavs'/'0.wav'
    with wave.open(str(path),'rb') as wav:
        if wav.getsampwidth()!=2 or wav.getnchannels()!=1:
            raise ValueError('Use a mono PCM16 WAV file')
        rate=wav.getframerate()
        samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    if args.sample_rate and args.sample_rate != rate:
        # Linear interpolation is sufficient for this upsampling diagnostic;
        # use the same speech and native call boundaries as the browser.
        output_count=round(len(samples)*args.sample_rate/rate)
        samples=np.interp(np.arange(output_count)*rate/args.sample_rate,
                          np.arange(len(samples)),samples).astype(np.float32)
        rate=args.sample_rate
    model=NemotronSTT(directory,device='cpu',cpu_threads=Config.STT_CPU_THREADS)
    try:
        stream=model.create_stream()
        for start in range(0,len(samples),args.chunk_size):
            model.accept_audio(stream,samples[start:start+args.chunk_size],rate)
        result=model.finish_stream(stream)
        print(json.dumps(result,indent=2))
        if not result['text']:
            raise RuntimeError('Known speech produced no transcript; recognizer/model issue independent of browser microphone')
    finally:
        model.close()


if __name__=='__main__':
    main()
