"""Authenticated, bounded PCM streaming transport for local recognition."""
import asyncio
import json
import time
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from config import Config
from contextlib import nullcontext


def install_speech_stream(app,get_model,authorize,metrics,activity=None):
    connections={}

    @app.websocket('/api/sessions/{session_id}/speech-stream')
    async def speech_stream(socket:WebSocket,session_id:str):
        if socket.headers.get('origin') not in Config.CORS_ORIGINS:
            await socket.close(code=1008);return
        try:
            session=authorize(socket,session_id)
        except (HTTPException,ValueError):
            await socket.close(code=1008);return
        owner=session['user_id']
        if connections.get(owner,0)>=2:
            await socket.close(code=1013);return
        lease=activity.use() if activity else nullcontext()
        try:lease.__enter__()
        except RuntimeError:
            await socket.close(code=1013);return
        model=get_model()
        language=session.get('training_language') or 'English'
        if not model or not hasattr(model,'supports_streaming') or not model.supports_streaming(language):
            lease.__exit__(None,None,None)
            await socket.close(code=1003);return
        if session.get('status')!='active':
            lease.__exit__(None,None,None)
            await socket.close(code=1008);return
        connections[owner]=connections.get(owner,0)+1
        started=time.perf_counter()
        try:
            await socket.accept()
            metadata=await asyncio.wait_for(socket.receive_json(),5)
            rate=int(metadata.get('sample_rate',0))
            if rate not in {16000,22050,24000,32000,44100,48000,96000}:
                raise ValueError('Unsupported capture sample rate')
            recognizer=model.primary
            stream=await asyncio.to_thread(recognizer.create_stream)
            await socket.send_json({'type':'ready','engine':'nemotron'})
            received=0;last_text=''
            while True:
                message=await asyncio.wait_for(socket.receive(),15)
                if message['type']=='websocket.disconnect':break
                if time.perf_counter()-started>100:
                    raise ValueError('Capture exceeded the streaming time limit')
                if message.get('bytes') is not None:
                    data=message['bytes'];received+=len(data)
                    if not data or len(data)>65536 or len(data)%4 or received>rate*4*90:
                        raise ValueError('Invalid or oversized PCM capture')
                    samples=np.frombuffer(data,dtype='<f4')
                    if not np.isfinite(samples).all() or np.max(np.abs(samples))>1.01:
                        raise ValueError('Invalid PCM samples')
                    text=await asyncio.to_thread(recognizer.accept_audio,stream,samples,rate)
                    if text and text!=last_text:
                        last_text=text
                        await socket.send_json({'type':'partial','text':text,'final':False})
                elif message.get('text') is not None:
                    if len(message['text'])>128 or json.loads(message['text']).get('type')!='finish':
                        raise ValueError('Invalid streaming command')
                    finalized=time.perf_counter()
                    result=await asyncio.to_thread(recognizer.finish_stream,stream)
                    final_ms=(time.perf_counter()-finalized)*1000
                    elapsed=(time.perf_counter()-started)*1000
                    metrics.record('transcription','streaming speech',elapsed,True,engine='nemotron',streaming=True,audio_ms=received/rate/4*1000)
                    await socket.send_json({'type':'final',**result,'needs_retry':False,'latency_ms':round(final_ms,1),'stream_wall_ms':round(elapsed,1)})
                    break
        except WebSocketDisconnect:
            pass
        except Exception:
            try:await socket.send_json({'type':'error','message':'Live recognition unavailable; retrying the recorded audio.'})
            except Exception:pass
        finally:
            lease.__exit__(None,None,None)
            connections[owner]-=1
            if not connections[owner]:connections.pop(owner,None)
            try:await socket.close()
            except Exception:pass
