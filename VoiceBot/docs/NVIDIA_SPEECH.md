# Local NVIDIA recognition and Whisper fallback

The default `STT_ENGINE=auto` selects the NVIDIA English Nemotron streaming
model when a compatible NVIDIA CUDA GPU, GPU runtime and downloaded model
are available. Otherwise it loads Whisper medium. CPU fallback forces CPU
execution and uses an appropriate integer precision. `STT_ENGINE=whisper`
restores the previous provider without removing the NVIDIA cache.

English browser calls send mono float32 PCM over an authenticated WebSocket
while the learner speaks. Each capture has its own cache-aware recognizer
stream; only finalized text starts a conversation turn. Partial transcripts
are display-only. The client retains a WebM recording for recovery if the
connection or recognizer fails. Non-English lessons use Whisper, loaded lazily
to avoid allocating two speech models unnecessarily during English practice.

## Setup on an NVIDIA machine

From the VoiceBot folder:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-nemotron.txt
.venv\Scripts\python.exe scripts/setup_nemotron.py
.venv\Scripts\python.exe run_hikari.py
```

On this machine, the user-approved model cache is on
`F:/Hikari-model-cache/nemotron`; `.env` sets `NEMOTRON_MODEL_DIR` to its
model subfolder. To install on that drive use:

```powershell
.venv\Scripts\python.exe scripts/setup_nemotron.py --cache-dir F:\Hikari-model-cache\nemotron
```

CPU-only machines need only the normal requirements and existing Whisper
cache/download. They do not need the optional CUDA runtime or Nemotron model.
The optional runtime is pinned separately to avoid upgrading the PyTorch and
Transformers versions used by ChatTTS. No cloud speech service is used.

The monitor's `/api/health` response reports `stt_runtime.engine`, `device`,
`streaming`, and any `fallback_reason`. Merely detecting a GPU is not enough:
initialization performs a real decode to catch runtime/DLL errors at startup.

## Scope and limitations

- Model: `nvidia/nemotron-speech-streaming-en-0.6b`, March 2026 checkpoint,
  Sherpa-ONNX April 25 ONNX export, 560 ms chunks, int8 weights.
- English only. Urdu and other languages continue through multilingual Whisper.
- A 560 ms model chunk is **not** a guaranteed complete-turn latency.
- Accuracy on learner accents, names and imperfect English needs recorded/user
  evaluation. Synthetic/reference audio tests do not establish accent accuracy.
- Native microphone permissions, room echo and interruptions need device testing.
- Model weights are governed by the NVIDIA Open Model License; the runtime has
  its own license. Preserve the upstream license files in the model cache.

Sources:
- https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b
- https://k2-fsa.github.io/sherpa/onnx/nemo/nemotron-streaming.html
- https://k2-fsa.github.io/sherpa/onnx/python/install.html

## Verification on October 12, 2026

- 80 backend tests passed, including no-CUDA selection, lazy non-English
  fallback, startup/decode failure fallback, authentication and PCM validation.
- Browser streaming/transcription regression tests and production build passed.
- Actual CUDA reference-audio recognition passed, not just mocked providers.
- Deployed localhost authenticated WebSocket produced 10 provisional events
  and one finalized transcript. Final decoder flush took 393.3 ms in that test.
  This is not speech-end-to-audible-response latency or an accent benchmark.
- Running server reports `engine=nemotron`, `device=cuda`, `streaming=true`,
  all components ready, and no model errors. Existing Kokoro selection retained.
- No physical microphone or user accent accuracy claim is made by these checks.
