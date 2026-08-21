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
| `vits_ar` | VITS Arabic ONNX | Arabic (Jordanian) | Downloads ~64 MB on first run; needs espeak-ng |

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

### Switching to Arabic (VITS)

#### 1. Install the espeak-ng system binary (one-time)

The Arabic TTS engine uses `phonemizer` as a Python wrapper around `espeak-ng`'s
Arabic G2P. `espeak-ng` must be installed as a **system binary** before running:

| Platform | Command |
|----------|---------|
| Windows | Download installer: https://github.com/espeak-ng/espeak-ng/releases |
| Linux (Ubuntu/Debian) | `sudo apt install espeak-ng` |
| macOS | `brew install espeak-ng` |

Verify the install: `espeak-ng --version`

#### 2. Install Python packages

```bash
pip install phonemizer
```

#### 3. Configure `.env`

```env
TTS_ENGINE=vits_ar

# Use multilingual Whisper to transcribe Arabic speech
WHISPER_MODEL_SIZE=small

# Optional tuning
VITS_AR_SPEAKER_ID=0
VITS_AR_QUANTIZE=True   # convert fp32 → int8 on first run (recommended for CPU)
```

On first run, VoiceBot will automatically download the model from HuggingFace
(`rhasspy/piper-voices`, `ar_JO-kareem-medium`) into `models/vits_ar/` (gitignored).
Subsequent runs use the local cache — no re-download.

### Performance Notes (Arabic)

- **fp32 on CPU is fast.** Unlike the Japanese model (fp16), the Arabic kareem-medium
  model ships as **fp32** — the native format for CPU inference. No precision penalty.
- **Optional int8 quantization.** `VITS_AR_QUANTIZE=True` (the default) converts the
  fp32 model to int8 via ONNX Runtime dynamic quantization on first run, saving the
  result as `models/vits_ar/ar_JO-kareem-medium-int8.onnx` (3–4× faster than fp32,
  negligible quality difference for TTS).
- **Sample rate:** The model outputs at 22,050 Hz. `SpeakerPlayer` is initialized with
  this rate directly via `tts_model.output_sample_rate` — no resampling is performed.
- **Thread allocation:** `ORT_INTRA_THREADS` and `ORT_INTER_THREADS` in `.env` control
  ONNX Runtime thread counts (default: auto-detect all logical cores) — same for all
  VITS engines.

### Verifying the Arabic Engine (Smoke Test)

```bash
python modules/tts_vits_ar.py
```

This synthesizes a short Arabic sentence (مرحباً، أنا مساعدك الصوتي، كيف يمكنني مساعدتك اليوم؟)
and writes it to `test_vits_ar_output.wav` without starting the full voice loop.

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

## ⚠️ License Notice — Kareem Arabic Voice Model

The Arabic TTS model (`rhasspy/piper-voices`, `ar_JO-kareem-medium`) is trained on the
**Arabic Speech Corpus** by **Nawar Halabi**, released under **CC BY 4.0**.

- **Attribution is required.** You must credit Nawar Halabi and the Arabic Speech Corpus
  when distributing output or applications built on this voice:
  [http://en.arabicspeechcorpus.com/](http://en.arabicspeechcorpus.com/)
- **Commercial use is permitted** under CC BY 4.0, provided attribution is included.

The piper-voices repository itself is MIT-licensed.

---

## Configuration Reference

All settings live in `.env` (loaded via `python-dotenv`). See `config.py` for defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | — | API key for LLM provider |
| `LLM_MODEL_NAME` | `qwen/qwen3-32b` | Model identifier |
| `LLM_BASE_URL` | GroqCloud URL | OpenAI-compatible endpoint |
| `WHISPER_MODEL_SIZE` | `small.en` | `small` for multilingual (Japanese/Arabic) |
| `TTS_ENGINE` | `kokoro` | `kokoro`, `vits_ja`, or `vits_ar` |
| `KOKORO_LANG` | `a` | `a`=American English, `b`=British |
| `KOKORO_VOICE` | `af_heart` | Kokoro voice name |
| `VITS_JA_HF_REPO_ID` | `ayousanz/piper-plus-tsukuyomi-chan` | HuggingFace repo |
| `VITS_JA_ONNX_FILE` | `tsukuyomi-chan-6lang-fp16.onnx` | ONNX filename in repo |
| `VITS_JA_CONFIG_FILE` | `config.json` | Config JSON filename |
| `VITS_JA_CACHE_DIR` | `models/vits_ja` | Local cache directory |
| `VITS_JA_SPEAKER_ID` | `0` | Speaker index (multi-speaker models) |
| `VITS_JA_SAMPLE_RATE` | `22050` | Model native output sample rate |
| `VITS_JA_QUANTIZE` | `True` | Auto-quantize to int8 on first run |
| `VITS_AR_HF_REPO_ID` | `rhasspy/piper-voices` | HuggingFace repo |
| `VITS_AR_ONNX_FILE` | `ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx` | ONNX path in repo |
| `VITS_AR_CONFIG_FILE` | `ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json` | Config path in repo |
| `VITS_AR_CACHE_DIR` | `models/vits_ar` | Local cache directory |
| `VITS_AR_SPEAKER_ID` | `0` | Speaker index |
| `VITS_AR_SAMPLE_RATE` | `22050` | Model native output sample rate |
| `VITS_AR_QUANTIZE` | `True` | Auto-quantize fp32→int8 on first run |
| `ORT_INTRA_THREADS` | `0` (auto) | ONNX intra-op thread count |
| `ORT_INTER_THREADS` | `0` (auto) | ONNX inter-op thread count |
| `SAMPLE_RATE` | `16000` | Microphone capture sample rate |
| `HEADSET_MODE` | `True` | Auto-detect headset for barge-in |
