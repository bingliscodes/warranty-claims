"""Runs migrations. Alembic loads this file for every `alembic` command."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import Settings
from app.db import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: when the tests run migrations, this
    # mustn't silence the app's loggers that are already set up.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# What the models say the schema should be. Autogenerate and `alembic check`
# compare the database against this.
target_metadata = Base.metadata


def database_url() -> str:
    # The tests set sqlalchemy.url to the test database; otherwise use the app's config.
    return config.get_main_option("sqlalchemy.url") or Settings().DATABASE_URL


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
