"""Import this before the server so that tests can never touch data/hikari.db.

Importing the server opens and migrates the configured database, so this must come first.
"""
import atexit
import os
import shutil
import tempfile

_folder = tempfile.mkdtemp(prefix='hikari-tests-')
os.environ['DATABASE_PATH'] = os.path.join(_folder, 'test.db')
os.environ['VECTOR_DATABASE_PATH'] = os.path.join(_folder, 'vectors.db')
os.environ['HIKARI_SKIP_MODELS'] = 'true'
atexit.register(shutil.rmtree, _folder, ignore_errors=True)
