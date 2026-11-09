"""Local evaluation server. It never uses your real data files.

    python scripts/conversation_eval/serve.py --port 8010          Chat only, empty temporary database.
    python scripts/conversation_eval/serve.py --port 8000 --full   Real speech models, on a copy of data/hikari.db.

Binds to 127.0.0.1 only and deletes its temporary files on exit.
"""
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8010)
parser.add_argument('--full', action='store_true', help='Load speech models and start from a copy of your database')
args = parser.parse_args()

folder = tempfile.TemporaryDirectory(prefix='hikari-eval-')
database = Path(folder.name) / 'eval.db'
settings = Path(folder.name) / 'runtime_settings.json'
if args.full:
    shutil.copy(ROOT / 'data' / 'hikari.db', database)
    if (ROOT / 'data' / 'hikari-vectors.db').exists():
        shutil.copy(ROOT / 'data' / 'hikari-vectors.db', Path(folder.name) / 'eval-vectors.db')
    if (ROOT / 'data' / 'runtime_settings.json').exists():
        shutil.copy(ROOT / 'data' / 'runtime_settings.json', settings)
else:
    os.environ['HIKARI_SKIP_MODELS'] = 'true'
os.environ['DATABASE_PATH'] = str(database)
os.environ.setdefault('ADMIN_EMAILS', 'eval.admin@example.test')  # Only for this temporary database.

import uvicorn  # noqa: E402
import api.server as server  # noqa: E402
from config import Config  # noqa: E402
from modules.llm_brain import LLMBrain  # noqa: E402

if __name__ == '__main__':
    server._settings_path = settings
    if not args.full:
        server._llm_model = LLMBrain(Config.LLM_API_KEY, Config.LLM_MODEL_NAME, Config.LLM_BASE_URL, Config.LLM_ROUTER_MODEL, Config.LLM_REVIEW_MODEL)
    print(f"Evaluation server on http://127.0.0.1:{args.port} ({'full speech, copy of your database' if args.full else 'chat only, empty database'}).", flush=True)
    uvicorn.run(server.app, host='127.0.0.1', port=args.port, log_level='warning')
