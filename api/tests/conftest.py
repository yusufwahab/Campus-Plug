import os

# Settings also read api/.env. Set every value here so a developer's real .env can never change what tests do,
# and so tests can never reach a real database, payment account or mailbox.
TEST_ENV = {
    "APP_ENV": "test",
    "DATABASE_URL": "sqlite://",
    "JWT_SECRET": "test-only-secret-not-used-anywhere-else-0123456789",
    "EXPOSE_DEV_CODES": "true",
    "PAYMENT_PROVIDER": "local",
    "PAYSTACK_SECRET_KEY": "",
    "EMAIL_PROVIDER": "local",
    "BREVO_API_KEY": "",
    "EMAIL_FROM": "",
    "STORAGE_PROVIDER": "local",
    "CLOUDINARY_CLOUD_NAME": "",
    "CLOUDINARY_API_KEY": "",
    "CLOUDINARY_API_SECRET": "",
    "CORS_ORIGINS": "http://localhost:3000",
    "WEB_URL": "http://localhost:3000",
    "FEATURE_SMS": "false",
    "VAPID_PRIVATE_KEY": "",
    "VAPID_PUBLIC_KEY": "",
    "RATE_LIMIT_MULTIPLIER": "1",
}
os.environ.update(TEST_ENV)

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402, F401
from app.db import Base, get_db  # noqa: E402
from app.features.catalogue.reference import seed_reference  # noqa: E402
from app.main import app  # noqa: E402
from app.models.identity import User  # noqa: E402
from app.ratelimit import reset_limits  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_reference(session)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db):
    reset_limits()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


class Helpers:
    def __init__(self, client: TestClient, db):
        self.client, self.db = client, db

    def make_user(self, email: str, role: str = "buyer", password: str = "password123", **extra) -> User:
        fields = {"full_name": email.split("@")[0].title(), **extra}
        user = User(email=email, role=role, password_hash=hash_password(password), **fields)
        self.db.add(user)
        self.db.commit()
        return user

    def login(self, email: str, password: str = "password123") -> dict[str, str]:
        res = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        body = res.json()
        if body["mfa_required"]:
            user = self.db.query(User).filter_by(email=email).one()
            if not user.mfa_secret:
                self.client.post("/api/v1/auth/mfa/enroll", json={"mfa_token": body["mfa_token"]})
                self.db.refresh(user)
            code = pyotp.TOTP(user.mfa_secret).now()
            body = self.client.post("/api/v1/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": code}).json()
        return {"Authorization": f"Bearer {body['token']}"}


@pytest.fixture()
def h(client, db) -> Helpers:
    return Helpers(client, db)
