# Recognition settings and CPU performance

Settings now offers genuine Whisper Small ONNX, Whisper Medium ONNX, and
NVIDIA Nemotron Streaming ASR, with Automatic and CPU-only execution choices.
Small/medium use multilingual INT8 encoder/decoder exports, not the old
CTranslate2 backend renamed as ONNX. Whisper's original CTranslate2 medium
remains the automatic fallback when NVIDIA Auto cannot use CUDA, or for
unsupported languages in a Nemotron lesson. Explicit Nemotron CPU mode is
allowed on CPU-only machines and retains live PCM/cache-aware recognition.

Switches are persisted independently of TTS preferences. Active recognition
leases block switches. A failed new-model load retains the old model/settings.
Existing speech-model caches remain available on the user-approved F: drive.

## Measurements

Ryzen 5 5600 / RTX 5060, INT8 exports, four CPU threads, identical 6.625-second
reference clip, one excluded warmup and three measured iterations:

| Engine/device | Warm median total decode | Real-time factor | Final streaming flush |
|---|---:|---:|---:|
| Nemotron CPU | 1.759 s | 0.265 | 260.5 ms |
| Nemotron CUDA | 2.567 s | 0.387 | 362.7 ms |
| Whisper Small ONNX CPU | 4.031 s | 0.608 | Not streaming |
| Whisper Medium ONNX CPU | 13.467 s | 2.033 | Not streaming |

CPU Nemotron and CUDA Nemotron produced identical reference transcripts across
these runs. All four modes recognized the same reference words; Whisper
punctuation differed. These are not end-to-end voice-response times, an accent
accuracy benchmark, or evidence of identical quality across all inputs. CPU
and CUDA use the same Nemotron weights; numerical/runtime differences can still
affect outputs on other audio. GPU is not universally faster for small streaming
workloads, and results vary by processor, competing tasks and runtime.

## Recommended CPU path

For English, select **NVIDIA Nemotron Streaming ASR → CPU only**. It processes
audio during speech, leaving only the final flush after endpointing. Keep a
CPU-efficient voice such as Kokoro for the complete CPU voice pipeline.
For multilingual work, Small ONNX is the lower-cost option. Medium ONNX is
available for comparison but was slower than real time on this machine and
should not be presented as a low-latency CPU default.

No claim of GPU-speed parity on arbitrary CPU-only devices is made. New user
accents, names, imperfect English and mixed-language speech need representative
evaluation before making accuracy guarantees.

## Verification

- 88 backend regression tests passed, including settings/authentication,
  persistence/rollback, explicit CPU mode and recognition-switch exclusion.
- Seven browser-client streaming tests passed; production frontend built.
- Deployed HTTP settings changed through all three models and performed actual
  CPU transcription. TTS engine/voice stayed unchanged; original recognition
  selection was restored after testing.
- Deployed CPU WebSocket produced nine provisional transcript events and a
  finalized transcript, with a 266.8 ms decoder flush on the reference clip.
- Visual browser verification was unavailable: the browser helper failed to
  initialize after reset. Compiled frontend/API checks do not replace visual QA.

Reproduce:

```powershell
.venv\Scripts\python.exe scripts/benchmark_recognition.py --engine nemotron --device cpu --threads 4
.venv\Scripts\python.exe scripts/benchmark_recognition.py --engine whisper_small_onnx --device cpu --threads 4
.venv\Scripts\python.exe scripts/benchmark_recognition.py --engine whisper_medium_onnx --device cpu --threads 4
```

Model exports and runtime references:
- https://k2-fsa.github.io/sherpa/onnx/nemo/nemotron-streaming.html
- https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/tiny.en.html
