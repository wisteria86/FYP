"""Verify deployed speech transport with an isolated QA account and reference WAV.

Set HIKARI_QA_EMAIL and HIKARI_QA_PASSWORD in the invoking process. This script
never prints cookies/credentials and cancels its test session when finished.
"""
import json
import argparse
import os
import sys
import time
from pathlib import Path
import httpx
import numpy as np
import soundfile as sf
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    parser.add_argument('--sample-rate',type=int,choices=[16000,44100,48000],default=16000)
    options=parser.parse_args()
    with httpx.Client(base_url='http://localhost:8000',timeout=30) as client:
        health=client.get('/api/health').json()
        runtime=health.get('stt_runtime') or {}
        if runtime.get('engine')!='nemotron' or runtime.get('device')!=options.device:
            raise RuntimeError('The deployed server is not using the requested NVIDIA recognition device')
        login=client.post('/api/auth/login',json={'email':os.environ['HIKARI_QA_EMAIL'],'password':os.environ['HIKARI_QA_PASSWORD']})
        login.raise_for_status()
        created=client.post('/api/sessions',json={'skill_id':'english-speaking','difficulty':'beginner','activity_id':'english-01'})
        created.raise_for_status();session=created.json()
        try:
            directory=ROOT/Config.NEMOTRON_MODEL_DIR
            audio,rate=sf.read(directory/'test_wavs'/'0.wav',dtype='float32')
            if rate!=options.sample_rate:
                # Upsample the reference clip to reproduce browser capture rates.
                from scipy.signal import resample_poly
                from math import gcd
                divisor=gcd(rate,options.sample_rate)
                audio=resample_poly(audio,options.sample_rate//divisor,rate//divisor).astype(np.float32)
                rate=options.sample_rate
            cookie='; '.join(f'{key}={value}' for key,value in client.cookies.items())
            began=time.perf_counter();partials=0
            with connect(f"ws://localhost:8000/api/sessions/{session['id']}/speech-stream",origin='http://localhost:8000',additional_headers={'Cookie':cookie},open_timeout=10) as socket:
                socket.send(json.dumps({'sample_rate':rate}))
                if json.loads(socket.recv(timeout=10))['type']!='ready':raise RuntimeError('Stream did not become ready')
                for start in range(0,len(audio),4096):
                    socket.send(np.asarray(audio[start:start+4096],dtype='<f4').tobytes())
                socket.send(json.dumps({'type':'finish'}))
                while True:
                    event=json.loads(socket.recv(timeout=30))
                    if event['type']=='partial':partials+=1
                    if event['type']=='error':raise RuntimeError(event['message'])
                    if event['type']=='final':break
            if not event.get('text') or not event.get('final'):raise RuntimeError('Missing finalized transcript')
            html=client.get('/').text
            import re
            bundle=re.search(r'src="([^"]+\.js)"',html).group(1)
            deployed=client.get(bundle).text
            if 'speech-stream' not in deployed or 'hikari-pcm-capture' not in deployed:
                raise RuntimeError('Deployed frontend is not the streaming build')
            print(json.dumps({'runtime':runtime,'input_sample_rate':rate,'partial_events':partials,'final_text':event['text'],
                              'final_decode_ms':event['latency_ms'],'reference_transport_seconds':round(time.perf_counter()-began,2),
                              'deployed_frontend':bundle},indent=2),flush=True)
        finally:
            client.post(f"/api/sessions/{session['id']}/cancel")
            client.post('/api/auth/logout')

if __name__=='__main__':main()
