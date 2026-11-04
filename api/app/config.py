from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./campusplug.db"
    jwt_secret: str = "change-me-local-only-use-a-long-random-string"
    cors_origins: str = "http://localhost:3000"
    payment_provider: str = "local"
    web_url: str = "http://localhost:3000"
    paystack_secret_key: str = ""
    # local = files on this server's disk (test only: Render wipes it on every deploy). cloudinary = real storage.
    storage_provider: str = "local"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    # local = writes to a log only (test). brevo = real email through Brevo's API.
    email_provider: str = "local"
    brevo_api_key: str = ""
    email_from: str = ""
    email_from_name: str = "Campus Plug"
    feature_sms: bool = False
    expose_dev_codes: bool = False
    access_token_minutes: int = 60 * 12
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:support@campusplug.example"
    # Only the throw-away e2e API raises this; production keeps 1.
    rate_limit_multiplier: int = 1

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def production_problems(settings: Settings) -> list[str]:
    """Everything that must be true before the API will start in production."""
    problems = []
    if settings.jwt_secret.startswith("change-me") or len(settings.jwt_secret) < 32:
        problems.append("JWT_SECRET must be a random secret of at least 32 characters")
    if settings.database_url.startswith("sqlite"):
        problems.append("DATABASE_URL must be PostgreSQL, not SQLite")
    if settings.payment_provider != "paystack" or not settings.paystack_secret_key:
        problems.append("PAYMENT_PROVIDER must be paystack with PAYSTACK_SECRET_KEY set")
    if settings.email_provider != "brevo" or not (settings.brevo_api_key and settings.email_from):
        problems.append("EMAIL_PROVIDER must be brevo with BREVO_API_KEY and EMAIL_FROM set (sign-up codes are sent by email)")
    if settings.storage_provider != "cloudinary" or not (
        settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret
    ):
        problems.append("STORAGE_PROVIDER must be cloudinary with CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET set")
    if settings.expose_dev_codes:
        problems.append("EXPOSE_DEV_CODES must be false")
    if settings.rate_limit_multiplier != 1:
        problems.append("RATE_LIMIT_MULTIPLIER must be 1")
    if "localhost" in settings.cors_origins or "localhost" in settings.web_url:
        problems.append("CORS_ORIGINS and WEB_URL must be the real site, not localhost")
    return problems


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and (problems := production_problems(settings)):
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
    return settings
