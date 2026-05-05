from fastapi import APIRouter
from backend.app.api.topics import router as topics_router
from backend.app.api.questions import router as questions_router
from backend.app.api.answers import router as answers_router
from backend.app.api.results import router as results_router
from backend.app.api.methodology import router as methodology_router
from backend.app.api.lineage import router as lineage_router

api_router = APIRouter(prefix="/api")
api_router.include_router(topics_router)
api_router.include_router(questions_router)
api_router.include_router(answers_router)
api_router.include_router(results_router)
api_router.include_router(methodology_router)
api_router.include_router(lineage_router)

