# Scene engine (case packs)

All 46 seeded lessons have a case pack in `content/cases/` and use this engine (definition version 3). Saved older sessions and lessons created in the admin screen without a pack still use the runtime in `CONVERSATION_RUNTIME.md`. Most packs are generated from `scripts/case_authoring/` with `python -m scripts.case_authoring.build`, so edit those sources and rebuild.

Principle: code owns the scene; the model only performs the line.

| Part | File | Job |
|---|---|---|
| Case pack | `content/cases/*.json`, `intelligence/case_library.py` | Learner brief, character cards, fact ledger, stages (beats), expert notes, variants. Validated on load. |
| Scene Director | `intelligence/scene_director.py` | Reads the turn, tracks the stage and chooses one move and speaker. Checks each generated sentence. |
| Negotiation strategy | `intelligence/negotiation_strategy.py` | Decides positions in code. The model never receives a reservation limit. Binding terms are spoken exactly. |
| Prompt | `intelligence/dialogue_style.py` | Character card, real dialogue turns, and this turn's move. |
| Scoring and debrief | `services/assessment_service.py`, `finalize_scene` in `services/structured_orchestrator.py` | One final review, separate scores, a debrief whose quotes must be the learner's own words. |

## Behaviour worth knowing

- Confusion is about the learner, not scene content: rephrase or orient, then a smaller step, then the coach.
- Stages advance on provisional signals or when stalled, so a scene cannot loop. Signals only steer. Credit comes only from the evidence review.
- One AI speaks per learner turn unless a stage, an invitation or a name calls for another.
- If the model is unavailable or every sentence fails its checks, prepared lines keep the scene going. The notice says so, and prepared lines earn no extra credit.
- A learner can finish early and receives an honest partial score. Unfinished attempts count for less in proficiency (weight 0.15 rather than 0.35).

## Model choices (free tier)

Measured on 9 November 2026 with `scripts/conversation_eval/review_calibration.py`. The labels are the author's and need a qualified human reviewer.

| Role | Model | Evidence |
|---|---|---|
| Dialogue | `qwen/qwen3.8-27b` | Shorter, more natural lines than `gpt-oss-120b` on the same script. Small sample. |
| Evidence review | `qwen/qwen3.8-27b` | 11 of 12 correct, no false credit, one missed paraphrase. Both `gpt-oss` models wrongly failed the clear positive examples they reached. |
| Turn reading | Local rules | The optional model reader (`LLM_ROUTER_MODEL`) misread turns in live runs, so it is off by default. |

The provider rejected requests citing "tokens per minute: limit 1000" while its headers advertised 8,000, so bursts fall back to prepared lines. Reviews during a call wait for idle time for this reason. Space live test runs.

## Evaluating

```bash
python -m scripts.conversation_eval.baseline_from_db
```
```bash
python -m scripts.conversation_eval.run --cases english-28 --personas confused,strong --delay 20 --finish --output tmp/eval/run.json
```
```bash
python -m scripts.conversation_eval.review_calibration --delay 20
```
```bash
python scripts/conversation_eval/serve.py --port 8010
```

The last command is a chat-only server with a temporary database, for trying lessons in a browser.

The gates catch observable failures such as invented figures, leaked limits, ignored confusion and repetition. They do not measure naturalness or learning: in live runs, transcripts passed every gate and still had real problems. Read the transcripts. High language scores on scripted learners have not been calibrated against human raters.

## Adding a case

Add a lesson to `scripts/case_authoring/` and rebuild, or write a file in `content/cases/`. The validator rejects generic goals, stage directions in facts, limits readable in facts, and objectives with no stage or expert note. `tests/test_scene_engine.py` then covers it automatically, including whether a strong learner can reach the end.

## Admin access

The admin screen appears only for accounts listed in `.env`, for example `ADMIN_EMAILS=you@example.com`. Restart Hikari after changing it.

## Evaluation with people

See `EVALUATION_PROTOCOL.md`.
