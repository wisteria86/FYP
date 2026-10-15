"""Read-only live voice latency and synthesized-speech transcription check."""
import base64
import json
import time
import requests

started = time.perf_counter()
response = requests.post("http://localhost:8000/api/tts/stream", json={
    "text": "Hello, it is lovely to meet you. How are you today?"
}, stream=True, timeout=90)
response.raise_for_status()
first = None
audio = None
chunks = 0
for line in response.iter_lines():
    if not line:
        continue
    event = json.loads(line)
    if event["type"] == "error":
        raise RuntimeError(event["message"])
    if event["type"] == "audio":
        chunks += 1
        if first is None:
            first = time.perf_counter() - started
            audio = base64.b64decode(event["audio_b64"])
print({"first_audio_seconds": round(first or 0, 2), "total_seconds": round(time.perf_counter()-started, 2), "chunks": chunks})
print(requests.post("http://localhost:8000/api/transcribe", files={"file": ("voice.wav", audio, "audio/wav")}, data={"language": "en"}, timeout=60).text[:600])
print(requests.get("http://localhost:8000/api/tts/engines", timeout=10).text[-1600:])
