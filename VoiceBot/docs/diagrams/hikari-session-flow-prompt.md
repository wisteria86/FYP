# Hikari session diagram — generation brief

Initial drafts used built-in image generation with the brief below. Those
drafts were rejected because connector arrows were ambiguous. The final PNG
and editable SVG are instead generated deterministically by
`render-session-flow.cjs`, using Sharp to rasterize the SVG. The source is based
on the current session, scenario, speech, assessment and training-orchestration
implementation, not proposed hosted mode. No application behavior is changed.

Create a polished, technically accurate pictorial architecture infographic as one high-resolution PNG, landscape 3840x2560 if possible. Title: "Hikari — Training Session Flow". Subtitle: "Current implementation • browser client + local Python backend". This is a project-report-ready diagram, not a screenshot, not a proposed cloud architecture. Warm ivory background, deep burgundy primary accents, muted teal for browser, navy for backend, purple for external LLM, amber for optional processes, green for success. Crisp legible English text, large flat illustrative icons in every card, ample spacing, clear arrowheads and clear loop arrows. No decorative people portraits or fake UI; use pictograms: learner, lesson book, role cards, microphone, waveform, server, document search, brain, speech speaker, checklist, camera, database and progress chart. Four horizontal numbered phases with a readable serpentine path, plus a narrow optional/parallel side rail. Carefully render these exact short labels; do not invent features.

PHASE 1 — PREPARE (left to right, cards 1–5):
1 "Sign in" / "Authenticate learner"
2 "Choose lesson" / "Skill • language • proficiency"
3 "Prepare scenario" / "Adapt to history and weak skills"
4 "Review briefing" / "Roles • objectives • AI participants"
5 "Create session" / "Freeze scenario snapshot • save opening"
Connect 1→2→3→4→5. Phase 1 card 5 leads to phase 2 card 6.

PHASE 2 — CAPTURE (left to right, cards 6–10):
6 "Join voice call" / "Play AI opening • request microphone"
7 "Prepare audio" / "Selected mic → gain → optional RNNoise"
8 "Capture learner speech" / "Manual: Stop & send" / "Automatic: Silero detects pause"
9 "Recognize speech" / "Nemotron live OR Whisper ONNX recorded"
10 "Validate transcript" / "Empty or uncertain? Retry" / "Valid? Submit learner turn"
Connect 6→7→8→9→10. Small clearly labeled retry loop from 10 to 8, and valid arrow from 10 to phase 3 card 11.
Small caption near 8: "Chat mode: typed text joins at step 11".
Small caption near 9: "Nemotron live recognition is optional; recorded audio is used when needed. No automatic Whisper fallback for explicit Nemotron."

PHASE 3 — CONVERSE (left to right, cards 11–15):
11 "Save learner turn" / "Apply ready review at turn boundary"
12 "Check progress" / "Objective evidence • local rules"
13 "Build roleplay context" / "Scenario • history • speaker role • optional RAG"
14 "Generate AI reply" / "External LLM • one selected speaker at a time"
15 "Deliver response" / "Filter reasoning → TTS → browser playback" / "Save reply • translate beginner captions when applicable"
Connect 11→12→13→14→15. Add one clearly connected purple background branch from 11/12 to a card "Background objective review" / "Meaning-based • exact learner quotes" and dotted return to 11 labeled "Apply at next turn boundary". Make clear that this review is parallel, not an extra mandatory synchronous step before every reply.
From 12 a thin green shortcut labeled "Already successful" bypasses 13/14 into 15 labeled "Closing reply". This reflects short-circuit closing rather than another LLM question.
At card15 label TTS "Kokoro / Piper / Kitten / ChatTTS". Small footnote: "Engine-specific buffering; selected speech engine is used."

PHASE 4 — RESOLVE (cards 16–19, left to right):
16 diamond "Objectives achieved?" with two branches.
NO branch, burgundy long loop arrow returning to 8, label "Continue targeted practice • next learner turn". Subcaption "In manual mode, learner starts recording; automatic mode resumes listening." IMPORTANT this must genuinely be a loop arrow, not just text.
YES branch →17 "Close naturally" / "Finish playback • stop capture" →18 "Assess and save" / "Transcript-grounded feedback • scores • optional posture" →19 "Update learning journey" / "History • skill progress • next activities".
Note at 16: "Completion uses saved semantic evidence when current; otherwise local rules. No word/turn quota."
Phase3 15 leads to16. Conceptual final assessment may be computed server-side alongside closing playback; do not imply feedback waits for a wholly new conversation step or a second generated closing. Card17 represents finishing the closing reply already delivered at15.
Bottom or side amber card "Optional posture" / "Camera → local landmarks → backend indicators" dashed into18. Amber card "Optional knowledge grounding" / "Authorized documents → retrieved passages" dashed into13. Label both "Lesson-controlled".
Bottom neutral card "Manual exit / disconnect" / "Release microphone • cancel active work" dashed branch from call loop, marked "Not a successful completion".
Thin footer rail "Runtime monitoring: input levels • recognition • LLM • TTS • queue/errors • CPU / GPU / RAM" with small gauge icons.

Legend: solid arrow = main flow, dashed arrow = optional / parallel; colors identify Browser, Backend, External LLM, Optional, Success. Ensure all arrows are nonambiguous, diagram remains readable at full resolution. Do not state that all models use GPU; do not include model weights, passwords, private files, made-up latency or a hosted deployment.
