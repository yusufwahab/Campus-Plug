import sqlalchemy as sa

import app.models  # noqa: F401
from app.db import Base
from app.rls import disable_statements, enable_statements

API = "/api/v1"


def test_every_table_gets_row_level_security_and_no_public_grants():
    tables = list(Base.metadata.tables)
    sql = enable_statements(tables)
    for table in tables:
        assert f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY' in sql
        assert f'REVOKE ALL ON "{table}" FROM anon, authenticated' in sql
    # only chat messages are readable by signed-in users, and only for their own conversations
    policies = [s for s in sql if s.startswith("CREATE POLICY")]
    assert len(policies) == 1 and '"messages"' in policies[0] and "FOR SELECT" in policies[0]


def test_rls_can_be_undone():
    sql = disable_statements(["messages", "users"])
    assert 'DROP POLICY IF EXISTS "messages_participants_read" ON "messages"' in sql
    assert 'ALTER TABLE "users" DISABLE ROW LEVEL SECURITY' in sql


def test_rls_migration_is_a_noop_on_sqlite(tmp_path, monkeypatch):
    from alembic.config import Config

    from alembic import command
    from app.config import get_settings

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
        assert sa.inspect(sa.create_engine(url)).has_table("users")
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_security_headers_on_every_response(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"]


def test_production_refuses_unsafe_settings():
    from app.config import Settings, production_problems

    unsafe = Settings(app_env="production")
    assert len(production_problems(unsafe)) >= 6
    safe = Settings(
        app_env="production",
        auth_provider="supabase",
        jwt_secret="x" * 40,
        supabase_url="https://abc.supabase.co",
        supabase_jwt_secret="y" * 40,
        database_url="postgresql+psycopg://u:p@host/db",
        payment_provider="paystack",
        paystack_secret_key="sk_test_x",
        expose_dev_codes=False,
        cors_origins="https://campusplug.example",
        web_url="https://campusplug.example",
    )
    assert production_problems(safe) == []
