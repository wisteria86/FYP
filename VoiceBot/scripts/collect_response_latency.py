"""Collect only opt-in timing events for ten minutes; no audio or transcripts."""
import json
import time
import requests

seen = set()
deadline = time.monotonic() + 600
print('Timing collector active for 10 minutes. No extra audio/transcripts saved.', flush=True)
while time.monotonic() < deadline:
    try:
        response = requests.get('http://127.0.0.1:8000/api/monitor/snapshot', timeout=5)
        response.raise_for_status()
        for event in reversed(response.json()['recent']):
            if event.get('name') != 'playback_started' or event['timestamp'] in seen:
                continue
            seen.add(event['timestamp'])
            keys = ('timestamp', 'engine', 'duration_ms', 'endpointing_ms',
                    'transcription_wall_ms', 'response_to_playback_ms', 'audio_output_latency_ms')
            print(json.dumps({key: event.get(key) for key in keys}), flush=True)
    except requests.RequestException:
        pass
    time.sleep(2)
print('Timing collection ended.', flush=True)
