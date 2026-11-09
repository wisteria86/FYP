"""Run the real speech pipeline with synthesized audio. No microphone is needed.

Start the full evaluation server first, which uses a copy of your data:
    python scripts/conversation_eval/serve.py --port 8000 --full
    python -m scripts.conversation_eval.check_voice_stack --register

--register creates a throwaway account, so use it only against the evaluation server. Otherwise
set HIKARI_QA_EMAIL and HIKARI_QA_PASSWORD. Timing here excludes the browser, the microphone and
the end-of-speech wait, so it is not the full delay a learner hears.
"""
import argparse
import base64
import io
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
LINES = ['The purpose of this meeting is to hear your concerns and agree a plan.',
         'Maya, what do you need for testing on Monday?',
         'We will start two weeks later, and Alex will redo the rota by next Friday.']


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def error_rate(reference, heard):
    ref, hyp = words(reference), words(heard)
    table = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        previous, table[0] = table[0], i
        for j, h in enumerate(hyp, 1):
            previous, table[j] = table[j], min(table[j] + 1, table[j - 1] + 1, previous + (r != h))
    return round(table[-1] / max(1, len(ref)), 3)


def synthesize(client, text):
    started = time.perf_counter()
    pieces, first = [], None
    with client.stream('POST', '/api/tts/stream', json={'text': text}) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            event = json.loads(line) if line else {}
            if event.get('type') == 'error':
                raise RuntimeError(event['message'])
            if event.get('type') == 'audio':
                first = first or time.perf_counter() - started
                audio, rate = sf.read(io.BytesIO(base64.b64decode(event['audio_b64'])), dtype='float32')
                pieces.append(audio)
    return np.concatenate(pieces), rate, round(first * 1000)


def wav_bytes(audio, rate):
    buffer = io.BytesIO()
    sf.write(buffer, audio, rate, format='WAV', subtype='PCM_16')
    return buffer.getvalue()


def live_stream(port, cookie, session_id, audio, rate):
    with connect(f'ws://localhost:{port}/api/sessions/{session_id}/speech-stream', origin=f'http://localhost:{port}', additional_headers={'Cookie': cookie}, max_size=None) as socket:
        socket.send(json.dumps({'sample_rate': rate}))
        ready = json.loads(socket.recv(timeout=20))
        if ready['type'] != 'ready':
            raise RuntimeError(f'Stream not ready: {ready}')
        for start in range(0, len(audio), 4096):
            socket.send(np.asarray(audio[start:start + 4096], dtype='<f4').tobytes())
        socket.send(json.dumps({'type': 'finish'}))
        partials = 0
        while True:
            event = json.loads(socket.recv(timeout=30))
            partials += event['type'] == 'partial'
            if event['type'] == 'error':
                raise RuntimeError(event['message'])
            if event['type'] == 'final':
                return event, partials


def voice_turn(client, session_id, text, confidence, delay_ack=.02):
    """Behave like the browser: play each sentence, then acknowledge it."""
    started = time.perf_counter()
    payload = {'text': text, 'duration_seconds': 4, 'synthesize_audio': False, 'request_id': uuid.uuid4().hex, 'addressed_participant_ids': [], 'recognition': {'source': 'speech', 'unreliable': False, 'confidence': confidence}}
    speech, first_audio, audio_chunks, result = [], None, 0, None
    with httpx.Client(base_url=str(client.base_url), cookies=client.cookies, timeout=120) as ack, client.stream('POST', f'/api/sessions/{session_id}/voice-stream', json=payload) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            event = json.loads(line)
            if event['type'] == 'speech_text':
                speech.append((event['speaker'], event['text']))
            elif event['type'] == 'audio':
                audio_chunks += 1
                first_audio = first_audio or time.perf_counter() - started
                if not sf.read(io.BytesIO(base64.b64decode(event['audio_b64'])), dtype='float32')[0].size:
                    raise RuntimeError('Empty audio chunk')
            elif event['type'] == 'segment_end':
                time.sleep(delay_ack)
                acknowledged = ack.post(f'/api/sessions/{session_id}/playback', json={'utterance_id': event['utterance_id'], 'segment': event['segment']})
                acknowledged.raise_for_status()
            elif event['type'] in {'error', 'speech_error'}:
                raise RuntimeError(event['message'])
            elif event['type'] == 'result':
                result = event['result']
    return {'speech': speech, 'first_audio_ms': round((first_audio or 0) * 1000), 'audio_chunks': audio_chunks, 'total_ms': round((time.perf_counter() - started) * 1000), 'moves': [r.get('move') for r in result['responses']]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--delay', type=float, default=15)
    args = parser.parse_args()
    report = {}
    with httpx.Client(base_url=f'http://localhost:{args.port}', timeout=120) as client:
        health = client.get('/api/health').json()
        report['components'] = health['components']
        report['stt'] = health.get('stt_runtime')
        report['tts_engine'] = health.get('engine')
        if args.register:
            client.post('/api/auth/register', json={'name': 'Voice Check', 'organization': 'Eval', 'email': f'voice.{uuid.uuid4().hex[:8]}@example.test', 'password': 'Local-eval-only-7391!'}).raise_for_status()
        else:
            client.post('/api/auth/login', json={'email': os.environ['HIKARI_QA_EMAIL'], 'password': os.environ['HIKARI_QA_PASSWORD']}).raise_for_status()
        cookie = '; '.join(f'{key}={value}' for key, value in client.cookies.items())
        session = client.post('/api/sessions', json={'skill_id': 'english-speaking', 'difficulty': 'advanced', 'activity_id': 'english-28'})
        session.raise_for_status()
        sid = session.json()['id']
        report['engine_version'] = 3 if session.json()['runtime'].get('scene') else 2
        report['turns'] = []
        for line in LINES:
            audio, rate, tts_ms = synthesize(client, line)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            started = time.perf_counter()
            upload = client.post('/api/transcribe', files={'file': ('speech.wav', wav_bytes(audio, rate), 'audio/wav')}, data={'language': 'English', 'duration_ms': str(int(len(audio) / rate * 1000))})
            upload.raise_for_status()
            upload = upload.json()
            upload_ms = round((time.perf_counter() - started) * 1000)
            stream, partials = live_stream(args.port, cookie, sid, audio, rate)
            heard = stream.get('text') or upload.get('text') or ''
            turn = voice_turn(client, sid, heard, stream.get('confidence') or upload.get('confidence'))
            row = {'said': line, 'upload_text': upload.get('text'), 'upload_ms': upload_ms, 'upload_error_rate': error_rate(line, upload.get('text') or ''), 'stream_text': stream.get('text'), 'stream_final_ms': stream.get('latency_ms'),
                   'stream_partials': partials, 'stream_error_rate': error_rate(line, stream.get('text') or ''), 'tts_first_audio_ms': tts_ms, **turn}
            report['turns'].append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            time.sleep(args.delay)
        state = client.get(f'/api/sessions/{sid}/runtime').json()
        report['scene'] = state.get('scene')
        assessment = client.post(f'/api/sessions/{sid}/complete?end_attempt=true')
        assessment.raise_for_status()
        result = assessment.json()
        report['assessment'] = {'overall': result['overall'], 'scores': result['scores'], 'speech_signal': result.get('speech_signal')}
    print(json.dumps({k: report[k] for k in ('components', 'stt', 'tts_engine', 'engine_version', 'scene', 'assessment')}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
