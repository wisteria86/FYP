"""Exercise deployed settings with QA credentials, restoring original selection."""
import json
import os
import sys
import time
import subprocess
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config


def main():
    with httpx.Client(base_url='http://localhost:8000',timeout=120) as client:
        login=client.post('/api/auth/login',json={'email':os.environ['HIKARI_QA_EMAIL'],'password':os.environ['HIKARI_QA_PASSWORD']})
        login.raise_for_status()
        state=client.get('/api/stt/engines').json()
        if len(state['engines'])!=3 or not all(item['installed'] for item in state['engines']):
            raise RuntimeError('The three requested recognizers are not installed')
        original={'engine':state['selected'],'device':state['device']}
        voice=client.get('/api/tts/engines').json()
        audio=(ROOT/Config.NEMOTRON_MODEL_DIR/'test_wavs'/'0.wav').read_bytes()
        results=[]
        try:
            for engine in ('whisper_small_onnx','whisper_medium_onnx','nemotron'):
                switched=client.post('/api/stt/engine',json={'engine':engine,'device':'cpu'})
                switched.raise_for_status()
                runtime=switched.json()['runtime']
                if runtime['device']!='cpu':raise RuntimeError('CPU selection was not honored')
                began=time.perf_counter()
                transcript=client.post('/api/transcribe',files={'file':('reference.wav',audio,'audio/wav')},data={'language':'English','duration_ms':6625})
                transcript.raise_for_status()
                if not transcript.json()['text']:raise RuntimeError('Recognition returned no text')
                results.append({'selected':engine,'runtime':runtime,'decode_seconds':round(time.perf_counter()-began,3),'text':transcript.json()['text']})
            subprocess.run([sys.executable,str(ROOT/'scripts'/'check_live_speech.py'),'--device','cpu'],check=True)
            html=client.get('/').text
            import re
            bundle=re.search(r'src="([^"]+\.js)"',html).group(1)
            compiled=client.get(bundle).text
            if 'Apply recognition mode' not in compiled:raise RuntimeError('Settings frontend was not deployed')
            current_voice=client.get('/api/tts/engines').json()
            if (current_voice['active'],current_voice['current_voice'])!=(voice['active'],voice['current_voice']):
                raise RuntimeError('Recognition switching changed the TTS selection')
            print(json.dumps({'results':results,'frontend':bundle,'tts_preserved':True},indent=2),flush=True)
        finally:
            restored=client.post('/api/stt/engine',json=original);restored.raise_for_status()
            client.post('/api/auth/logout')

if __name__=='__main__':main()
