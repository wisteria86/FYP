# Compare English TTS engines

Restart Hikari after updating and refresh the browser. Open Settings and select
**Download & Switch** on Piper English or Kitten Nano INT8. The first selection
requires internet access and may take a while; later selections use the local
cache. A failed activation retains the previous working engine.

Both engines use Sherpa-ONNX on CPU. Nemotron's installed Sherpa runtime already
includes the needed API. If missing, install `requirements-english-tts.txt` into
the server environment. Do not replace a working CUDA Sherpa installation just
for these CPU voices.

Defaults:

| Engine | Package | Speaker | Threads |
| --- | --- | --- | --- |
| Piper | vits-piper-en_US-amy-low | 0 (Amy) | 2 |
| Kitten | kitten-nano-en-v0_8-int8 | 0 | 2 |

Packages are downloaded from the official Sherpa-ONNX `tts-models` release and
stored in `models/tts/`. Each package contains the ONNX model, tokens, eSpeak
data, and its supplied documentation/license files; Kitten also contains voices.
Optional `PIPER_MODEL_DIR` / `KITTEN_MODEL_DIR` point to existing extracted package
directories (relative paths resolve against VoiceBot). `PIPER_CPU_THREADS`,
`KITTEN_CPU_THREADS`, `PIPER_SPEAKER_ID`, and `KITTEN_SPEAKER_ID` configure loading.
The existing Kokoro voice selector applies only to Kokoro.

Test the same English text after one warmup preview for each engine. Compare
settings preview first, then an actual session. Browser console output
`[Hikari TTS latency]` includes engine, synthesis time, lock wait, character count,
and audio duration. `synthesis_ms / (audio_seconds * 1000)` below 1 means faster
than real time. Session `[Hikari backend latency]` and `[Hikari latency]` also
include the surrounding pipeline. Model download/loading time is not synthesis
latency. Sample rate is taken from each engine so playback has the correct pitch.

Sources:
- https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-tts.py
- https://k2-fsa.github.io/sherpa/onnx/tts/all/English/kitten-nano-en-v0_8-int8.html
