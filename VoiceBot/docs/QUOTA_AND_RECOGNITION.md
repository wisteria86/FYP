# LLM quota and recognition changes — 8 November 2026

## Conversation requests

Public group cases now use one streamed completion for two distinct characters.
The prompt contains public scenario context once, plus each selected participant's
identity and direction. One JSON line becomes the first reply; the second remains
a private draft until playback acknowledges the first. Interruption discards it.
If validation changes the first reply, its speculative continuation is discarded.
The local director can still select a different stakeholder when necessary.

Batching is disabled for negotiation, any AI private knowledge, different public
knowledge, pending repairs, personal clarification and locally grounded replies.
Those paths retain the existing role-scoped provider interface. Learner preparation
never enters a shared character prompt. Two audible AI turns remain the maximum.

`modules/llm_quota.py` shares admission control between adapters using the same
provider credential and model. It observes response headers and Retry-After,
reserves estimated input/output tokens, and blocks requests locally during a
known cooldown. No hidden SDK retries. Diagnostics retain rate-limit numbers,
not credentials, organization IDs or prompts. All LLMBrain requests use this gate.
Background review waits for idle time and at least 120 seconds between starts;
quota deferral does not manufacture assessment or mark dialogue offline. Explicit
review is still possible. A retry deadline persists with the session and the UI
shows a countdown instead of repeatedly submitting the failed learner turn.

Live checks against the configured Groq model demonstrated two characters from
**one** provider request, with text result time around 1.2–1.4 seconds. This is
a 50% reduction in character-generation calls for an eligible two-person exchange,
not a 50% reduction in all application requests. Captions and assessment have
their own costs. The account still hit 429: observed cooldowns included 156 and
403 seconds. Further attempts in those runs sent zero requests during cooldown.
The latter response reported all 8,000 per-minute tokens available and 944 of
1,000 requests remaining, so these two headers alone do not identify the exhausted
quota. A subsequent check, after the requested cooldown, confirmed **tokens per
day: limit 200,000, used 198,441, requested 1,636**. The account had consumed about
99.2% of its daily allowance. Do not claim the account limit has been removed or
all live turns passed. Reports: `tmp/runtime-tests/batched-group-quota.json` and
`tmp/runtime-tests/batched-group-quota-reason.json`.

Provider limits can include daily tokens as well as minute tokens and requests;
they apply across the organization. Exact account limits must be checked in the
[Groq limits page](https://console.groq.com/settings/limits), as explained in
[Groq's rate-limit documentation](https://console.groq.com/docs/rate-limits).
Long cooldowns can require a different configured model or a higher account quota.
No provider/model or billing plan was switched automatically.

## Recognition

The saved recognizer was Nemotron on CUDA. Its greedy streaming decoder does not
consume the previous full-scenario `initial_prompt`; changing CUDA or simply
adding prompt prose cannot fix its word substitutions. Sherpa hotword biasing
requires a supported modified-beam decoder, per the
[Sherpa documentation](https://k2-fsa.github.io/sherpa/onnx/hotwords/index.html).
Existing local beam comparisons did not establish an accuracy advantage.

Session audio preferences now include **Check final English transcript with local
Whisper**, now **off by default** after the latency correction below. Nemotron still produces live text.
When recording stops, the complete in-memory recording is decoded locally using
the installed faster-whisper model, beam size 5, a fixed lesson language and no
previous-transcript conditioning. Public participant names and bounded case
vocabulary supply hotwords, never learner preparation or a proposed answer.
Negated/unestablished scenario details are excluded from vocabulary. Models are
loaded from the existing local cache only; no automatic download or LLM call.
Implementation follows the supported [faster-whisper interface](https://github.com/SYSTRAN/faster-whisper).

Low likelihood, large decoder disagreement, changed numbers or changed negation
hold the transcript for review. The voice call includes an editor and the live
recognizer's alternative; sending after review retains both hypotheses and learner
confirmation. Uncertain manual recognition is no longer sent automatically.
Model likelihood is **not** a calibrated probability of correctness. Smaller
substitutions can still be wrong. If the local verifier cannot load, the live
transcript is held for review and the failure is labelled. A deliberate short
answer is no longer rejected merely because recording included preceding silence.

No server-side raw-audio recording was introduced. The browser's existing explicit
recording-export control remains available for learner-directed diagnostics.
Restart the backend and refresh the frontend to load these changes. The first
Whisper pass includes lazy model loading; disabling the new preference restores
the fast live-only path.

## Evidence and limits

On this RTX 5060, installed Whisper medium loaded in roughly 17 seconds. Six
same-audio comparisons used three bundled reference clips (4.83–16.71 seconds),
both original and deterministic synthetic noise at 8 dB SNR. Both models had zero
word errors on the clean clips. Across the noisy copies, Nemotron had 1/77 errors
and Whisper 4/77; three Whisper errors were spelling/tokenization differences
(`dishonoured/dishonored`, `for ever/forever`). The remaining lexical error was
different between models. Warm Whisper decode took 0.47–1.96 seconds.

This small sample does **not** demonstrate lower WER for the learner's microphone,
accent or domain. The second pass is an alternative acoustic decode plus a review
mechanism, not proof of improved accuracy for every speaker. Measure real WER with
consented recordings and verified references before making an improvement claim.
`scripts/compare_final_recognition.py --manifest manifest.json --output report.json`
accepts `[{"path":"...wav","reference":"exact words spoken"}]`; it uses no LLM.
Current results: `tmp/runtime-tests/final-recognition-comparison.json`.

Automated coverage includes shared cooldowns, token admission, private-knowledge
batch exclusions, two-speaker call count, interruption/partial delivery, invalid
first drafts, vocabulary isolation, original transcripts, numeric/negation
disagreement, verifier failure and authenticated session vocabulary. Full backend
suite: 231 passing; frontend: 46 passing; production build passed. After the final
recognition-routing adjustment, 59 targeted backend tests passed (including one
new routing regression); the six quota tests also passed after the final
diagnostic-message change.
The settings control was checked in the browser. Live physical microphone,
headset/speaker echo, final-pass learner WER, and English/Urdu educational review
remain human acceptance tasks; do not label them complete.

## Follow-up: remove the default second-pass delay

The initial always-on final pass held every learner turn until a complete Whisper
decode finished, including a roughly 17-second lazy model load on first use.
The browser now reuses completed Nemotron recognition immediately by default.
An empty/unavailable live result still falls back to recorded recognition, and
uncertainty still opens transcript review. The slower Whisper check remains an
explicit opt-in in session audio settings.

Preferences from the previous policy migrate to fast recognition on reload;
microphone, decoder, input mode, suppression and gain are preserved. New explicit
accuracy choices persist under recognition policy version 2. Refresh the app and
rejoin the call to load the updated preference. This removes the extra decode
from the default request path; provider cooldowns and generation/TTS latency are
separate and unchanged. No physical end-to-end latency improvement is claimed
until measured in a new call.

## Follow-up: stop defaulting to RNNoise (25 November 2026)

An offline test ran the RNNoise build that Hikari uses (48 kHz, 480-sample frames)
over the accent test sets before Nemotron decoding. Error rates are word error
rate at 560 ms lookahead.

| Set | Raw audio | After RNNoise |
|---|---|---|
| South Asian Common Voice test | 8.37 | 22.00 |
| EdAcc, South Asian speakers | 13.93 | 38.40 |
| EdAcc, Urdu speakers | 17.54 | 48.66 |
| EdAcc, mainstream US English | 13.30 | 17.66 |
| LibriSpeech test-clean | 2.38 | 2.77 |

RNNoise removed about 12% of loud speech frames on phone-quality recordings, and
it hurt South Asian speakers most. The test audio was already 16 kHz, while live
capture is raw 48 kHz, so the live effect may be smaller. Hikari's own raw
recordings are needed to measure it.

Changes:
- The fallback for missing or unknown settings is now browser suppression.
- The voice test page now starts on browser suppression.
- Saved RNNoise or Browser + RNNoise choices move to browser suppression once,
  under recognition policy version 3.

Device, decoder, input mode and gain are preserved. RNNoise stays selectable, and
a choice made after the migration persists. Browser (WebRTC) suppression itself
was not measured offline. Compare it with "No noise suppression" on the voice
test page.
