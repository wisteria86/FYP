"""Opt-in live-provider smoke check. Sends fictional test dialogue only; no microphone.

Run with --live to use the configured provider. Results are observations, not
educational validation. The disposable database lives under tmp/runtime-tests.
"""
import argparse
import asyncio
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config
from core.training_service import TrainingService
from modules.llm_brain import LLMBrain
from integrations.conversation import ConversationAdapter
from services.training_orchestrator import TrainingOrchestrator
from services.structured_orchestrator import BACKGROUND
from api.schemas import RoleplayTurn


async def run():
    provider=ConversationAdapter(LLMBrain(Config.LLM_API_KEY,Config.LLM_MODEL_NAME,Config.LLM_BASE_URL))
    directory=ROOT/'tmp'/'runtime-tests';directory.mkdir(parents=True,exist_ok=True)
    report=[]
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        training=TrainingService(Path(temporary)/'live.db')
        for activity,lines in [('english-01',['Hello, call me Amina. It is a pleasure to meet you.',
                'I am well, thank you. What is your name again?', 'It was lovely talking with you. Take care, and see you around!']),
                ('english-22',['Maya, I coordinated a support team. We reduced response time by 20 percent by changing the rota. What would you like to know about my role?'])]:
            session=training.create_session('demo','english-speaking','beginner',activity)
            orchestrator=TrainingOrchestrator(training,provider,None,Mock(),24000,'none')
            for line in lines:
                began=time.perf_counter()
                result=await orchestrator.run_turn(session['id'],RoleplayTurn(text=line,synthesize_audio=False,request_id=uuid.uuid4().hex))
                if BACKGROUND:await asyncio.gather(*list(BACKGROUND),return_exceptions=True)
                report.append({'activity':activity,'learner':line,'responses':result['responses'],
                    'progress':training.evaluate_progress(session['id']), 'wall_ms':round((time.perf_counter()-began)*1000)})
    target=directory/'live-conversation-report.json'
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    for item in report:
        print(json.dumps({'activity':item['activity'],'learner':item['learner'],
            'replies':[(r['speaker'],r['text']) for r in item['responses']],
            'outcome':item['progress']['outcome'],'wall_ms':item['wall_ms']},ensure_ascii=True))
    print(f'Report: {target}')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
    if not args.live:parser.error('--live is required; this calls the configured external provider')
    asyncio.run(run())
