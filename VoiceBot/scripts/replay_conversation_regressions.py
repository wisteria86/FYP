"""Replay the reported fictional exchanges against the configured provider.

Opt in with --live. This checks dialogue behavior, not microphone recognition
or educational validity. Background assessment is left out of this focused run.
"""
import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from api.schemas import RoleplayTurn
from config import Config
from core.training_service import TrainingService
from integrations.conversation import ConversationAdapter
from modules.llm_brain import LLMBrain
from services.training_orchestrator import TrainingOrchestrator
from services.structured_orchestrator import cancel_scheduled_review, BACKGROUND


async def main(delay=5,meeting=False,proactive=False,output=None,max_turns=None):
    target=ROOT/('tmp/runtime-tests/proactive-group-replay.json' if proactive else 'tmp/runtime-tests/meeting-dialogue-replay.json' if meeting else 'tmp/runtime-tests/reported-dialogue-replay.json')
    if output:target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    provider=ConversationAdapter(LLMBrain(Config.LLM_API_KEY,Config.LLM_MODEL_NAME,Config.LLM_BASE_URL))
    cases=[('negotiation',None,[
        'First tell me who are you','I will offer you ten seats','I will offer you ten seeds',
        'Okay, I will take it for ten thousand',
        'Alternative supplier offers twenty seats for USD eighty five hundred in forty five days with one month support','Yes, I can']),
        ('english-speaking','english-20',[
        "Now let's decide what the plan is supposed to accomplish","I'm not really that sure",
        'Okay, if I do this','So I meant to get I do this',
        'So I mean the other person is going to tell tell me',
        "I mean the other person is going to tell me",'They will tell the plan'])]
    if meeting:
        cases=[('english-speaking','english-27',[
            'Sam, why are you changing the plan', 'Okay Sam, can you tell me more about it',
            'Okay, get me about this', 'Zap zap', 'Can you tell me about it, Sam',
            'Okay', "I don't know. Tell me about it", 'Okay',
            'What the heck are you talking about', 'Why did you do it, man',
            'Why did you do it then', 'Why did that do it', 'Why did that do it',
            'Alex, tell Sam what you need before the next change', 'Both of you, agree a next step'])]
    if proactive:
        cases=[('english-speaking','english-27',[
            'I think we need to hear the concerns before deciding what happens next.',
            'We should discuss changes before editing the shared plan.',
            'Let us agree who will do what next.']),
            ('english-speaking','english-20',[
            'We should spend most of the workshop on practical work.',
            'I think a short demonstration followed by paired practice would help.'])]
    report=[]
    with tempfile.TemporaryDirectory(dir=target.parent) as folder:
        training=TrainingService(Path(folder)/'replay.db')
        runner=TrainingOrchestrator(training,provider,None,Mock(),24000,'none')
        for skill,activity,lines in cases:
            session=training.create_session('demo',skill,'intermediate',activity)
            for line in lines:
                if max_turns and len(report)>=max_turns:break
                started=time.perf_counter()
                before=provider.provider.quota.requests
                result=await runner.run_turn(session['id'],RoleplayTurn(text=line,synthesize_audio=False))
                cancel_scheduled_review(training,session['id'])
                row={'skill':skill,'learner':line,'replies':[{'speaker':r['speaker'],'id':r['participant_id'],'text':r['text'],'mode':r.get('response_mode')} for r in result['responses']],
                     'provider_status':result['runtime'].get('provider_status'),'latency_ms':round((time.perf_counter()-started)*1000),
                     'provider_requests':provider.provider.quota.requests-before,'quota_headers':provider.provider.quota.last_headers,
                     'quota_reason':provider.provider.quota.limit_reason}
                report.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
                target.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
                await asyncio.sleep(delay)
        pending=list(BACKGROUND)
        for task in pending:task.cancel()
        if pending:await asyncio.gather(*pending,return_exceptions=True)
    print(f'Report: {target}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--delay',type=float,default=5)
    parser.add_argument('--meeting',action='store_true',help='Replay the reported Alex/Sam conflict meeting')
    parser.add_argument('--proactive',action='store_true',help='Check group participation without naming or calling on anyone')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--max-turns',type=int)
    args=parser.parse_args()
    if not args.live:parser.error('--live is required')
    asyncio.run(main(max(0,args.delay),args.meeting,args.proactive,args.output,args.max_turns))
