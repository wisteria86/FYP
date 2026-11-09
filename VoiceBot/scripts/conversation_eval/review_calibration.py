"""Check the evidence reviewer against hand-labelled learner lines (requirement L2).

    python -m scripts.conversation_eval.review_calibration --models qwen/qwen3.8-27b,openai/gpt-oss-120b

Labels are the author's judgement and need a qualified human reviewer. This selects a
model and catches regressions; it does not validate assessment.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from config import Config
from core.training_service import TrainingService
from modules.llm_brain import LLMBrain

# (label, learner lines, objective id, expected)
CASES = [
    ('direct', ["I'm so sorry this has happened twice. I can see why you're frustrated."], 'o1', True),
    ('paraphrase', ['Twice now? And no callback either? Honestly, I would be fed up as well.'], 'o1', True),
    ('imperfect English', ['I am sorry, this is second time late, must be very annoying for you.'], 'o1', True),
    ('stock phrase only', ['We apologise for any inconvenience caused.'], 'o1', False),
    ('negation', ["I don't really care how you feel about it, that's not my department."], 'o1', False),
    ('keyword-rich but irrelevant', ['Frustration and sorry and understand are all words my teacher told me to use today.'], 'o1', False),
    ('real question', ['What date do you actually need it by, and what is it for?'], 'o2', True),
    ('paraphrased question', ['Help me out here: is there a particular day this has to be with you?'], 'o2', True),
    ('promise to ask', ['I will ask you some questions about your needs later on.'], 'o2', False),
    ('concrete action', ["I'll send it by express today and call you tomorrow by noon with the tracking number."], 'o3', True),
    ('vague promise', ["We'll look into it and someone will get back to you soon."], 'o3', False),
    ('mentions a solution only', ['A solution would be nice, solutions are important, next steps matter.'], 'o3', False),
]


def run(model, delay=0):
    brain = LLMBrain(Config.LLM_API_KEY, Config.LLM_MODEL_NAME, Config.LLM_BASE_URL, Config.LLM_ROUTER_MODEL, model)
    results = []
    with tempfile.TemporaryDirectory() as folder:
        training = TrainingService(Path(folder) / 'calibration.db')
        runtime = training.context.runtime
        for label, lines, objective, expected in CASES:
            session = training.create_session('demo', 'english-speaking', 'intermediate', 'english-19')
            sid = session['id']
            for index, line in enumerate(lines):
                generation, _ = runtime.start(sid, SimpleNamespace(text=line, duration_seconds=0, request_id=f'r{index}', expected_revision=None, addressed_participant_ids=[], recognition={}))
                speaker = runtime.speakers(sid)[0]
                uid = runtime.create_utterance(sid, generation, speaker)
                runtime.sentence(sid, uid, 'Go on.', False)
                runtime.finish(sid, generation, {})
            started = time.perf_counter()
            outcome = None
            for _ in range(6):
                try:
                    reply = brain.evaluate_runtime(runtime.evaluation_context(sid))
                    runtime.save_evaluation(sid, runtime.read(sid)[1]['evidence_revision'], reply)
                    progress = {c['id']: c['met'] for c in runtime.progress(sid)['criteria']}
                    outcome = progress[objective]
                    break
                except Exception as exc:
                    # A rate limit says nothing about judgement quality, so wait and retry.
                    if getattr(exc, 'status_code', None) != 429:
                        outcome = f'error: {type(exc).__name__}'
                        break
                    time.sleep(min(90, getattr(exc, 'retry_after', 30) + 2))
                    outcome = 'error: rate limited'
            results.append({'label': label, 'expected': expected, 'outcome': outcome, 'correct': outcome == expected, 'seconds': round(time.perf_counter() - started, 1)})
            print(f"  {'ok ' if outcome == expected else 'NO '} {label}: expected {expected}, got {outcome}", flush=True)
            if delay:
                time.sleep(delay)
    correct = sum(r['correct'] for r in results)
    false_credit = sum(r['outcome'] is True and r['expected'] is False for r in results)
    missed = sum(r['outcome'] is False and r['expected'] is True for r in results)
    return {'model': model, 'correct': correct, 'total': len(results), 'false_credit': false_credit, 'missed_credit': missed,
            'errors': sum(str(r['outcome']).startswith('error') for r in results), 'results': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', default=Config.LLM_REVIEW_MODEL)
    parser.add_argument('--delay', type=float, default=8)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = []
    for name in args.models.split(','):
        print('==', name, flush=True)
        outcome = run(name, args.delay)
        report.append(outcome)
        print(f"  {outcome['correct']}/{outcome['total']} correct, false credit {outcome['false_credit']}, missed credit {outcome['missed_credit']}, errors {outcome['errors']}", flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
