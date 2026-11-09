"""Run scripted learners through the real engine and report the gates.

    python -m scripts.conversation_eval.run --cases english-28 --personas confused,strong --delay 16 --output tmp/eval/run.json

Live runs spend real provider quota. Use --delay to stay under the per-minute limit.
"""
import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from api.schemas import RoleplayTurn
from core.training_service import TrainingService
from scripts.conversation_eval.metrics import evaluate, failed_gates, summarise
from scripts.conversation_eval.personas import STRONG, lines_for
from services.structured_orchestrator import BACKGROUND, cancel_scheduled_review, finalize_scene
from services.training_orchestrator import TrainingOrchestrator

SKILLS = {'activity-negotiation': 'negotiation', 'activity-presentations': 'presentations', 'activity-company-knowledge': 'company-knowledge', 'activity-ai-literacy': 'ai-literacy', 'activity-communication': 'communication', 'activity-public-speaking': 'public-speaking', 'activity-customer-communication': 'customer-communication', 'activity-concise-communication': 'concise-communication', 'activity-barter': 'barter'}


SAMPLE_POLICY = ('Annual leave policy. Employees must request annual leave at least 10 working days in advance using the HR portal. '
                 'A line manager must approve the request before travel is booked. Requests made with less notice need written approval from the department head. '
                 'Unused leave of up to 5 days may be carried into the next year.')


def private_numbers(definition):
    values = []
    case = definition.get('negotiation')
    if case:
        values += [case['seller']['minimum'], case['buyer']['maximum'], case['buyer']['target']]
    return values


async def run_case(provider, activity, persona, delay=0, training=None, on_turn=None, variant=None):
    """Return (transcript, result, session id). Accepts a provider or None for offline."""
    folder = None
    if training is None:
        folder = tempfile.TemporaryDirectory()
        training = TrainingService(Path(folder.name) / 'eval.db')
    try:
        documents = None
        if activity == 'activity-company-knowledge':
            documents = [training.add_document('demo', 'Annual Leave Policy', SAMPLE_POLICY)['id']]
        skill = activity.removeprefix('activity-') if activity.startswith('activity-') else 'english-speaking'
        session = training.create_session('demo', skill, 'intermediate', activity, document_ids=documents)
        sid = session['id']
        runner = TrainingOrchestrator(training, provider, None, Mock(), 24000, 'none')
        runtime = training.context.runtime
        definition, _ = runtime.read(sid)
        transcript = [{'role': 'ai', 'speaker': session['counterpart'], 'text': session['turns'][0]['text'], 'move': 'opening', 'authorised': True}]
        latencies = []
        # Without a written script, a strong learner says each objective's example answer.
        script = lines_for(activity, persona) if persona != 'strong' or activity in STRONG else [o['alternatives'][0] for o in definition['objectives']]
        for line in script:
            started = time.perf_counter()
            result = await runner.run_turn(sid, RoleplayTurn(text=line, synthesize_audio=False))
            latencies.append(round((time.perf_counter() - started) * 1000))
            cancel_scheduled_review(training, sid)
            transcript.append({'role': 'learner', 'speaker': 'You', 'text': line})
            for reply in result['responses']:
                transcript.append({'role': 'ai', 'speaker': reply['speaker'], 'text': reply['text'], 'move': reply.get('move'), 'mode': reply.get('response_mode')})
            if on_turn:
                on_turn(line, result['responses'])
            if delay:
                await asyncio.sleep(delay)
        people = [p['name'] for p in definition['participants'] if p['kind'] == 'ai']
        private = private_numbers(definition)
        heard = [f['text'] for f in definition.get('ledger', [])] if definition.get('version') == 3 else definition['facts']
        # Figures chosen by the bargaining strategy are authorised, not invented.
        for turn in transcript:
            if turn.get('move') == 'bargain':
                turn['authorised'] = True
        metrics = evaluate(transcript, known_facts=heard, private_numbers=private, ai_names=people)
        metrics['latency_ms_median'] = sorted(latencies)[len(latencies) // 2] if latencies else None
        metrics['scripted_lines'] = sum(t.get('mode') == 'scripted' for t in transcript)
        return transcript, metrics, sid
    finally:
        if folder:
            pending = list(BACKGROUND)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            training = None
            try:
                folder.cleanup()
            except OSError:
                pass


async def main(cases, personas, delay, output, dialogue_model=None, finish=False):
    from config import Config
    from integrations.conversation import ConversationAdapter
    from modules.llm_brain import LLMBrain
    brain = LLMBrain(Config.LLM_API_KEY, dialogue_model or Config.LLM_MODEL_NAME, Config.LLM_BASE_URL, Config.LLM_ROUTER_MODEL, Config.LLM_REVIEW_MODEL)
    provider = ConversationAdapter(brain)
    report = []
    for activity in cases:
        for persona in personas:
            before = brain.estimated_tokens
            def show(line, replies):
                print('  You:', line, flush=True)
                for reply in replies:
                    print(f"  {reply['speaker']} [{reply.get('move')}/{reply.get('response_mode')}]: {reply['text']}", flush=True)
            print(f'== {activity} / {persona}', flush=True)
            with tempfile.TemporaryDirectory() as folder:
                training = TrainingService(Path(folder) / 'eval.db')
                transcript, metrics, sid = await run_case(provider, activity, persona, delay, training=training, on_turn=show)
                if finish:
                    assessment = await finalize_scene(training, provider, sid)
                    metrics['assessment'] = {key: assessment[key] for key in ('overall', 'scores', 'strengths', 'improvements', 'feedback')}
                    print('  Assessment:', json.dumps(metrics['assessment'], ensure_ascii=False), flush=True)
                pending = list(BACKGROUND)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
            metrics['estimated_tokens'] = brain.estimated_tokens - before
            failed = failed_gates(metrics)
            print('  gates failed:', ', '.join(failed) or 'none', '| est. tokens', metrics['estimated_tokens'], flush=True)
            report.append({'activity': activity, 'persona': persona, 'failed': failed, **metrics, 'transcript': transcript})
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps({'model': brain.model_name, 'summary': summarise(report), 'runs': report}, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summarise(report), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', default='english-01,english-19,english-28,activity-negotiation')
    parser.add_argument('--personas', default='confused,strong')
    parser.add_argument('--delay', type=float, default=16)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dialogue-model')
    parser.add_argument('--finish', action='store_true', help='Also run the final review, scoring and debrief')
    args = parser.parse_args()
    asyncio.run(main(args.cases.split(','), args.personas.split(','), args.delay, args.output, args.dialogue_model, args.finish))
