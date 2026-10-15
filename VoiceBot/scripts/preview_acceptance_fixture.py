"""Disposable local UI fixture, never a production server or real learner account.

No model/network calls, real account access, microphone, or camera required.
The process uses a temporary database and a fixed synthetic identity exclusively
on 127.0.0.1:8001. Stop with Ctrl+C; the database is then removed automatically.
"""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['HIKARI_SKIP_MODELS']='true'
import uvicorn
import api.server as server
from core.training_service import TrainingService

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='hikari-ui-acceptance-') as directory:
        path=Path(directory)/'fixture.db'
        server.training=TrainingService(path)
        server.auth_service.path=path
        user={'id':'demo','name':'Acceptance fixture','email':'fixture@example.com','role':'Learner',
              'organization':'Hikari Demo','status':'active','is_admin':False}
        server.auth_service.user_for_token=lambda _:user
        server._llm_model=server._stt_model=server._tts_model=None
        uvicorn.run(server.app,host='127.0.0.1',port=8001,log_level='warning')
