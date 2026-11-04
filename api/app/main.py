import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.storage import UPLOAD_ROOT
from app.config import get_settings
from app.features.admin import config as admin_config
from app.features.admin import finance as admin_finance
from app.features.admin import growth as admin_growth
from app.features.admin import logs as admin_logs
from app.features.admin import moderation as admin_moderation
from app.features.admin import users as admin_users
from app.features.analytics import router as analytics
from app.features.auth import router as auth
from app.features.catalogue import contact, content, seller
from app.features.catalogue import public as marketplace
from app.features.catalogue import router as catalogue
from app.features.chat import router as chat
from app.features.notifications import router as notifications
from app.features.orders import router as orders
from app.features.promotions import reviews
from app.features.promotions import router as promotions
from app.features.requests import router as plug_requests
from app.features.verification import rep
from app.features.verification import router as verification

API_PREFIX = "/api/v1"
logger = logging.getLogger("campusplug.api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Campus Plug API", version="0.1.0", docs_url=None if settings.is_production else "/docs")

    # Registered BEFORE the CORS middleware so it sits inside it. An unhandled crash then becomes an ordinary JSON 500 that
    # still carries the CORS headers (otherwise the browser reports a misleading "blocked by CORS" instead of the real error),
    # and the full traceback goes to the server log. No detail about the failure is sent to the client.
    @app.middleware("http")
    async def catch_unhandled(request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")  # uploaded images are shown on the web origin
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response

    api = APIRouter(prefix=API_PREFIX)
    # seller before marketplace: "/listings/payout-preview" must match before "/listings/{public_id}"
    for module in (
        auth,
        catalogue,
        seller,
        marketplace,
        contact,
        content,
        verification,
        rep,
        admin_users,
        admin_moderation,
        admin_config,
        admin_logs,
        admin_finance,
        chat,
        notifications,
        plug_requests,
        orders,
        promotions,
        reviews,
        admin_growth,
        analytics,
    ):
        api.include_router(module.router)
    app.include_router(api)
    public_dir = UPLOAD_ROOT / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=public_dir), name="uploads")  # TEST storage; production uses Cloudinary

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
