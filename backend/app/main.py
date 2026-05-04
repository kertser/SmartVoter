from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.api import api_router
from backend.app.admin import admin_router

settings = get_settings()

app = FastAPI(
    title="SmartVoter API",
    description=(
        "Evidence-based political match API for Israeli parties. "
        "This tool compares user policy preferences with parties' observed parliamentary "
        "behavior and declared positions. It does not tell users whom to vote for."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
    return {"status": "ok", "version": "0.1.0"}

