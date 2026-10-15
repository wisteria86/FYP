"""Measure local reference-audio speed; not a learner-accent accuracy benchmark."""
import argparse
import gc
import json
import statistics
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',choices=['nemotron','whisper_small_onnx','whisper_medium_onnx'],required=True)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--runs',type=int,default=3)
    args=parser.parse_args()
    reference=ROOT/Config.NEMOTRON_MODEL_DIR/'test_wavs'/'0.wav'
    audio,rate=sf.read(reference,dtype='float32');duration=len(audio)/rate
    began=time.perf_counter()
    if args.engine=='nemotron':
        from modules.stt_nemotron import NemotronSTT
        model=NemotronSTT(ROOT/Config.NEMOTRON_MODEL_DIR,args.device,args.threads)
    else:
        from modules.stt_whisper_onnx import WhisperOnnxSTT
        model=WhisperOnnxSTT(args.engine.split('_')[1],ROOT/Config.WHISPER_ONNX_CACHE_DIR,args.device,args.threads)
    load_seconds=time.perf_counter()-began
    times=[];tails=[];texts=[]
    for _ in range(args.runs+1):
        began=time.perf_counter()
        if args.engine=='nemotron':
            stream=model.create_stream()
            for offset in range(0,len(audio),4096):
                model.accept_audio(stream,audio[offset:offset+4096],rate)
            ended=time.perf_counter();result=model.finish_stream(stream)
            tails.append(time.perf_counter()-ended)
        else:
            result=model.transcribe_detailed(reference.read_bytes(),'en')
        times.append(time.perf_counter()-began);texts.append(result['text'])
    print(json.dumps({'engine':args.engine,'device':args.device,'threads':args.threads,
                      'audio_seconds':round(duration,3),'load_seconds':round(load_seconds,3),
                      'warm_median_seconds':round(statistics.median(times[1:]),3),
                      'realtime_factor':round(statistics.median(times[1:])/duration,3),
                      'final_flush_median_ms':round(statistics.median(tails[1:])*1000,1) if tails else None,
                      'transcript':texts[-1],'consistent_transcripts':len(set(texts))==1},indent=2),flush=True)
    model.close();del model;gc.collect()

if __name__=='__main__':main()
