# Prototype completion and verification — 12 October 2026

## Implemented scope

The English-primary, workplace-training prototype retains its existing learner
layout, accounts, history, thirty English lessons and workplace/multi-AI filters.
It now has 42 activities: the existing 40 plus Company Knowledge and Email
Professionalism. Other full language curricula remain roadmap work, not finished
English-prototype features.

| Capability | Implementation and evidence |
|---|---|
| Per-attempt scenarios | Bounded, repeatable case variants with difficulty, weakest subskill and previous feedback. Not unlimited generative scenarios. Exact preview is atomically consumed and saved; later catalog edits cannot change an existing session. |
| Organization RAG | Explicit selected-document retrieval, ready-document and organization authorization, cited excerpts in chat/transcript, separate policy practice objectives and source-grounded prompts. Required-policy lessons reject missing documents. Revoked documents cannot start or continue an attempt. |
| Optional posture | Lesson-level capability, learner opt-in, camera permission, local MediaPipe worker and four visible-body indicators. No-body/unavailable states are reported. Visual indicators and sample counts are separate from language proficiency. |
| Workplace coverage | Communication, active listening, conflict resolution, negotiation (including anchoring/counteroffers/concessions/objections), interviews, presentations, storytelling, critical thinking, responsible AI, social engineering, email and company policy. |
| Training flow | Single/multi-AI participant metadata and four turn modes preserved. End Session cancels rather than awarding completion and remains available during generation. Speech settings are reachable in-session. |
| English learning | Individual lesson personas, models, corrections, target observations and beginner native-language captions retained. Distinct-response minimum is now 3/4/5 by level, removing needless extra turns after simple greetings are demonstrated. Repeated identical replies cannot complete a lesson. |
| Assessments/plans | Evidence-linked prototype scores, automatic successful completion, saved results, proficiency history, next-lesson recommendations and adaptive plans. Unsuccessful practice continues; cancellation awards no mastery. |
| Speech robustness | Incremental capture retained; speech text is published before synthesis; speaking status is not masked by generation. Synchronous duplicate-send guard, request cancellation, guarded microphone restarts, bounded caption/evaluation waits and real transcript timestamps. |
| Administration | Authorized lesson knowledge/posture settings plus existing catalog/scenario configuration. Custom case context and success criteria are retained rather than replaced by seeded workplace cases. |

## Verification

- 69 backend regression tests pass, including new preview consumption,
  immutable snapshots, document availability, posture gating and completion tests.
- 3 incremental-transcription tests pass; production frontend build passes.
- Actual localhost application, not an acceptance fixture: isolated QA login,
  retained filters, English briefing, single-AI full-window layout, Urdu beginner
  captions, responsive chat/progress and safe cancellation inspected in browser.
- Final real-browser First Greetings attempt automatically completed after three
  distinct responses, displayed evidence-linked assessment and returned to the
  persisted dashboard. The walkthrough also identified identity inconsistency,
  identical-phrase corrections and unsupported audio advice; guards were added.
- Multiple-AI grid and presentation posture opt-in inspected in the real browser.
  Configuration changes now preserve the prepared case rather than cycling it.
- `prototype-live-completion-2026-10-12.png` shows the isolated QA dashboard's
  saved First Greetings result and Introduce Yourself recommendation; these are
  test-account results, not the user's performance.
- `scripts/verify_live_prototype.py` checks the real running routes and configured
  models: selected policy documents, varying briefs, premature-completion rejection,
  successful assessment persistence, posture configuration/cancellation, and
  synthesized ChatTTS speech recognized correctly by Whisper medium CUDA.
- Speech round-trip result: “Hello, my name is Alex. Nice to meet you.”
- Health: ChatTTS modules on RTX 5060 CUDA; Whisper medium CUDA int8_float16;
  schema 7; no reported component errors. Existing speech selection is unchanged.
- QA records and synthetic policy document are deliberately isolated under
  `prototype-qa-20261012@example.invalid` / `Prototype Acceptance QA`. No existing
  learner records or organization documents were deleted.

## Honest validation limits

This is implemented prototype scope, not production or educational certification.
Real-user microphone/noise accuracy, physical webcam capture/landmarks, long-call
audio quality, barge-in, load capacity, browser coverage and learning gains require
device/user trials. Generated speech recognition is not a microphone test.
Posture indicators are presentation proxies, not medical assessments. Pattern-based
objective checks are transparent heuristic observations, not semantic policy
certification or calibrated English proficiency. The LLM may still make mistakes;
source excerpts and corrections must remain inspectable.

Run: `.venv\Scripts\python.exe run_hikari.py`, then http://localhost:8000.
