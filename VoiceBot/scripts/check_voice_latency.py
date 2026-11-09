"""Live voice latency check against a running Hikari server.

Engine and speech endpoints require sign-in, so set HIKARI_QA_EMAIL and HIKARI_QA_PASSWORD first.
For the complete loop, use scripts/conversation_eval/check_voice_stack.py.
"""
import base64
import json
import os
import time
import requests

BASE = "http://localhost:8000"
session = requests.Session()
session.post(f"{BASE}/api/auth/login", json={"email": os.environ["HIKARI_QA_EMAIL"], "password": os.environ["HIKARI_QA_PASSWORD"]}, timeout=20).raise_for_status()
started = time.perf_counter()
response = session.post(f"{BASE}/api/tts/stream", json={"text": "Hello, it is lovely to meet you. How are you today?"}, stream=True, timeout=90)
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
print({"first_audio_seconds": round(first or 0, 2), "total_seconds": round(time.perf_counter() - started, 2), "chunks": chunks})
print(session.post(f"{BASE}/api/transcribe", files={"file": ("voice.wav", audio, "audio/wav")}, data={"language": "English"}, timeout=60).json())
print(session.get(f"{BASE}/api/tts/engines", timeout=10).text[-1600:])
