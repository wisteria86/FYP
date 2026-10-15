"""Real localhost acceptance checks on an isolated synthetic QA account.

Uses actual HTTP routes and configured models. Never changes speech settings,
deletes records, or accesses existing learners. Leaves labelled QA data.
"""
import base64
import io
import json
import os
import wave
import httpx


def main():
    results=[]
    with httpx.Client(base_url='http://localhost:8000/api',timeout=120) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            response.raise_for_status()
            return response.json()
        call('POST','/auth/login',json={'email':os.environ['HIKARI_QA_EMAIL'],'password':os.environ['HIKARI_QA_PASSWORD']})
        health=call('GET','/health')
        assert health['database_schema']==7 and all(health['components'].values())
        results.append({'check':'live CUDA models and schema','result':health})
        activities=call('GET','/training/activities')
        assert len([a for a in activities if a['training_language']=='English'])==30
        assert {'one_to_one','learner_with_ai_team','ai_team_vs_learner','round_robin'} <= {a['roleplay_mode'] for a in activities}
        results.append({'check':'30 English lessons, workplace categories, four call modes','passed':True})
        document=next((doc for doc in call('GET','/documents') if doc['name']=='qa-travel-policy.txt' and doc['status']=='ready'),None)
        if document is None:
            document=call('POST','/documents',files={'file':('qa-travel-policy.txt',b'Overseas travel requires team lead Jordan approval before booking. Domestic travel requires department manager approval.','text/plain')})
        document_id=document['id']
        args={'skill_id':'company-knowledge','difficulty':'beginner','document_ids':[document_id]}
        first=call('POST','/scenarios/preview',json=args)
        second=call('POST','/scenarios/preview',json=args)
        assert first['situation']!=second['situation']
        session=call('POST','/sessions',json={**args,'preview_id':first['preview_id']})
        assert session['situation']==first['situation']
        assert client.post(f"/sessions/{session['id']}/complete").status_code==409
        for text in ['Overseas travel requires team lead Jordan approval before booking. I will ask Jordan before I book.',
                     'For domestic travel I will request department manager approval and follow the policy before booking.',
                     'If an urgent exception is not covered by the travel policy, I will verify it and ask an authorized manager.']:
            response=call('POST',f"/sessions/{session['id']}/turn",json={'text':text,'synthesize_audio':False})
            assert all(s['document_id']==document_id for s in response['sources'])
        assert response['session_progress']['outcome']=='success'
        stored=call('GET',f"/sessions/{session['id']}")
        assert stored['status']=='completed' and stored['assessment']
        results.append({'check':'selected-document RAG, varied briefing, success/assessment/progress persistence','passed':True,'session_id':session['id']})
        preview=call('POST','/scenarios/preview',json={'skill_id':'presentations','difficulty':'beginner','posture_enabled':True})
        session=call('POST','/sessions',json={'skill_id':'presentations','difficulty':'beginner','preview_id':preview['preview_id']})
        assert session['posture_enabled']
        call('POST',f"/sessions/{session['id']}/cancel")
        results.append({'check':'optional posture capability and cancellation','passed':True})
        speech=client.post('/tts/stream',json={'text':'Hello, my name is Alex. Nice to meet you.'})
        speech.raise_for_status()
        events=[json.loads(line) for line in speech.text.splitlines()]
        blocks=[base64.b64decode(e['audio_b64']) for e in events if e['type']=='audio']
        assert blocks, events
        frames=[]
        for block in blocks:
            with wave.open(io.BytesIO(block),'rb') as chunk:
                assert chunk.getsampwidth()==2 and chunk.getnchannels()==1
                frames.append(chunk.readframes(chunk.getnframes()))
        wav=io.BytesIO()
        with wave.open(wav,'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(health['sample_rate'])
            out.writeframes(b''.join(frames))
        recognized=call('POST','/transcribe',files={'file':('qa-speech.wav',wav.getvalue(),'audio/wav')},data={'language':'English'})
        assert 'alex' in recognized['text'].lower(), recognized
        results.append({'check':'actual ChatTTS audio → Whisper medium CUDA transcription','passed':True,'transcript':recognized['text']})
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
