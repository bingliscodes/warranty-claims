import logging

from fastapi import Depends, FastAPI, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import OriginCheckMiddleware
from app.auth import router as auth_router
from app.claims.routes import router as claims_router
from app.config import Settings
from app.conversations import router as conversations_router
from app.db import get_db, make_session_factory
from app.photos.routes import router as photos_router
from app.storage import build_storage
from app.unread import router as unread_router
from app.uploads import router as upload_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Warranty Claims")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.DATABASE_URL)
    app.state.storage = build_storage(settings)
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.ALLOWED_ORIGINS)
    app.include_router(auth_router)
    app.include_router(upload_router)
    app.include_router(claims_router)
    app.include_router(photos_router)
    app.include_router(conversations_router)
    app.include_router(unread_router)

    @app.get("/api/health")
    def health(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
        """Up only if the database answers, so a host can tell when the app is down."""
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("Health check failed: database unreachable (%s)", type(exc).__name__)
            response.status_code = 503
            return {"status": "unavailable"}
        return {"status": "ok"}

    return app


app = create_app()
