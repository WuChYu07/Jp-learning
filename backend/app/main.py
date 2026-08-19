from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import require_site_auth
from app.api.v1.auth import router as auth_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.services.owner_service import ensure_owner_user


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # /auth/login must stay outside the gate below — it's how you get the token
    # that satisfies that gate in the first place.
    app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])

    # Router-level dependency: covers every route under api_router uniformly,
    # including ones that don't declare any user-identity dependency of their
    # own (see docs/private/PROJECT_DEEP_DIVE.md for why that mattered).
    app.include_router(
        api_router,
        prefix=settings.API_V1_PREFIX,
        dependencies=[Depends(require_site_auth)],
    )

    @app.on_event("startup")
    def _ensure_singleton_owner() -> None:
        if not settings.AUTH_ENABLED:
            ensure_owner_user()

    # GET for browsers / curl; HEAD for free UptimeRobot checks (no GET quota).
    @app.api_route("/health", methods=["GET", "HEAD"], tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
