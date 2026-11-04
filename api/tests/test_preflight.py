import httpx
import pytest

from app import preflight
from app.config import Settings

SECRETS = {
    "jwt_secret": "JWT-SECRET-VALUE-" + "x" * 30,
    "paystack_secret_key": "sk_test_PAYSTACK-SECRET-VALUE",
    "brevo_api_key": "xkeysib-BREVO-SECRET-VALUE",
    "cloudinary_api_secret": "CLOUDINARY-SECRET-VALUE",
    "cloudinary_api_key": "CLOUDINARY-KEY-VALUE",
}


def settings(**over) -> Settings:
    base = {
        "app_env": "staging",
        "database_url": "postgresql+psycopg://dbuser:DB-PASSWORD-VALUE@db.example.com:6543/postgres?sslmode=require",
        "payment_provider": "paystack",
        "email_provider": "brevo",
        "email_from": "no-reply@campusplug.example",
        "storage_provider": "cloudinary",
        "cloudinary_cloud_name": "democloud",
        "web_url": "http://localhost:3000",
        "cors_origins": "http://localhost:3000",
        **SECRETS,
    }
    return Settings(_env_file=None, **{**base, **over})


def everything_printed(s: Settings, online: bool = False) -> str:
    checks = preflight.offline_checks(s) + (preflight.online_checks(s) if online else [])
    return preflight.render(checks)


def test_offline_report_never_contains_a_secret_or_the_connection_string():
    out = everything_printed(settings())
    for value in [*SECRETS.values(), "DB-PASSWORD-VALUE", "dbuser", "db.example.com", "democloud"]:
        assert value not in out
    assert "[OK  ] JWT_SECRET" in out and "TEST key" in out


def test_a_live_paystack_key_is_called_out_and_a_weak_secret_fails():
    out = everything_printed(settings(paystack_secret_key="sk_live_REAL-MONEY-KEY", jwt_secret="change-me-please"))
    assert "LIVE key" in out and "sk_live_REAL-MONEY-KEY" not in out
    assert "[FAIL] JWT_SECRET" in out


def test_localhost_is_a_warning_for_a_rehearsal_and_production_rules_are_summarised():
    out = everything_printed(settings())
    assert "[WARN] WEB_URL / CORS_ORIGINS" in out
    assert "Production start-up rules" in out and "would block a production start" in out


def test_online_checks_report_results_without_leaking_anything(monkeypatch):
    def fake_send(self, request, **kwargs):
        host = request.url.host
        return {
            "api.brevo.com": httpx.Response(200, json={}),
            "api.cloudinary.com": httpx.Response(401),
            "api.paystack.co": httpx.Response(200, json={}),
        }[host]

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    # The database is unreachable on purpose; its error text (which contains the connection string) must never be printed.
    out = everything_printed(settings(), online=True)
    assert "[FAIL] Database connection" in out and "could not connect" in out
    assert "[OK  ] Brevo account" in out and "[FAIL] Cloudinary account" in out and "[OK  ] Paystack account" in out
    for value in [*SECRETS.values(), "DB-PASSWORD-VALUE", "dbuser"]:
        assert value not in out


def test_network_errors_are_reported_without_details(monkeypatch):
    def boom(self, request, **kwargs):
        raise httpx.ConnectError("secret-bearing url in message " + SECRETS["brevo_api_key"])

    monkeypatch.setattr(httpx.Client, "send", boom)
    out = everything_printed(settings(), online=True)
    assert "could not reach the service" in out
    assert SECRETS["brevo_api_key"] not in out


def test_exit_code_reflects_failures(capsys):
    assert preflight.run(online=False, settings=settings(jwt_secret="short")) == 1
    assert "problem(s) to fix" in capsys.readouterr().out


def test_seed_refuses_a_postgres_database_unless_explicitly_allowed(monkeypatch, db):
    from app.config import get_settings
    from app.seed_dev import seed_dev

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example.com/x")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="only runs on SQLite"):
            seed_dev(db)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
