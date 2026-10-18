"""Benchmark decoders serially against identical audio without changing live STT."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
METHODS={'greedy_search','modified_beam_search'}


def compare_decoders(data,methods,model_dir,device,threads,beam=4):
    if not methods or len(methods)>2 or len(set(methods))!=len(methods) or any(m not in METHODS for m in methods):
        raise ValueError('Select greedy_search and/or modified_beam_search once each')
    if not 1<=beam<=8:raise ValueError('Beam width must be between 1 and 8')
    results=[]
    with tempfile.TemporaryDirectory(prefix='hikari-decoder-') as temporary:
        audio=Path(temporary)/'capture.audio'
        audio.write_bytes(data)
        for method in methods:
            command=[sys.executable,str(ROOT/'scripts/compare_nemotron_decoder.py'),
                     '--audio',str(audio),'--model-dir',str(model_dir),'--method',method,
                     '--device',device,'--threads',str(threads),'--beam',str(beam)]
            try:
                process=subprocess.run(command,capture_output=True,text=True,timeout=90,cwd=ROOT)
            except subprocess.TimeoutExpired:
                results.append({'method':method,'status':'error','message':'Decoder test timed out after 90 seconds.'})
                continue
            if process.returncode:
                detail=(process.stderr+'\n'+process.stdout)
                unsupported='Unsupported decoding method' in detail
                results.append({'method':method,'status':'unsupported' if unsupported else 'error',
                                'message':('Installed Sherpa-ONNX does not support this decoder for Nemotron.'
                                           if unsupported else 'Decoder worker failed. '+detail[-1500:])})
                continue
            try:
                result=json.loads(process.stdout.strip().splitlines()[-1])
                if result.get('method')!=method or result.get('status')!='ok':raise ValueError('Invalid worker result')
                results.append(result)
            except (ValueError,IndexError):
                results.append({'method':method,'status':'error','message':'Decoder returned no valid benchmark result.'})
    return results
