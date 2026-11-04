"""Checks the configuration you are about to run with, WITHOUT ever printing a secret.

Run: python -m app.cli preflight            (offline: looks only at the settings)
     python -m app.cli preflight --online   (also makes one harmless, read-only call to each service)

Output is names, OK / WARN / FAIL and short reasons. It never prints a key, password, token or connection string,
and it never prints an exception message (database errors can contain the connection string).
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from sqlalchemy import create_engine, inspect, text

from app.config import Settings, production_problems

TIMEOUT = 12.0


@dataclass
class Check:
    name: str
    status: str  # OK | WARN | FAIL
    detail: str


def _secret_state(value: str, *, min_len: int = 1) -> str:
    return f"set ({len(value)} characters)" if len(value) >= min_len else "missing"


def offline_checks(s: Settings) -> list[Check]:
    out: list[Check] = []
    add = lambda name, status, detail: out.append(Check(name, status, detail))  # noqa: E731

    add("APP_ENV", "OK" if s.app_env in ("production", "staging", "local", "test") else "WARN", s.app_env)

    if len(s.jwt_secret) >= 32 and not s.jwt_secret.startswith("change-me"):
        add("JWT_SECRET", "OK", _secret_state(s.jwt_secret))
    else:
        add("JWT_SECRET", "FAIL", "must be random and at least 32 characters")

    url = urlsplit(s.database_url)
    scheme = url.scheme.split("+")[0]
    if scheme == "sqlite":
        add("DATABASE_URL", "FAIL" if s.app_env == "production" else "WARN", "SQLite (fine for tests, not for production)")
    elif scheme in ("postgresql", "postgres"):
        ssl = "sslmode=require" in (url.query or "")
        add("DATABASE_URL", "OK" if ssl else "WARN", "PostgreSQL" + ("" if ssl else " without sslmode=require"))
    else:
        add("DATABASE_URL", "FAIL", "unrecognised database type")

    if s.payment_provider == "paystack" and s.paystack_secret_key:
        if s.paystack_secret_key.startswith("sk_live_"):
            add("PAYSTACK_SECRET_KEY", "WARN", "LIVE key: payments made against it move real money")
        elif s.paystack_secret_key.startswith("sk_test_"):
            add("PAYSTACK_SECRET_KEY", "OK", "TEST key (no real money)")
        else:
            add("PAYSTACK_SECRET_KEY", "FAIL", "does not look like a Paystack secret key")
    else:
        add("PAYSTACK_SECRET_KEY", "FAIL" if s.app_env == "production" else "WARN", f"payment provider is {s.payment_provider}")

    if s.email_provider == "brevo" and s.brevo_api_key and "@" in s.email_from:
        add("EMAIL (Brevo)", "OK", f"BREVO_API_KEY {_secret_state(s.brevo_api_key)}, sender address set")
    else:
        add(
            "EMAIL (Brevo)",
            "FAIL" if s.app_env == "production" else "WARN",
            f"provider is {s.email_provider}; needs BREVO_API_KEY and EMAIL_FROM",
        )

    if s.storage_provider == "cloudinary" and s.cloudinary_cloud_name and s.cloudinary_api_key and s.cloudinary_api_secret:
        add("STORAGE (Cloudinary)", "OK", "cloud name, API key and API secret set")
    else:
        add(
            "STORAGE (Cloudinary)",
            "FAIL" if s.app_env == "production" else "WARN",
            f"provider is {s.storage_provider}; needs all three Cloudinary values",
        )

    add(
        "EXPOSE_DEV_CODES",
        "FAIL" if s.expose_dev_codes and s.app_env == "production" else ("WARN" if s.expose_dev_codes else "OK"),
        "on" if s.expose_dev_codes else "off",
    )
    add("RATE_LIMIT_MULTIPLIER", "OK" if s.rate_limit_multiplier == 1 else "FAIL", str(s.rate_limit_multiplier))
    local = "localhost" in s.web_url or "localhost" in s.cors_origins
    add(
        "WEB_URL / CORS_ORIGINS",
        "WARN" if local else "OK",
        "localhost (right for a local rehearsal, wrong on Render)" if local else "real site address",
    )

    problems = production_problems(s)
    add(
        "Production start-up rules",
        "OK" if not problems else "WARN",
        "all pass" if not problems else f"{len(problems)} would block a production start: " + "; ".join(p.split(" (")[0] for p in problems),
    )
    return out


def online_checks(s: Settings) -> list[Check]:
    out: list[Check] = []

    try:
        engine = create_engine(s.database_url, connect_args={"connect_timeout": 8} if not s.database_url.startswith("sqlite") else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            migrated = "alembic_version" in inspect(conn).get_table_names()
        out.append(
            Check(
                "Database connection",
                "OK",
                "connected" + ("; migrations table present" if migrated else "; no tables yet (run: alembic upgrade head)"),
            )
        )
    except Exception:  # noqa: BLE001 - never print the error: it can contain the connection string
        out.append(Check("Database connection", "FAIL", "could not connect (check host, password and sslmode)"))

    def call(name: str, url: str, ok: str, **kwargs: object) -> None:
        try:
            res = httpx.Client(timeout=TIMEOUT).get(url, **kwargs)  # type: ignore[arg-type]
        except httpx.HTTPError:
            out.append(Check(name, "FAIL", "could not reach the service"))
            return
        if res.status_code < 300:
            out.append(Check(name, "OK", ok))
        elif res.status_code in (401, 403):
            out.append(Check(name, "FAIL", "key rejected"))
        else:
            out.append(Check(name, "WARN", f"unexpected answer (status {res.status_code})"))

    if s.brevo_api_key:
        call("Brevo account", "https://api.brevo.com/v3/account", "key accepted (no email sent)", headers={"api-key": s.brevo_api_key})
    if s.cloudinary_cloud_name and s.cloudinary_api_key and s.cloudinary_api_secret:
        call(
            "Cloudinary account",
            f"https://api.cloudinary.com/v1_1/{s.cloudinary_cloud_name}/ping",
            "credentials accepted (nothing uploaded)",
            auth=(s.cloudinary_api_key, s.cloudinary_api_secret),
        )
    if s.paystack_secret_key:
        call(
            "Paystack account",
            "https://api.paystack.co/bank?country=nigeria&perPage=1",
            "key accepted (no payment made)",
            headers={"Authorization": f"Bearer {s.paystack_secret_key}"},
        )
    return out


def render(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    return "\n".join(f"[{c.status:<4}] {c.name:<{width}}  {c.detail}" for c in checks)


def run(online: bool, settings: Settings | None = None) -> int:
    from app.config import Settings as S

    s = settings or S()
    checks = offline_checks(s) + (online_checks(s) if online else [])
    print(render(checks))
    failed = [c for c in checks if c.status == "FAIL"]
    print("\n" + (f"{len(failed)} problem(s) to fix." if failed else "No blocking problems."))
    return 1 if failed else 0
