from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import app.models  # noqa: F401  (registers the tables on Base.metadata)
from app.db import Base


def test_migrations_match_models(engine):
    """The schema built by the migrations is exactly what the models describe."""
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
