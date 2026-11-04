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
    # Nothing is readable through the database's own public API: no policies and no grants.
    assert not [s for s in sql if s.startswith(("CREATE POLICY", "GRANT"))]


def test_rls_can_be_undone():
    assert 'ALTER TABLE "users" DISABLE ROW LEVEL SECURITY' in disable_statements(["messages", "users"])


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

    unsafe = Settings(app_env="production", _env_file=None)
    assert len(production_problems(unsafe)) >= 5
    safe = Settings(
        app_env="production",
        _env_file=None,
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://u:p@host/db",
        payment_provider="paystack",
        paystack_secret_key="sk_test_x",
        email_provider="brevo",
        brevo_api_key="key",
        email_from="no-reply@campusplug.example",
        storage_provider="cloudinary",
        cloudinary_cloud_name="demo",
        cloudinary_api_key="key",
        cloudinary_api_secret="secret",
        expose_dev_codes=False,
        cors_origins="https://campusplug.example",
        web_url="https://campusplug.example",
    )
    assert production_problems(safe) == []
    assert any("JWT_SECRET" in p for p in production_problems(safe.model_copy(update={"jwt_secret": "short"})))
    assert any("brevo" in p.lower() for p in production_problems(safe.model_copy(update={"email_provider": "local"})))
    assert any("cloudinary" in p.lower() for p in production_problems(safe.model_copy(update={"storage_provider": "local"})))


def test_brevo_sends_through_the_transactional_api_without_logging_the_message(monkeypatch, caplog):
    import httpx

    from app.adapters import email as email_module

    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers)
        return httpx.Response(401, json={"code": "unauthorized", "message": "Key not found"})

    monkeypatch.setattr(email_module.httpx, "post", fake_post)
    sender = email_module.BrevoEmail("secret-key", "no-reply@campusplug.example", "Campus Plug")
    with caplog.at_level("ERROR", logger="campusplug.email"):
        sender.send("ada@example.com", "Your code", "Your code is 123456")
    assert seen["url"] == "https://api.brevo.com/v3/smtp/email"
    assert seen["headers"]["api-key"] == "secret-key"
    assert seen["json"]["to"] == [{"email": "ada@example.com"}]
    assert seen["json"]["sender"]["email"] == "no-reply@campusplug.example"
    assert "status=401" in caplog.text and "unauthorized" in caplog.text
    assert "ada@example.com" not in caplog.text and "123456" not in caplog.text and "secret-key" not in caplog.text


def test_brevo_network_failure_does_not_crash_the_request(monkeypatch):
    import httpx

    from app.adapters import email as email_module

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(email_module.httpx, "post", boom)
    email_module.BrevoEmail("k", "a@b.example", "X").send("ada@example.com", "s", "b")  # must not raise


def test_email_provider_is_chosen_from_settings(monkeypatch):
    from app.adapters.email import BrevoEmail, LocalEmail, get_email
    from app.config import get_settings

    assert isinstance(get_email(), LocalEmail)
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "k")
    monkeypatch.setenv("EMAIL_FROM", "no-reply@campusplug.example")
    get_settings.cache_clear()
    try:
        assert isinstance(get_email(), BrevoEmail)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_a_crash_is_a_json_500_that_still_has_cors_headers_and_is_logged(caplog):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("database exploded: password=hunter2")

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="campusplug.api"):
        res = client.get("/boom", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 500
    assert res.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"  # so the browser shows the real error, not "CORS"
    assert "hunter2" not in res.text  # nothing about the failure is sent to the client
    assert "Unhandled error on GET /boom" in caplog.text  # but the traceback is in the server log
