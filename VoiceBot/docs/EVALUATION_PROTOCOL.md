# Evaluation protocol

These are the human steps that the software cannot do. The tools are in `scripts/evaluation/tools.py`. Check whether your university requires ethics approval before you start with learners.

## 1. Device checks (one person, about an hour)

Use `docs/RUNTIME_HUMAN_ACCEPTANCE.md`. To check the speech models without a microphone, start the full evaluation server on a copy of your data, then run the voice check in a second terminal:

```bash
.venv\Scripts\python.exe scripts\conversation_eval\serve.py --port 8000 --full
```
```bash
.venv\Scripts\python.exe -m scripts.conversation_eval.check_voice_stack --register
```

Record the machine, browser, microphone, speech engines, and median and 95th percentile latency.

## 2. Expert rating of assessment

1. Collect at least 30 objective judgements, across several lessons and learners.
2. Export them. The file uses random codes and hides the system's judgements:
   ```bash
   python -m scripts.evaluation.tools export --database data/hikari.db --output tmp/eval/raters.csv
   ```
3. Two qualified raters separately fill `rater_a` and `rater_b` with `met` or `not_met`, using the `what_counts` column. They must not discuss items first. Save the result as `tmp/eval/raters-filled.csv`.
4. Compare:
   ```bash
   python -m scripts.evaluation.tools agree --ratings tmp/eval/raters-filled.csv --key tmp/eval/raters.key.json
   ```
5. Review every item in `raters_agree_system_differs`, and use those to improve the rubrics. Report the number of items with any kappa value.

## 3. Learner study (a small pilot is fine)

For each consenting learner:

| Step | What happens |
|---|---|
| Consent | Read the text below and sign. |
| Pre-test | One lesson with no coach. |
| Practice | Two or three sessions, using the coach freely. |
| Post-test | A new case of the same lesson with no coach. Hikari records the variant used. |
| Transfer | A related lesson they have not practised. |
| Delayed test | Use the 7-day review from the Learning Path. |
| Survey | How useful was the feedback? Did the conversation feel realistic? What was confusing? |

Summarize with:

```bash
python -m scripts.evaluation.tools learners --database data/hikari.db --output tmp/eval/learners.json
```

Enjoyment and completion counts do not show that learning occurred (P12). Without a comparison group, report results as a pilot and not as proof of effectiveness.

## 4. Claims to avoid

- No CEFR level or certified proficiency.
- No claim about pronunciation, accent, confidence, emotion or personality.
- No use of scores for hiring or appraisal.
- Report negative findings too.

## Consent text (adapt as required)

> You are invited to try Hikari, a student project that uses AI roleplay for workplace skills. Your conversations are stored on the project computer, and the text of what you say or type is sent to an external AI provider to generate replies. Please do not share real personal, customer or company information. The microphone is used only if you choose voice, and the camera is optional and analysed on your device. Your results will be reported only in anonymous form, under a random code. Scores are prototype estimates and do not measure your ability or your job performance. You may stop at any time, without giving a reason, and ask for your data to be deleted. Contact: [name and email].
