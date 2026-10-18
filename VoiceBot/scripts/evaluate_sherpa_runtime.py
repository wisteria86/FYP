"""Compare Nemotron decoders and smoke-test installed Piper/Kitten in one runtime.

Run in an isolated environment; each invocation evaluates one decoder. JSON is
written to --output, with loading separated from recognition time.
"""
import argparse
import json
import re
from pathlib import Path
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def decode_audio(path):
    import av
    import numpy as np
    # PCM16 conversion matches the upload decoder's scaling/downmix behavior.
    resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
    parts=[]
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            parts.extend(item.to_ndarray().reshape(-1) for item in resampler.resample(frame))
    parts.extend(item.to_ndarray().reshape(-1) for item in resampler.resample(None))
    return np.concatenate(parts).astype(np.float32)/32768 if parts else np.zeros(0,dtype=np.float32)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--method',choices=['greedy_search','modified_beam_search'],required=True)
    parser.add_argument('--audio',type=Path,action='append',default=[])
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--beam',type=int,default=4)
    parser.add_argument('--tts',action='store_true')
    parser.add_argument('--source-commit',help='Actual checkout SHA for source builds; embedded runtime metadata can lag')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import sherpa_onnx
    from config import Config
    from modules.stt_nemotron import NemotronSTT
    directory=Config.BASE_DIR/Config.NEMOTRON_MODEL_DIR
    paths=[directory/'test_wavs'/name for name in ('0.wav','1.wav','8k.wav')]+args.audio
    references={}
    for line in (directory/'test_wavs'/'trans.txt').read_text().splitlines():
        name,text=line.split(' ',1);references[name]=text
    def word_error_rate(reference,text):
        first=re.findall(r"[a-z0-9]+(?:'[a-z]+)?",reference.lower())
        second=re.findall(r"[a-z0-9]+(?:'[a-z]+)?",text.lower())
        row=list(range(len(second)+1))
        for i,a in enumerate(first,1):
            next_row=[i]
            for j,b in enumerate(second,1):next_row.append(min(next_row[-1]+1,row[j]+1,row[j-1]+(a!=b)))
            row=next_row
        return round(row[-1]/max(1,len(first))*100,2)
    report={'runtime_version':getattr(sherpa_onnx,'__version__',sherpa_onnx.version),
            'runtime_git':getattr(sherpa_onnx,'git_sha1',None),'onnxruntime_version':getattr(sherpa_onnx,'onnxruntime_version',None),'method':args.method,'beam':args.beam,'threads':args.threads}
    if args.source_commit:report['source_commit']=args.source_commit
    started=time.perf_counter()
    model=NemotronSTT(directory,'cpu',args.threads,decoding_method=args.method,max_active_paths=args.beam)
    report['model_load_ms']=round((time.perf_counter()-started)*1000,1)
    rows=[]
    try:
        for path in paths:
            samples=decode_audio(path)
            started=time.perf_counter();stream=model.create_stream()
            for offset in range(0,len(samples),4096):model.accept_audio(stream,samples[offset:offset+4096],16000)
            result=model.finish_stream(stream)
            duration=(time.perf_counter()-started)*1000
            rows.append({'file':path.name,'recognition_ms':round(duration,1),
                         'rtf':round(duration/max(1,len(samples)/16),3),
                         'reference_wer_percent':word_error_rate(references[path.name],result['text']) if path.name in references else None,**result})
    finally:model.close()
    report['recognition']=rows
    if args.tts:
        from modules.tts_english import EnglishOnnxTTS
        report['tts']=[]
        for engine in ('piper','kitten'):
            started=time.perf_counter();voice=EnglishOnnxTTS(engine)
            loading=(time.perf_counter()-started)*1000
            list(voice.synthesize('Ready.'))
            started=time.perf_counter();audio=list(voice.synthesize('Hello. I would like to practice my English today.'))
            elapsed=(time.perf_counter()-started)*1000
            report['tts'].append({'engine':engine,'load_ms':round(loading,1),'synthesis_ms':round(elapsed,1),
                                  'audio_seconds':round(sum(len(part) for part in audio)/4/voice.output_sample_rate,3),
                                  'sample_rate':voice.output_sample_rate,'runtime':voice.runtime_info()})
            del voice
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
