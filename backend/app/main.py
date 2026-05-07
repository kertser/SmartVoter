import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager

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


# ── Poll refresh helpers ─────────────────────────────────────────────────────


def _polls_need_refresh(db) -> bool:
    """
    Return True if we should fetch fresh polls.
    Skip if a web_search poll was already stored today (same UTC date).
    """
    try:
        from datetime import date as _date
        from backend.app.models.simulation import Poll
        latest = (
            db.query(Poll)
            .filter(Poll.method == "web_search")
            .order_by(Poll.publication_date.desc())
            .first()
        )
        if latest is None:
            return True  # no live polls yet
        # Allow at most one refresh per calendar day (UTC)
        return latest.publication_date < _date.today()
    except Exception:
        return False


def _background_poll_refresh() -> None:
    """Synchronous worker: fetch live polls and store them. Runs in a thread."""
    from backend.app.db.session import SessionLocal
    from backend.app.services.polling.web_polling import fetch_and_store_live_polls

    db = SessionLocal()
    try:
        if not _polls_need_refresh(db):
            logger.info("startup poll refresh: data is fresh, skipping")
            return

        logger.info(
            "startup poll refresh: fetching live polls via OpenAI web search (model=gpt-4o)"
        )
        result = fetch_and_store_live_polls(
            db=db,
            api_key=settings.openai_api_key,
            model="gpt-4o",
        )
        if result["polls_stored"] > 0:
            logger.info(
                "startup poll refresh: stored %d polls, %d party results (source=%s)",
                result["polls_stored"],
                result["parties_stored"],
                result["source"],
            )
            if result.get("warnings"):
                for w in result["warnings"]:
                    logger.warning("startup poll refresh: %s", w)
        else:
            logger.warning(
                "startup poll refresh: no polls stored — %s",
                "; ".join(result.get("warnings", ["unknown reason"])),
            )
    except Exception as exc:
        logger.error("startup poll refresh: unexpected error: %s", exc)
    finally:
        db.close()


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: runs startup tasks then yields."""
    # Trigger poll refresh in background so we don't block the server startup
    if settings.has_openai:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _background_poll_refresh)
        logger.info("startup: scheduled background poll refresh")
    else:
        logger.info("startup: no OpenAI key configured — skipping poll refresh")

    yield
    # (shutdown tasks go here if needed)


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
    lifespan=lifespan,
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
