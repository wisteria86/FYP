"""One isolated decoder benchmark. Invoked by the Settings comparison service."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--audio',required=True)
    parser.add_argument('--model-dir',required=True)
    parser.add_argument('--method',choices=['greedy_search','modified_beam_search'],required=True)
    parser.add_argument('--device',choices=['cpu','cuda'],required=True)
    parser.add_argument('--threads',type=int,required=True)
    parser.add_argument('--beam',type=int,default=4)
    args=parser.parse_args()
    try:
        import resource
    except ImportError:
        pass
    else:
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    from faster_whisper.audio import decode_audio
    import sherpa_onnx
    from modules.stt_nemotron import NemotronSTT
    started=time.perf_counter()
    samples=decode_audio(args.audio,sampling_rate=16000)
    decode_ms=(time.perf_counter()-started)*1000
    if not len(samples) or len(samples)>16000*15:
        raise ValueError('Comparison requires between 0 and 15 seconds of audio')
    started=time.perf_counter()
    model=NemotronSTT(args.model_dir,args.device,args.threads,
                     decoding_method=args.method,max_active_paths=args.beam)
    load_ms=(time.perf_counter()-started)*1000
    try:
        # Constructor warms the model. Keep loading out of recognition timings.
        started=time.perf_counter()
        stream=model.create_stream()
        for offset in range(0,len(samples),4096):
            model.accept_audio(stream,samples[offset:offset+4096],16000)
        result=model.finish_stream(stream)
        inference_ms=(time.perf_counter()-started)*1000
        print(json.dumps({'status':'ok','method':args.method,'runtime_version':sherpa_onnx.__version__,
                         'load_ms':round(load_ms,1),'audio_decode_ms':round(decode_ms,1),
                         'recognition_ms':round(inference_ms,1),'audio_seconds':round(len(samples)/16000,3),
                         'realtime_factor':round(inference_ms/(len(samples)/16),3),
                         'beam_width':args.beam if args.method=='modified_beam_search' else None,**result}),flush=True)
    finally:model.close()


if __name__=='__main__':
    main()
