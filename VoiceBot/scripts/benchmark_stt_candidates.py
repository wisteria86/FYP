"""Compare installed recognizers on identical referenced audio, without LLMs."""
import argparse
import gc
import io
import json
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config
from scripts.compare_final_recognition import errors


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--engines',default='turbo,nemotron')
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text())
    rows=[]
    for engine in args.engines.split(','):
        began=time.perf_counter()
        if engine=='nemotron':
            from modules.stt_nemotron import NemotronSTT
            model=NemotronSTT(Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR,'cuda',4)
            beams=[None]
        else:
            from modules.stt_whisper import WhisperSTT
            path=next((ROOT/'models/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots').iterdir())
            model=WhisperSTT(str(path) if engine=='turbo' else 'medium',4,1,'cuda',local_files_only=True)
            beams=[1,3,5] if engine=='turbo' else [5]
        print(json.dumps({'engine':engine,'loaded_seconds':round(time.perf_counter()-began,2)}),flush=True)
        for beam in beams:
            for item in manifest:
                data=Path(item['path']).read_bytes();started=time.perf_counter();final_ms=None
                if engine=='nemotron':
                    from faster_whisper.audio import decode_audio
                    audio=decode_audio(io.BytesIO(data),sampling_rate=16000)
                    stream=model.create_stream()
                    for offset in range(0,len(audio),4096):model.accept_audio(stream,audio[offset:offset+4096],16000)
                    ended=time.perf_counter();result=model.finish_stream(stream);final_ms=(time.perf_counter()-ended)*1000
                    text=result['text']
                else:
                    segments,_=model.model.transcribe(io.BytesIO(data),language='en',beam_size=beam,temperature=0,
                        condition_on_previous_text=False,vad_filter=True,word_timestamps=False)
                    text=''.join(s.text for s in segments if s.no_speech_prob<.75).strip()
                latency=(time.perf_counter()-started)*1000
                mistakes,words=errors(item['reference'],text)
                rows.append({'engine':engine,'beam':beam,'row':item.get('row'), 'reference':item['reference'],
                    'text':text,'errors':mistakes,'words':words,'decode_ms':round(latency,1),'stream_final_ms':round(final_ms,1) if final_ms is not None else None})
                args.output.write_text(json.dumps({'rows':rows},indent=2))
            group=[r for r in rows if r['engine']==engine and r['beam']==beam]
            print(json.dumps({'engine':engine,'beam':beam,'clips':len(group),
                'wer':sum(r['errors'] for r in group)/sum(r['words'] for r in group),
                'median_ms':float(np.median([r['decode_ms'] for r in group])),
                'p95_ms':float(np.percentile([r['decode_ms'] for r in group],95))}),flush=True)
        if hasattr(model,'close'):model.close()
        del model;gc.collect()


if __name__=='__main__':main()
