# Prototype implementation and acceptance — 10 October 2026

## Completed learner behavior

- Existing learner screens, full-window calls, voice/chat modes, language tags, workplace lessons and multi-AI activity metadata remain intact.
- Lesson-specific objective observations contain learner transcript evidence. Repeated identical replies do not count as distinct meaningful responses; unrelated workplace speech cannot satisfy scenario objectives merely by reaching a word count.
- Premature completion returns actionable guidance and leaves the session active. Leaving cancels the session without awarding proficiency. Successful objective demonstration triggers assessment and saved progress.
- Guided fallback advances greetings into wellbeing, polite closing and fresh transfer practice. It no longer treats “I am doing well” as a person's name or applies a workplace-action persona to language training.
- English plans recommend the next unfinished qualifying lesson; roadmap/start buttons pass the exact activity ID. Uncompleted roadmap steps are not marked completed just because their skill has prior sessions.
- Assessment uses explicit rubric observations, rejects invalid/nonfinite AI score values and excludes fabricated correction quotes. Offline grammar/fluency are unavailable, not invented. Feedback encourages transfer without accusing correct learners of nonexistent mistakes.
- Chat does not invoke TTS. Voice-engine failure returns the AI's text response instead of hiding it. Timed-out model generation stops publishing late callback output. TTS warmup moves initial setup cost out of the first user response.
- First-use privacy notice explains local storage, external-provider transcript/document excerpts and optional local vision. It is a non-binding prototype disclosure, not a legal compliance certification.
- Administrator editors now provide fields, checkboxes and line-separated lists rather than requiring handwritten JSON. Roles still require explicit trusted administrator provisioning.

## Verification evidence

| Check | Result and limits |
| --- | --- |
| Regression/acceptance suite | 58 tests passed: auth, API, migrations, STT settings, TTS settings, concurrent assessment, domain lifecycle, custom catalogs, 30-lesson metadata, learning outcome negatives/positives, organization document sharing/isolation and upload authorization |
| Frontend production build | Passed; learner layout retained and form-based administrator changes compile |
| Concurrent common operations | 20 authenticated clients, 300 requests: p95 154.4 ms, maximum 222.1 ms, all under two seconds; isolated in-process HTTP, not simultaneous GPU voice capacity |
| Live generated-speech/STT smoke test | Final running app: selected Kokoro returned audio in 3.23 seconds; Whisper medium/CUDA transcribed “Hello, it is lovely to meet you. How are you today?” correctly in 594.8 ms, confidence 0.83. Earlier pre-warmup output took 4.38 seconds. Isolated bounded-thread synthesis measured 1.245 seconds, but the integrated result remains slower; neither measurement proves instantaneous end-to-end conversation |
| Learner UI walkthrough | Disposable localhost:8001 fixture: disclosure → dashboard → lesson briefing → single-AI session → chat → five distinct responses → automatic assessment → saved result and Introduce Yourself recommendation. No real account, microphone, camera or cloud AI was used for this fixture |
| Failure usability | Offline STT shows a clear call limitation; chat remains usable without TTS. Premature completion shows missing objectives in the session. Missing-TTS voice text is covered by an API regression test |
| Visual evidence | `prototype-acceptance.png` captures the isolated completed lesson/dashboard and next-lesson recommendation. Fixture scores are synthetic acceptance evidence, not user performance |

## Run and reproduce

From VoiceBot: `.venv\Scripts\python.exe run_hikari.py` starts the integrated application. Open http://localhost:8000. Preserve your existing `.env` and model selection.

Run `.venv\Scripts\python.exe -m unittest discover -s tests`, `npm run build` inside frontend, `.venv\Scripts\python.exe scripts\benchmark_common_operations.py`, and `.venv\Scripts\python.exe scripts\check_voice_latency.py` against the running app.

Optional UI fixture: `.venv\Scripts\python.exe scripts\preview_acceptance_fixture.py`, then localhost:8001. This deliberately unauthenticated synthetic fixture binds only to loopback, runs without models, and uses temporary storage. **Never deploy it or expose it to a network.** Stop with Ctrl+C to remove the fixture database.

## Remaining acceptance, not claims of completed validation

The implementation is suitable for prototype evaluation, not production certification. Physical microphone accuracy with the user's voice/noise, actual webcam landmarks, barge-in/audio quality, long-call behavior, non-Chromium browsers, adversarial security tests and measured educational gains need real-device/user trials. Automated tests and synthesized speech do not replace them. Heuristic rubric observations are not psychometrically calibrated or certified English proficiency. External-provider privacy/retention policies must be reviewed for the actual deployment.

The acceptance walkthrough used the computer-use skill to verify the preserved learner UI and uncovered/fixed chat-TTS coupling and the fallback greeting loop. No device permissions were granted by automation.
