"""Runs a command against a throw-away PostgreSQL that lives on THIS computer (data in api/.pgdata, git-ignored).

Examples (from api/):
    python scripts/pg_test.py -m alembic upgrade head     # apply every migration on real PostgreSQL
    python scripts/pg_test.py -m pytest -q                # run the whole test suite on PostgreSQL instead of SQLite

It sets DATABASE_URL and TEST_DATABASE_URL for the command only. The test fixtures refuse any database that is not on
127.0.0.1 / localhost, so this can never touch a real database. Needs: pip install pgserver (listed in requirements-dev.txt).
"""

import os
import subprocess
import sys
from pathlib import Path

import pgserver

API = Path(__file__).resolve().parents[1]
uri = pgserver.get_server(str(API / ".pgdata"), cleanup_mode=None).get_uri()
url = uri.replace("postgresql://", "postgresql+psycopg://", 1)
env = {**os.environ, "DATABASE_URL": url, "TEST_DATABASE_URL": url, "APP_ENV": "test", "PYTHONPATH": str(API)}
sys.exit(subprocess.call([sys.executable, *sys.argv[1:]], env=env, cwd=API))  # noqa: S603 (our own interpreter and arguments)
