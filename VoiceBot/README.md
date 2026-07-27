# VoiceBot

A Duolingo-style language-learning voice bot with a strictly decoupled, interface-driven architecture. Supports multiple TTS engines selectable via a single `.env` setting.

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in LLM_API_KEY
python main.py
```

---

## TTS Engine Selection

Set `TTS_ENGINE` in your `.env` file (or shell environment):

| Value | Engine | Language | Notes |
|-------|--------|----------|-------|
| `kokoro` | KokoroTTS (default) | English | No extra download |
| `vits_ja` | VITS Japanese ONNX | Japanese | Downloads ~170 MB on first run |

### Switching to Japanese (VITS)

Add to your `.env`:

```env
TTS_ENGINE=vits_ja

# Recommended: use multilingual Whisper so it can transcribe Japanese speech
WHISPER_MODEL_SIZE=small

# Optional tuning (see config.py for all options)
VITS_JA_SPEAKER_ID=0
VITS_JA_QUANTIZE=True   # convert fp16→int8 on first run for faster CPU inference
```

On first run, VoiceBot will automatically download the model from HuggingFace
(`ayousanz/piper-plus-tsukuyomi-chan`) into `models/vits_ja/` (gitignored).
Subsequent runs use the local cache — no re-download.

### Performance Notes

- **fp16 on CPU is slow.** `VITS_JA_QUANTIZE=True` (the default) converts the downloaded
  fp16 weights to int8 via ONNX Runtime dynamic quantization on first run. The int8 model
  is saved as `models/vits_ja/tsukuyomi-chan-6lang-fp16-int8.onnx` and used for all
  subsequent inference (typically 3–4× faster than fp16 on a multi-core CPU).
- **Sample rate:** The VITS model outputs at 22,050 Hz. `SpeakerPlayer` is initialized
  with this rate directly — no resampling is performed.
- **Thread allocation:** `ORT_INTRA_THREADS` and `ORT_INTER_THREADS` in `.env` control
  ONNX Runtime thread counts (default: auto-detect all logical cores).

### Verifying the Japanese Engine (Smoke Test)

```bash
python modules/tts_vits_ja.py
```

This synthesizes a short Japanese sentence and writes it to `test_vits_ja_output.wav`
without starting the full voice loop. Useful for checking model quality and latency.

---

## ⚠️ License Notice — Tsukuyomi-chan Voice Model

The Japanese TTS model (`ayousanz/piper-plus-tsukuyomi-chan`) uses voice data from the
**Tsukuyomi-chan corpus**, which belongs to **Rei Yumesaki**.

- **Attribution is required.** You must credit Rei Yumesaki when distributing output.
- **Commercial use is restricted.** Please read the full corpus license before
  using this bot in a commercial product or service:
  [https://tyc.rei-yumesaki.net/material/corpus/](https://tyc.rei-yumesaki.net/material/corpus/)

The piper-plus engine itself is MIT-licensed.

---

## Configuration Reference

All settings live in `.env` (loaded via `python-dotenv`). See `config.py` for defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | — | API key for LLM provider |
| `LLM_MODEL_NAME` | `qwen/qwen3-32b` | Model identifier |
| `LLM_BASE_URL` | GroqCloud URL | OpenAI-compatible endpoint |
| `WHISPER_MODEL_SIZE` | `small.en` | `small` for multilingual (Japanese) |
| `TTS_ENGINE` | `kokoro` | `kokoro` or `vits_ja` |
| `KOKORO_LANG` | `a` | `a`=American English, `b`=British |
| `KOKORO_VOICE` | `af_heart` | Kokoro voice name |
| `VITS_JA_HF_REPO_ID` | `ayousanz/piper-plus-tsukuyomi-chan` | HuggingFace repo |
| `VITS_JA_ONNX_FILE` | `tsukuyomi-chan-6lang-fp16.onnx` | ONNX filename in repo |
| `VITS_JA_CONFIG_FILE` | `config.json` | Config JSON filename |
| `VITS_JA_CACHE_DIR` | `models/vits_ja` | Local cache directory |
| `VITS_JA_SPEAKER_ID` | `0` | Speaker index (multi-speaker models) |
| `VITS_JA_SAMPLE_RATE` | `22050` | Model native output sample rate |
| `VITS_JA_QUANTIZE` | `True` | Auto-quantize to int8 on first run |
| `ORT_INTRA_THREADS` | `0` (auto) | ONNX intra-op thread count |
| `ORT_INTER_THREADS` | `0` (auto) | ONNX inter-op thread count |
| `SAMPLE_RATE` | `16000` | Microphone capture sample rate |
| `HEADSET_MODE` | `True` | Auto-detect headset for barge-in |
