# Hikari Employee Trainer

Hikari is an English-first workplace-skills prototype that runs locally. It combines spoken AI roleplay, ChatTTS voice responses, structured assessment, adaptive proficiency tracking, organization-document grounding, and optional posture indicators.

## What works

- Ten workplace training areas, including communication, listening, conflict resolution, negotiation, interviews, presentations, critical thinking, responsible AI use, and defensive social-engineering awareness.
- Adaptive beginner, intermediate, and advanced roleplay scenarios.
- Browser microphone capture with local Whisper transcription.
- Adaptive speech detection with a live input meter, automatic silence stop, microphone selection, and automatic submission.
- ChatTTS speech for every generated response. Text appears as soon as the LLM finishes; voice uses one continuous, edge-faded buffer so it cannot underrun or click. A **Play response** control remains available if browser sound policy blocks automatic playback. Older TTS modules are preserved but are not active.
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

The first backend start loads Whisper and ChatTTS and may take longer. The dashboard remains usable in a degraded text-only mode when an optional model fails to load.
ChatTTS is warmed during startup so the first real roleplay response does not pay its one-time GPU setup cost.

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
LLM_MODEL_NAME=qwen/qwen3.6-27b
LLM_BASE_URL=https://api.groq.com/openai/v1
COMMUNICATION_LANGUAGE=English
TTS_ENGINE=chattts
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=auto
CHAT_TTS_DEVICE=auto
```

`TTS_ENGINE` is intentionally fixed to ChatTTS by the application. The setting remains documented so older environments are clear about the active engine.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run build
```

## Local data and privacy

Runtime records are stored in `data/hikari.db` and ignored by Git. Uploaded document text stays in that local database. Browser camera frames are not uploaded; when supported, the browser derives four numeric alignment indicators and only those scores are sent to the local API.

## Prototype boundaries

This is not an enterprise deployment. It intentionally excludes SSO, unrestricted multilingual training, psychological diagnosis, emotion/personality assessment, identity recognition, comprehensive gesture analysis, and offensive social-engineering instruction.
