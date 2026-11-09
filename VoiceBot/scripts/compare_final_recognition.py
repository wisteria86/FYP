"""Same-audio WER/latency comparison. Optional manifest: [{path, reference}]."""
import argparse
import io
import json
import re
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config
from modules.stt_nemotron import NemotronSTT
from modules.stt_whisper import WhisperSTT


def errors(reference,hypothesis):
    a=re.findall(r"[a-z0-9]+(?:'[a-z]+)?",reference.lower())
    b=re.findall(r"[a-z0-9]+(?:'[a-z]+)?",hypothesis.lower())
    row=list(range(len(b)+1))
    for i,word in enumerate(a,1):
        new=[i]
        for j,other in enumerate(b,1):new.append(min(new[-1]+1,row[j]+1,row[j-1]+(word!=other)))
        row=new
    return row[-1],len(a)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device',default='cuda',choices=['cpu','cuda'])
    parser.add_argument('--noise-snr',type=float,help='Also test deterministic synthetic noise; not learner accuracy evidence.')
    args=parser.parse_args()
    directory=Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR
    if args.manifest:
        samples=json.loads(args.manifest.read_text(encoding='utf-8'))
    else:
        samples=[]
        for line in (directory/'test_wavs/trans.txt').read_text().splitlines():
            name,reference=line.split(' ',1)
            samples.append({'path':str(directory/'test_wavs'/name),'reference':reference})
    models={'nemotron':NemotronSTT(directory,args.device,Config.STT_CPU_THREADS),
            'whisper':WhisperSTT(Config.WHISPER_MODEL_SIZE,4,1,args.device,local_files_only=True)}
    rows=[]
    for sample in samples:
        path=Path(sample['path'])
        audio,rate=sf.read(path,dtype='float32')
        variants=[('original',audio)]
        if args.noise_snr is not None:
            rng=np.random.default_rng(42)
            amplitude=np.sqrt(np.mean(audio**2))/10**(args.noise_snr/20)
            variants.append(('synthetic_noise',np.clip(audio+rng.normal(0,amplitude,audio.shape),-1,1)))
        for variant,wave in variants:
            buffer=io.BytesIO();sf.write(buffer,wave,rate,format='WAV')
            row={'file':path.name,'variant':variant,'audio_seconds':round(len(audio)/rate,2),'reference':sample['reference']}
            for name,model in models.items():
                began=time.perf_counter();result=model.transcribe_detailed(buffer.getvalue(),'en')
                mistakes,words=errors(sample['reference'],result['text'])
                row[name]={'text':result['text'],'errors':mistakes,'reference_words':words,
                           'wer':round(mistakes/max(1,words),4),'seconds':round(time.perf_counter()-began,3)}
            rows.append(row)
            print(json.dumps(row),flush=True)
    report={'device':args.device,'whisper_model':Config.WHISPER_MODEL_SIZE,'noise_snr':args.noise_snr,
            'learner_recordings':bool(args.manifest),'rows':rows}
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    for model in models.values():
        if hasattr(model,'close'):model.close()


if __name__=='__main__':main()
