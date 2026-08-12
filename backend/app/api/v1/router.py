from fastapi import APIRouter

from app.api.v1 import (
    dashboard,
    export,
    grammar,
    ingestion,
    jlpt,
    links,
    notion,
    practice,
    quiz,
    songs,
    speech,
    vocab,
)

api_router = APIRouter()
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(notion.router, prefix="/notion", tags=["notion"])
api_router.include_router(vocab.router, prefix="/vocab", tags=["vocab"])
api_router.include_router(grammar.router, prefix="/grammar", tags=["grammar"])
api_router.include_router(jlpt.router, prefix="/jlpt", tags=["jlpt"])
api_router.include_router(links.router, prefix="/graph", tags=["graph"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
api_router.include_router(practice.router, prefix="/practice", tags=["practice"])
api_router.include_router(songs.router, prefix="/songs", tags=["songs"])
api_router.include_router(speech.router, prefix="/speech", tags=["speech"])
