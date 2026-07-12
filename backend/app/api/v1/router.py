from fastapi import APIRouter

from app.api.v1 import dashboard, grammar, ingestion, links, notion, quiz, vocab

api_router = APIRouter()
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(notion.router, prefix="/notion", tags=["notion"])
api_router.include_router(vocab.router, prefix="/vocab", tags=["vocab"])
api_router.include_router(grammar.router, prefix="/grammar", tags=["grammar"])
api_router.include_router(links.router, prefix="/graph", tags=["graph"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
