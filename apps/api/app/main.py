from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.mvp import router as mvp_router
from app.core.config import get_settings
from app.db.session import create_db_and_tables
from app.services.paper_scheduler import shutdown_paper_scheduler, start_paper_scheduler


def create_app() -> FastAPI:
    settings = get_settings()
    create_db_and_tables()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        start_paper_scheduler(settings)
        try:
            yield
        finally:
            shutdown_paper_scheduler()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(mvp_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
