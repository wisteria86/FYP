"""Sequential live TTS comparison; restores the original engine and voice."""
import json
import statistics
import time
import requests

BASE = 'http://127.0.0.1:8000/api'
TEXT = 'Hello, it is lovely to meet you. How are you today?'

def select(engine, voice=None):
    body = {'engine': engine}
    if voice:
        body['voice'] = voice
    response = requests.post(BASE + '/tts/engine', json=body, timeout=300)
    response.raise_for_status()
    return response.json()

if __name__ == '__main__':
    original = requests.get(BASE + '/tts/engines', timeout=10).json()
    print('original_state', json.dumps(original), flush=True)
    try:
        for engine in ('kokoro', 'chattts'):
            start = time.perf_counter()
            state = select(engine)
            print('engine', engine, 'activation_seconds', round(time.perf_counter()-start, 3),
                  'runtime', state.get('runtime'), flush=True)
            results = []
            for trial in range(3):
                start = time.perf_counter()
                first = None
                chunks = 0
                with requests.post(BASE + '/tts/stream', json={'text': TEXT},
                                   stream=True, timeout=120) as response:
                    response.raise_for_status()
                    for line in response.iter_lines(chunk_size=1):
                        if not line:
                            continue
                        event = json.loads(line)
                        if event['type'] == 'error':
                            raise RuntimeError(event['message'])
                        if event['type'] == 'audio':
                            chunks += 1
                            if first is None:
                                first = time.perf_counter()-start
                result = {'trial': trial+1, 'first_audio_s': round(first, 3),
                          'total_s': round(time.perf_counter()-start, 3), 'chunks': chunks}
                results.append(result)
                print(engine, json.dumps(result), flush=True)
            print(engine, 'median_first_audio_s', statistics.median(r['first_audio_s'] for r in results),
                  'median_total_s', statistics.median(r['total_s'] for r in results), flush=True)
    finally:
        restored = select(original.get('active', 'kokoro'), original.get('current_voice'))
        print('restored', restored.get('active'), restored.get('current_voice'), flush=True)
