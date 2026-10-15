# Browser capture sample-rate crash

The native recognizer reported `Expected: 48000, given: 16000` when a real
browser capture finished. Incoming PCM used the browser AudioContext rate,
but Nemotron finalization appended padding at a hard-coded 16 kHz. Sherpa's
internal resampler requires an unchanged input rate for the entire stream.
Earlier reference tests used 16 kHz input and missed this case.

Each capture now owns its native stream, input rate and finalized state.
Final padding uses the capture's rate and one second of samples. Attempts to
change rates or reuse a finalized capture raise a Python ValueError before
calling the native runtime. Rates are independent across simultaneous captures.

Verification:

- 92 backend tests passed, including padding at 16/44.1/48 kHz, interleaved
  rates, invalid rate changes and duplicate finalization.
- Deployed native CPU WebSocket recognized real reference speech resampled to
  48 kHz and 44.1 kHz. Both returned finalized transcripts and remained healthy.
- Final decoder flush: 253.7 ms at 48 kHz and 246.6 ms at 44.1 kHz in these
  tests; these are not complete voice-response latency measurements.
- Backend restarted after releasing the crashed launcher. Existing Nemotron
  CPU recognition and Kokoro voice selection were retained.
- This verifies the failing native capture-rate path, not physical microphone
  permissions or user-accent accuracy.

Reproduce with the isolated QA credentials supplied as environment variables:

```powershell
.venv\Scripts\python.exe scripts/check_live_speech.py --device cpu --sample-rate 48000
.venv\Scripts\python.exe scripts/check_live_speech.py --device cpu --sample-rate 44100
```
