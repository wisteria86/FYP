# Conversation runtime v2

Newly prepared lessons use persistent participant identities, an immutable scenario definition, an event log, delivered-speech records, and evidence-based evaluation. Historical sessions without a v2 definition continue through the compatibility runtime. Restart the backend after updating; the launcher serves the rebuilt frontend.

## Runtime behavior

- The prepared roster is the identity source for openings, labels, routing and prompts. A learner introduction updates only the learner identity.
- Public briefing responses exclude counterpart private constraints. Character prompts contain only that character's private knowledge. Learner preparation stays outside character prompts.
- A local conversation director prioritizes explicit participant selection, natural vocatives (including punctuation-free “Okay Sam”), requests for another participant, authored action ownership, persistent conversational focus and topic ownership. A name mentioned in the third person is not automatically an addressee. Duplicate names require role clarification. Collective invitations can include two participants even when both have already spoken. Speaker selection does not require an extra model call or turn-count rotation.
- Character speech uses recent delivered dialogue, relevant older quotations, attributed memory and binding facts. Attributed learner claims do not rewrite scenario facts.
- Chat text is delivered immediately. Voice sentences carry event, revision, participant, utterance and segment identifiers. The browser acknowledges completed playback; an interruption invalidates queued speech and pending acknowledgments. An interrupted sentence is conservatively excluded when it was not fully delivered.
- The microphone interruption monitor requires browser echo cancellation and sustained Silero speech probability. It rotates idle in-memory recordings and preserves the current recording's container header during playback and interruption. The Interrupt button works without automatic detection. AI speech is serialized. A second character's draft can be prepared during playback, but it stays outside shared state and is discarded unless the predecessor is acknowledged. Interruptions invalidate that draft.
- Named questions between characters trigger a brief answer without another learner submission. After substantive contributions, relevant or quiet colleagues can keep joining the exchange, including after they have already spoken. Topic relevance guides the choice, but cannot permanently exclude a quieter specialist. Personal questions and communication repair remain focused; explicitly requested speakers keep their place. Exchanges remain bounded at two AI contributions before yielding. Replies are capped at two generated sentences; near-duplicate speech is suppressed with a focused clarification instead of a fake provider error.
- The provider receives an explicit selected-speaker reminder after the history. Streaming checks correct self-address, cross-person action claims, and assertions of explicitly unknown quantities. These checks are bounded safeguards, not proof that every possible semantic mistake is detected.
- Evidence review, factual checking and optional translated captions share one background provider call, deferred until 12 seconds of quiet and spaced at least 60 seconds apart per provider. Captions appear after review and never delay first speech. Failed or rate-limited dialogue calls retain the learner turn and show a retry notice outside character speech. Retrying that response reuses the original learner turn. Failures cannot fabricate completion or language scores.
- The coach is separate from the characters. Help escalates from a hint to a model, a smaller task, and an exit choice. Assistance is recorded against actual learner turns.
- Success remains active until the learner chooses the debrief. Extra practice, pausing and leaving retain demonstrated achievement. Transcript correction invalidates affected evidence; original text is retained.
- Negotiation cases include private preparation, feasible multi-issue packages, approval authority, a conditional offer ledger and a no-ZOPA variant. Complete numeric spoken offers can enter the ledger through validated source quotations; partial/ambiguous offers use the editable package controls. Confirmation is checked against the ledger, never inferred from a vague yes.
- Reviews appear in the training plan at 1, 7 and 30 days. Completing a linked fresh case records transfer or delayed retention according to its due date. These intervals are product defaults, not validated learning prescriptions.

## Interfaces and storage

Migration `0008_conversation_runtime.sql` adds state, events, requests, utterances and review scheduling, plus transcript provenance. Existing sessions and assessments are preserved. Do not downgrade the application against a migrated database.

Existing `/turn` and `/voice-stream` routes use the new runtime when a session has a v2 definition. Turn requests accept `request_id`, optional `expected_revision`, `addressed_participant_ids` and recognition provenance. Retried completed request IDs return the saved result; in-progress or stale requests return 409.

The authenticated `/api/chat` compatibility adapter accepts `session_id` and the same turn fields. Without an ID it starts a private first-greetings lesson; clients must retain the returned `session_id` for continuity. Existing generic clients must supply their authentication cookie (or use the existing explicitly enabled local demo mode).

New owner-authorized routes under `/api/sessions/{id}`:

| Route | Purpose |
|---|---|
| `GET /runtime` | Learner-safe state and rubric progress |
| `GET /events` | SSE event stream; supports `after` and `Last-Event-ID` |
| `POST /actions` | Interrupt, pause/resume, coach, correction, preferences, reflection, private preparation and ledger actions |
| `POST /playback` | Acknowledge an utterance segment |
| `DELETE /conversation-data` | Remove transcript, runtime memory and source evidence while retaining a minimal history record |

Structured scenario JSON can be supplied in the administrator scenario editor. IDs and roster cardinality are validated; saved definitions affect future sessions. Unknown legacy private facts are never reconstructed.

Generated v2 negotiation cases with contradictory legacy role labels receive a read-time role correction only when their existing private constraints establish the buyer/seller side. Prices, limits and history are preserved. New group planning cases include a concrete workshop brief and distinct responsibilities; start a fresh lesson to use that brief.

New “Resolve Team Conflict” sessions contain a fixed plan change, two distinct concerns, ID-bound ownership of the change, and explicitly unknown timing. Sam made the change; Alex wants notice and joint approval. The reason is a missing end-to-end test, not an improvised security patch. Existing sessions retain their facts; an original opening explicitly saying Sam changed the plan can restore that ownership, but cannot supply a missing reason, duration or deadline. Start a new conflict lesson for the complete brief. Administrator definitions can use `actions` and `unknown_quantities`; quantity checks permit clearly labelled proposals while rejecting unsupported assertions.

Lesson support opens in an accessible side drawer. The conversation, transcript and call controls retain their layout. Provider retry notices are separate from coach and character messages. `retry_last_turn: true` is accepted only for the matching failed latest learner turn.

Saved lessons appear in Home's “Continue learning” section, with lesson titles, skills, levels, start dates and individual resume controls. The initial view shows three rows; the rest expand into a bounded scrolling list. They no longer form a global banner above unrelated pages. Resume disables duplicate clicks and reports failures inside the section. Desktop, narrow layout, expansion and resume were checked in an isolated browser session; screenshot: `tmp/runtime-tests/saved-lessons-redesign.jpg`.

## Requirement traceability

Automated tests establish runtime behavior and evidence integrity. They do **not** establish teaching effectiveness, translation quality, accent fairness or educational calibration.

Implementation and automated coverage links for the requirement groups below:

| Requirements | Implementation | Automated coverage |
|---|---|---|
| L1, L7, N1–N5 | [Scenario contracts](../intelligence/scenario_contracts.py), [typed records](../domain/conversation.py), [administrator validation](../services/administration_service.py) | [Runtime cases](../tests/test_conversation_runtime.py): roster, private projection, malformed definitions, numeric feasibility |
| L2–L6, L9–L12, P5–P9, P12 | [Evidence, support and review state](../services/conversation_runtime.py), [assessment](../services/assessment_service.py), [provider contract](../modules/llm_brain.py) | [Runtime cases](../tests/test_conversation_runtime.py): source quotes, revisions, recognition, support, completion preservation, review scheduling; [API cases](../tests/test_conversation_api.py): debrief choice |
| L8, P1–P4, P10–P11 | [Character orchestration](../services/structured_orchestrator.py), [coach interface](../frontend/src/ConversationCoach.jsx), [runtime API](../api/routers/conversation.py) | [Runtime/API cases](../tests/test_conversation_api.py); [playback state](../frontend/src/conversationPlayback.test.mjs), [interruption recording](../frontend/src/bargeIn.test.mjs); Urdu caption binding in [runtime cases](../tests/test_conversation_runtime.py) |
| N6–N12 | [Offer ledger and authority checks](../services/conversation_runtime.py), [negotiation rubrics](../intelligence/scenario_contracts.py), [semantic business assessment contract](../modules/llm_brain.py) | [Runtime cases](../tests/test_conversation_runtime.py): conditional terms, unauthorized approval, feasible acceptance, no-ZOPA rejection, justified no-deal and group contributions |

The tests with a mocked semantic evaluator check evidence integrity and state transitions, not whether a real model judges every utterance correctly. Historical-session suites explicitly use the compatibility fixture; the new runtime suites exercise v2. Human work is recorded in the [acceptance worksheet](RUNTIME_HUMAN_ACCEPTANCE.md).

| Requirement | Implementation | Verification / remaining human check |
|---|---|---|
| L1 | Versioned objectives, evidence descriptions, prerequisites and alternatives | Scenario validation tests; review all lesson-specific rubrics with an educator |
| L2 | Semantic judgment with exact source quotes and revision checks; no v2 keyword completion | Runtime evidence and keyword-negative tests; live paraphrase/negation rating pending |
| L3 | Separate task, comprehension, grammar, vocabulary and interaction evidence | Dimension validation; pronunciation omitted; human rating pending |
| L4 | Coach ladder, support provenance, independent fresh replies and linked transfer cases | Support and retained-completion tests |
| L5 | At most one source-quoted correction; selectable timing and a meaning-preservation instruction | Source/identity guards implemented; correction usefulness and meaning preservation require human review |
| L6 | Clarification/repair instructions and scenario objectives | Context tests; conversational repair corpus review pending |
| L7 | Roles, relationships, stable identities and bounded settings | Roster/routing/privacy tests; register and cultural review pending |
| L8 | English dialogue, optional Urdu coach help and captions | UI language controls; Urdu quality is not yet human validated |
| L9 | Original/corrected transcripts and unreliable-recognition provenance | Correction and unreliable-evidence tests; browser correction verified |
| L10 | No text-derived pronunciation or accent score | Assessor contract; no audio pronunciation feature introduced |
| L11 | Linked fresh cases and 1/7/30-day reviews | Review scheduling tests; actual delayed-learning study pending |
| L12 | Practice-evidence labels; no CEFR certification | UI copy and assessor contract |
| P1 | Respectful character instructions and lightweight harmful-text guard | Guard checks; challenging-conversation human review pending |
| P2 | Goals via lesson selection, challenge, correction, captions, manual/automatic speech, pause/exit | API controls and browser interaction |
| P3 | Learner-adjustable challenge, evidence-informed recommendations, existing one-to-one/group progression | Runtime preferences and existing planning tests |
| P4 | Short character replies, one question, optional separate coach panel | UI and prompt contract; cognitive-load user study pending |
| P5 | Quoted demonstrated behaviors replace ungrounded assessment praise | Evidence validation tests |
| P6 | Evidence-based strengths, reflection and later performance categories | Assessment evidence; longitudinal usefulness review pending |
| P7 | Optional saved reflection and debrief evidence | Reflection API/UI |
| P8 | Escalating hints/models/subtasks after repeated difficulty | Support ladder tests; retry/pause/skip/exit controls |
| P9 | One completion decision; natural closure and optional continuation | Completion, pause/restart and debrief API tests |
| P10 | AI disclosure and adjustable confrontation intensity | UI controls and role-scoped prompts |
| P11 | Optional camera, no personality inference, data disclosure and deletion | Owner-isolation/deletion tests; accessibility/device review pending |
| P12 | Independent/transfer/retention categories, evidence and reviewer worksheet | Instrumentation delivered; qualified-rater study pending |
| N1 | Private target, alternative, walk-away and rationale | Private projection and preparation validation |
| N2 | Discovery objectives and semantic evidence | Scenario rubric; expert negotiation rating pending |
| N3 | Frozen numeric case, currencies, units and feasibility constraints | Feasible/infeasible offer tests |
| N4 | Supplied fictional benchmark and offer rationale | Ledger validation; unsupported real-world claims excluded by assessor |
| N5 | Price, lead time, seats and support packages with cost trade-offs | Multi-issue feasibility cases |
| N6 | Conditional terms, requested return, proposed/countered/accepted/withdrawn status | Ledger transition tests; conditional proposals cannot auto-finalize |
| N7 | Role-scoped interests and authority; validated acceptance/rejection/clarification | Runtime/ledger tests; longer live conversations pending |
| N8 | Ethics rubric, confidentiality and transparent simulation intensity | Private-context tests; difficult-tactics rating pending |
| N9 | Distinct roles, selected speaker, approval owner and bounded group exchanges | Direct-address and privacy tests; live group acceptance pending |
| N10 | Explicit executable package and confirmation | Ledger and completion tests |
| N11 | No-ZOPA variant; justified no-deal can complete learning | Infeasible-deal rejection and no-deal evaluation fixture |
| N12 | Business dimensions separated from language, ledger-backed evidence and transfer | Assessment contract; expert utility calibration pending |

## Verification on 8 November 2026

### Follow-up: Alex/Sam meeting flow

- Ongoing group contribution replay: `scripts/replay_conversation_regressions.py --live --proactive --delay 28` exercised five learner turns across the conflict and workshop cases without naming any participant. Every turn received contributions from both AI participants, including direct exchanges between colleagues, with no service failures. Recorded in `tmp/runtime-tests/proactive-group-replay.json`. This checks text behavior, not physical audio latency or educational validity.
- Final backend suite: **207 passing** in 71.263 seconds (`tmp/runtime-tests/meeting-backend-results.txt`). An earlier run hit the known Windows rename error in the existing speech-package fixture; all seven tests in that module passed on isolated retry, followed by this clean full run.
- Added `tests/test_meeting_flow.py` for conversational vocatives, third-person mentions, manual overrides, focus after resume, duplicate names, action ownership, unknown quantities, repeated speech, spontaneous reactions, colleague-directed questions, collective invitations, provider identity enforcement, and interruption-safe prefetch.
- Replayed the 15-turn reported conflict exchange with the configured provider. Both Alex and Sam contributed; direct questions to Sam were answered by Sam, and questions about the plan change stayed with its owner. The final run completed without service failures. Report: `tmp/runtime-tests/meeting-dialogue-replay.json`.
- Earlier live runs exposed an invented test duration and a self-address error. The quantity guard and final selected-speaker reminder address these. The final replay also exposed a repeated fallback clarification; an additional deterministic regression now verifies three distinct clarification attempts. The live report predates that last fallback-only adjustment.
- Replies used the authored uncertainty instead of asserting a security patch, migration risk or unchanged delivery deadline. Text response timing excludes recognition, speech synthesis, playback and physical interruption; it is not an audio-latency result. A deliberately rapid earlier replay hit the provider quota; the successful replay used an 18-second interval between learner submissions.
- Frontend state tests remain 42 passing and the production build passes. Physical headset/speaker acceptance and human judgments of conversational naturalness remain required.

### Earlier runtime acceptance

- Full automated backend suite after the reported-dialogue repairs: **191 passing** (69.399 seconds), recorded locally in `tmp/runtime-tests/backend-results.txt`.
- Frontend tests: 42 passing. Production build passes.
- Browser: checked the desktop and narrow layout, drawer opening/closing, preserved controls, supplier identity, and outage retry without a duplicate learner turn. Screenshot: `tmp/runtime-tests/repaired-lesson-ui.jpg`. Voice engines were disabled in this isolated UI check.
- Reported dialogue replay: **13 turns completed without service failure**, with both Alex and Maya contributing, correct supplier identity, and clarification of incomplete/ambiguous answers. Run `python scripts/replay_conversation_regressions.py --live --delay 1`; it uses fictional cases and the configured provider. Bounded identity/package replies are generated locally; other turns use the provider. The report records that distinction in `tmp/runtime-tests/reported-dialogue-replay.json`. Assessment is intentionally excluded from this replay; these results do not establish live learning judgment quality or audio latency.
- Regression coverage in `tests/test_conversation_repairs.py` includes buyer/seller consistency, saved-case projection, other-person routing, provider retry, playback waits beyond ten seconds, local speaker selection, repeated questions, review coalescing, the reported Urdu mistranslation, unfinished conditions and ambiguous agreement.
- Physical headset/laptop-speaker interruption tests and qualified English/Urdu reviews remain outstanding. Do not describe this implementation as educationally validated or release-certified.

For Windows sandboxed testing, set `TEMP` and `TMP` to a workspace-local directory. Windows asyncio also requires local loopback access. Tests never need microphone models or external provider access unless the live check is explicitly selected.
