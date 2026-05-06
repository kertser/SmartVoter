import logging
import logging.config

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from pythonjsonlogger import json as jsonlogger

from backend.app.config import get_settings
from backend.app.api import api_router
from backend.app.admin import admin_router

settings = get_settings()

# ── Structured JSON logging ──────────────────────────────────────────────────
_handler = logging.StreamHandler()
_handler.setFormatter(
    jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
    )
)
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger(__name__)

# ── Rate limiter (Redis-backed in prod, in-memory in dev) ────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["300/minute"],
)

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartVoter API",
    description=(
        "Evidence-based political match API for Israeli parties. "
        "This tool compares user policy preferences with parties' observed parliamentary "
        "behavior and declared positions. It does not tell users whom to vote for."
    ),
    version="0.1.0",
    # Hide docs in production
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(admin_router)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """Real health check: pings DB and Redis."""
    checks: dict[str, str] = {}

    # DB ping
    try:
        from sqlalchemy import text
        from backend.app.db.session import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("Health DB ping failed: %s", exc)
        checks["db"] = f"error: {exc}"

    # Redis ping
    try:
        import redis as redis_lib
        r = redis_lib.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.warning("Health Redis ping failed: %s", exc)
        checks["redis"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "version": "0.1.0", "checks": checks}
