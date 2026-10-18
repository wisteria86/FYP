# Hikari Employee Trainer

Hikari is an integrated AI-powered employee-training application. It combines authenticated learner workspaces, spoken roleplay, local speech models, persistent training data, organization-document grounding, and optional posture indicators.

## What works

- Ten workplace training areas, including communication, listening, conflict resolution, negotiation, interviews, presentations, critical thinking, responsible AI use, and defensive social-engineering awareness.
- Account registration and login with scrypt password hashing, revocable browser sessions, and owner-scoped private training records.
- Scenario preparation briefings with roles, objectives, target skills, difficulty, duration, and participant structure before a session is created.
- Adaptive beginner, intermediate, and advanced roleplay scenarios.
- Browser microphone capture with selectable Whisper Small ONNX, Whisper Medium ONNX, and NVIDIA Nemotron streaming recognition (CUDA or CPU), plus automatic Whisper fallback.
- Adaptive speech detection with a live input meter, automatic silence stop, microphone selection, and automatic submission.
- Kokoro is the low-latency default speech engine. ChatTTS and installed VITS providers can be selected in Settings. A **Play response** control remains available if browser sound policy blocks automatic playback.
- Two roleplay modes: **Voice call** is the default continuous hands-free loop, while **Chat** keeps typed messages, voice-message transcription, and replay controls.
- Qwen reasoning is disabled and hidden at the provider, then filtered again before any response can be displayed, stored, or spoken.
- Persistent SQLite history, scores, skill proficiency, recommendations, and three-session training plans.
- Evidence-based feedback across clarity, relevance, professionalism, active listening, delivery, and optional posture.
- PDF, DOCX, TXT, and Markdown policy uploads with local retrieval and source labels.
- Optional browser camera check limited to slouching, head position, shoulder alignment, and body orientation. It does not infer identity, emotion, health, or personality.

## Run locally on Windows

From `C:\Users\pc\Documents\FYP\VoiceBot`:

```powershell
.\start_hikari.cmd
```

That one command loads the models, serves the API and compiled dashboard, opens `http://localhost:8000`, and stops everything when you press Ctrl+C. It does not use Uvicorn reload mode, avoiding duplicate model copies in memory.

Useful test modes:

```powershell
.\start_hikari.cmd --check
.\start_hikari.cmd --skip-models
.\start_hikari.cmd --no-browser
.\start_hikari.cmd --dev
```

`--skip-models` is a fast text-only UI test. `--dev` additionally runs Vite on port 5173 for frontend development and requires Node.js/npm. Normal use does not require a second terminal or Node.js at runtime because FastAPI serves the compiled frontend.

Allow microphone access for spoken responses and camera access only if you want posture feedback.

The first backend start loads the available speech recognizer and selected TTS engine and may take longer. NVIDIA setup and CPU fallback are documented in [NVIDIA_SPEECH.md](docs/NVIDIA_SPEECH.md). The dashboard remains usable in a degraded text-only mode when an optional model fails to load.

## Run locally on Linux

From the `VoiceBot` directory, use Python 3.12 to create a **Linux** virtual
environment (do not reuse a Windows `.venv`) and install the dependencies. The
pinned Transformers/tokenizers stack currently fails to build on Python 3.13:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.template .env  # First setup only; configure your API key and Linux cache paths.
cd frontend
npm install
npm run build
cd ..
bash start_hikari.sh
```

The Linux launcher uses the same supervisor and supports the same options:

```bash
bash start_hikari.sh --check
bash start_hikari.sh --no-browser
bash start_hikari.sh --dev
```

For direct execution, run `chmod +x start_hikari.sh` once, then `./start_hikari.sh`.
Normal mode serves both the API and compiled frontend at `http://localhost:8000`;
Ctrl+C stops the app. Node.js/npm are needed to build the frontend or use `--dev`,
not to serve an already-built dashboard. Install system audio/FFmpeg dependencies
and platform-appropriate GPU libraries for your selected speech engines; adding
this launcher does not install them. Windows drive paths in a copied `.env` must
be replaced with Linux paths.

## Runtime monitor

Select **Monitor** in the sidebar during a test run. It refreshes every two seconds and reports:

- Browser-to-API round trip and server HTTP mean, p50, p95, request count, and error rate.
- Retrieval, LLM first-token, text-visible, first-audio, and completed voice-pipeline latency.
- Generated audio duration and ChatTTS real-time factor. A value below `1.0` means synthesis finished faster than the audio would play.
- System CPU/RAM, backend working-set memory and thread count.
- NVIDIA GPU utilization, VRAM use, temperature, and power when `nvidia-smi` is available.
- LLM, Whisper, ChatTTS, and database readiness and model-load durations.
- Selected microphone, sample rate, channels, live/peak/trigger levels, capture state, Whisper latency, recent transcript, and mic errors.

The monitor keeps a bounded in-memory test window. For explicit testing, it includes recent microphone transcripts and device details; these disappear when the backend restarts or when you select **Reset window**. It does not persist prompts or document content. Use **Reset window** before a repeatable benchmark.

## Configuration

Copy `.env.template` to `.env` and set at least:

```env
LLM_API_KEY=your_key
LLM_MODEL_NAME=qwen/qwen3.8-27b
LLM_BASE_URL=https://api.groq.com/openai/v1
COMMUNICATION_LANGUAGE=English
TTS_ENGINE=kokoro
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=auto
CHAT_TTS_DEVICE=auto
```

Use `CHAT_TTS_DEVICE=cuda:0` to require NVIDIA CUDA acceleration. Hikari verifies that ChatTTS's GPT, DVAE, decoder, embedding, and vocoder modules are actually on CUDA and reports their devices through `/api/health` and `/api/tts/engines`.

ChatTTS buffers each speaker's complete reply as one continuous utterance, avoiding gaps when generating the next sentence takes longer than playing the current sentence. Faster TTS engines retain sentence streaming. ChatTTS uses BF16 for its transformer on compatible CUDA GPUs; audio decoders retain their original precision. `CHAT_TTS_SPEAKER_SEED=9001` selects the higher-pitched speaker preset. ChatTTS samples speaker embeddings rather than providing a guaranteed gender selector.

Speech recognition uses multilingual Whisper `medium` on CUDA with `WHISPER_COMPUTE_TYPE=int8_float16` to leave GPU memory for ChatTTS. Recognition explicitly uses transcription rather than translation, with deterministic decoding. `/api/health` reports `stt_runtime` model, device, and precision; GPU initialization runs at startup. Runtime errors are reported as service failures, not misleading "no speech" results.

On Windows, faster-whisper needs separate CUDA 12 cuBLAS/cuDNN libraries only when using CUDA; CPU inference does not require CUDA. Those libraries are not installed by `requirements.txt`, and must be installed separately for CUDA inference. The STT module registers their DLL directories when available. To smoke-test the running app, use `.venv\Scripts\python.exe scripts\check_voice_latency.py` (synthesizes two sentences and transcribes the first; does not access the microphone).

The selected engine and Kokoro voice can also be changed from the Settings screen.

## Database migrations

Database changes are applied automatically from `database/migrations` when the application starts. Applied versions are recorded in `schema_migrations`; existing data is preserved while the normalized application model evolves.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run build
```

## Local data and privacy

Runtime records are stored in `data/hikari.db` and ignored by Git. Organization documents stay in local relational/vector storage, but retrieved excerpts and conversation text may be sent to the configured external AI provider. The learner sees a first-use disclosure. Browser camera frames are not uploaded: numeric body landmarks are sent to the local API for optional alignment indicators.

## Prototype learning acceptance

Learners must demonstrate lesson objectives with distinct meaningful answers before completion. A premature finish leaves the session active; **End Session** cancels without awarding mastery. Typed chat never depends on voice synthesis. If TTS fails during a call, the AI text remains usable. AI outages activate lesson-specific guided practice.

English recommendations progress through the 30-lesson sequence instead of repeatedly selecting lesson one. Assessment shows transcript evidence; grammar and fluency grades require the AI assessor and are omitted in offline fallback rather than fabricated. These are prototype training estimates, not certified proficiency tests. Microphone pronunciation is not inferred from text.

Speech models warm up during startup (`TTS_WARMUP=false` disables TTS warmup). Keep Whisper `medium` on CUDA as configured. The current TTS selection is preserved.

See [prototype acceptance results](docs/PROTOTYPE_ACCEPTANCE.md) for automated, live-pipeline and UI verification, and remaining physical-device acceptance checks.

See [12 October completion verification](docs/PROTOTYPE_COMPLETION_2026-10-12.md) for lesson-scoped RAG, optional posture, immutable scenario snapshots, additional workplace lessons, real-site checks and honest validation limits.

## Application status

The primary learner journey is integrated: create an account, review a persistent dashboard, select and prepare a scenario, complete a voice or chat roleplay, receive an assessment, and continue from updated proficiency, progress, recommendations, and training plans. Demo access is disabled by default; set `ALLOW_DEMO_ACCESS=true` only for isolated development fixtures.

## Setting up another PC

Use Python 3.12 and create a fresh virtual environment on the destination machine;
never copy `.venv` between PCs. Include all new source files when transferring the
project. Models, `.env`, runtime preferences and the compiled frontend are ignored
by Git, so a fresh clone requires setup and a frontend build.

Windows PowerShell, from `VoiceBot`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.template .env # First setup only; never overwrite existing secrets.
.\.venv\Scripts\python.exe scripts/setup_nemotron.py
cd frontend
npm ci
npm run build
cd ..
.\start_hikari.cmd
```

Linux, after the environment/dependency steps above:

```bash
.venv/bin/python scripts/setup_nemotron.py
cd frontend
npm ci
npm run build
cd ..
./start_hikari.sh
```

Configure your LLM credentials in `.env` before starting. The template selects
English Nemotron on CPU with no automatic Whisper fallback, and Piper on CPU.
Piper downloads its voice package on first use; Nemotron requires the setup command
above. Internet is needed for these downloads and the configured LLM API. Existing
`data/runtime_settings.json` may override the template's engine selections; inspect
Settings if migrating an existing installation.

Use `http://localhost:8000` on the destination PC. Select its microphone in Settings;
browser microphone identifiers and saved processing choices do not transfer between
PCs. Fresh browsers use browser-only suppression, manual turns and greedy decoding.
RNNoise requires 48 kHz AudioWorklet capture; choose browser-only suppression if the
browser cannot provide it. Automatic turns require the bundled Silero assets.

The pinned Sherpa wheel supports greedy Nemotron decoding. The isolated experimental
build is not part of installation, and selecting beam is validated before saving.
After backend changes, stop and restart Hikari, then refresh the browser; a stale
backend can return “Method Not Allowed” for a newly added endpoint.
