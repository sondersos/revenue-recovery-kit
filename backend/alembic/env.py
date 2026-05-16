import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Import all models so that Base.metadata is fully populated before any
# autogenerate or migration run.
# ---------------------------------------------------------------------------
from app.models.base import Base  # noqa: F401
from app.models import contact, invoice, sequence, detection  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
target_metadata = Base.metadata


def _get_sync_url() -> str:
    """
    Return a *synchronous* psycopg connection URL for Alembic.

    The application runtime uses asyncpg; Alembic does not support async
    natively, so we swap the driver to psycopg (sync) here.
    """
    url = os.environ.get(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url", ""),
    )
    # Normalise: replace asyncpg driver with sync psycopg driver.
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    # Also handle bare postgresql:// just in case.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    url = _get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection).

    Migrations that set ``transaction_per_migration = True`` on their module
    will each run in their own transaction.  Migrations that need to run
    outside *any* transaction (e.g. ``CREATE INDEX CONCURRENTLY``) should set
    ``transactional_ddl = False`` on their module instead — the runner will
    call ``connection.execution_options(isolation_level="AUTOCOMMIT")`` for
    those migrations only.
    """
    sync_url = _get_sync_url()

    # Override the URL that alembic.ini may have provided.
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = sync_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Honour per-migration transactional_ddl = False declarations so
            # that CREATE INDEX CONCURRENTLY can run outside a transaction.
            transaction_per_migration=True,
            # Indexes are managed via explicit migrations (0006+), not via
            # autogenerate — skip them in alembic check comparisons.
            include_object=lambda obj, name, type_, reflected, compare_to: type_ != "index",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
