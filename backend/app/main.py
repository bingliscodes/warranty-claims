import logging

from fastapi import Depends, FastAPI, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db, make_session_factory

logger = logging.getLogger(__name__)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Warranty Claims")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.DATABASE_URL)

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
