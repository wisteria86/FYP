"""Isolated NFR-01/02 benchmark. Does not modify the real application database."""
import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import Request
from fastapi.testclient import TestClient
from api.application import create_application
from config import Config
from core.training_service import TrainingService
from services.auth_service import AuthService


def run():
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'benchmark.db'
        training=TrainingService(path)
        auth=AuthService(path)
        app=create_application()
        @app.get('/benchmark/{operation}')
        def common(operation: str,request: Request):
            user=auth.user_for_token(request.cookies.get(Config.AUTH_COOKIE_NAME))
            if not user: raise RuntimeError('Benchmark client was not authenticated')
            return getattr(training,operation)(user['id'])
        clients=[]
        for i in range(20):
            _,token=auth.register(f'Learner {i}',f'learner{i}@example.com','benchmark-password-123')
            client=TestClient(app)
            client.cookies.set(Config.AUTH_COOKIE_NAME,token)
            clients.append(client)
        def execute(client):
            measurements=[]
            for _ in range(5):
                for operation in ('dashboard','history','skills'):
                    start=time.perf_counter()
                    response=client.get('/benchmark/'+operation)
                    elapsed=time.perf_counter()-start
                    if response.status_code!=200: raise RuntimeError(response.text)
                    measurements.append(elapsed)
            return measurements
        try:
            with ThreadPoolExecutor(max_workers=20) as pool:
                values=sorted(value for batch in pool.map(execute,clients) for value in batch)
            print(json.dumps({'authenticated_clients':20,'requests':len(values),
                'p95_ms':round(values[int(len(values)*.95)-1]*1000,1),
                'max_ms':round(max(values)*1000,1),'under_2_seconds':all(v<2 for v in values),
                'scope':'isolated in-process HTTP, common non-AI operations; not GPU or production-network capacity'},indent=2))
        finally:
            for client in clients: client.close()


if __name__=='__main__': run()
