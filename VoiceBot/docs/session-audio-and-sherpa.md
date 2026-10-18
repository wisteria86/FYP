# Session audio preferences

Open Settings → Audio settings for sessions. Select the microphone, noise
processing, optional software gain, manual or automatic input, and whether to recognize live. Save, then
join a new voice session. Device-specific preferences are saved in this browser.
Changes made while a call is active apply to the next call.

The voice test's **Use these settings in sessions** button copies its current
microphone, processing mode, and gain into that profile. Live-recognition choice
is preserved. Test controls otherwise remain independent.

Processing order: browser capture constraints → optional software gain → optional
RNNoise → recording and recognition. Browser suppression is requested only for
Browser-only or Browser + RNNoise modes. Echo cancellation remains on and browser
automatic gain remains off. The audio side panel shows the saved processing profile.

Manual input uses one bottom-bar button: Record voice → Stop & send. Automatic
input starts listening between replies and uses Silero to send after a speech
pause; Stop & send is also available. Manual remains the default. With
live recognition enabled, audio reaches the recognizer while recording, but the
conversation does not receive the turn until Stop & send. A final live transcript
is reused; recorded-audio recognition is used if streaming is unavailable or empty.
There is no automatic Whisper fallback.

# Isolated Sherpa evaluation

Published runtime: 1.13.8. Newer upstream source evaluated at commit
`1a9d234ab95567eba8c2e89873a87d70b79633e2`.

Source: https://github.com/k2-fsa/sherpa-onnx/tree/1a9d234ab95567eba8c2e89873a87d70b79633e2

The experimental source, build, and Python package live under `/tmp/hikari-sherpa-*`.
They do not replace the application virtual environment. Native build output is
in `/tmp/hikari-sherpa-build.log`.

The repeatable evaluation script is `scripts/evaluate_sherpa_runtime.py`. It tests
the three bundled reference recordings against their published transcripts,
optionally adds saved microphone files, and can smoke-test both English TTS engines.
Each invocation uses one decoder. Recognition time excludes model loading and
audio-container decoding. Results are single-machine spot checks, not a broad
accuracy benchmark; microphone recordings without a reference have no WER score.

## Results

All runs used CPU, four recognition threads, the same INT8 Nemotron model, and
identical PCM16 decoding at 16 kHz. Beam search used four active paths.

| Runtime / decoder | Total recognition time, four clips | Reference WER (0 / 1 / 8k) | Microphone text |
| --- | ---: | --- | --- |
| Published wheel, greedy | 31.47 s | 0% / 0% / 0% | Hello |
| New source, greedy | 31.56 s | 0% / 0% / 0% | Hello |
| New source, modified beam | 36.42 s | 0% / 4.17% / 0% | Hello |

The beam WER difference is the spelling/tokenization `forever` versus the reference
`for ever`, rather than a clearly worse spoken-word interpretation. Beam search
works in the new source build but took about 15% longer than source greedy across
these clips and showed no demonstrated accuracy gain. Keep greedy for now. These
are single runs, with no claim of statistically significant speed differences.
Recognition times include feeding the entire recording, not just the final wait
after live speech ends; they should not be compared directly with UI finalization
latency. No recording with a verified spoken “Hikari” reference was available.

The new runtime also generated nonempty audio with both TTS engines after a warmup:
Piper 344 ms / 3.417 seconds of audio; Kitten 2768 ms / 3.853 seconds of audio.
Both used two threads. This is a synthesis smoke test, not a listening evaluation.

Raw reports: [stable greedy](benchmarks/sherpa-stable-greedy.json),
[source greedy and TTS](benchmarks/sherpa-source-greedy.json),
[source beam](benchmarks/sherpa-source-beam.json).

Both builds report version 1.13.8 and ONNX Runtime 1.28.2. The source's embedded
`git_sha1` is stale (`8c8e275d`); `source_commit` in the reports records the actual
checked-out SHA. The application environment has not been upgraded, so its decoder
comparison still uses the installed wheel and may report beam as unavailable.

## Repeat an isolated comparison

From the VoiceBot directory, while the temporary environments still exist:

```bash
PYTHONPATH=/tmp/hikari-audio-debug /usr/bin/python3 scripts/evaluate_sherpa_runtime.py \
  --method greedy_search --output /tmp/sherpa-stable.json

PYTHONPATH=/tmp/hikari-sherpa-next/python:/tmp/hikari-audio-debug \
LD_LIBRARY_PATH=/tmp/hikari-sherpa-build/_deps/onnxruntime-src/lib \
/usr/bin/python3 scripts/evaluate_sherpa_runtime.py \
  --method modified_beam_search --beam 4 \
  --source-commit 1a9d234ab95567eba8c2e89873a87d70b79633e2 \
  --output /tmp/sherpa-source-beam.json
```

Add `--audio /path/to/recording.webm` for another recording; add `--tts` to check
Piper and Kitten. Temporary build files can disappear on cleanup or reboot.

## Session decoder selection

Settings → Audio settings for sessions → Nemotron decoding selects greedy search
or modified beam search (four active paths). The preference is stored in this
browser and applies on the next voice-session join to both live PCM streaming and
recorded recognition. Test comparisons remain independent.

Saving beam search probes the installed runtime in a disposable process before
loading a cached decoder in the API. An unavailable decoder leaves the previous
saved settings intact. The isolated source experiment does not upgrade the app;
beam can remain unavailable until the app itself runs a compatible Sherpa build.
On a compatible runtime, the extra decoder loads once and is reused; keeping both
loaded consumes additional model memory. Greedy remains the default.
