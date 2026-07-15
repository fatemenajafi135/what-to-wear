import os
from logging.config import fileConfig

import psycopg
from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from whattowear.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DATABASE_URL_DIRECT (5432) is preferred for migrations per research.md ->
# "Supabase transaction pooler" (DDL over the pooler can misbehave under
# autogenerate), but falls back to DATABASE_URL (pooler, 6543) when the
# direct host isn't reachable (e.g. IPv6-only routing unavailable in some
# dev sandboxes). Overrides the placeholder alembic.ini sqlalchemy.url.
load_dotenv()


def _reachable(url: str | None, timeout: float = 5.0) -> bool:
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=timeout):
            return True
    except psycopg.OperationalError:
        return False


_direct_url = os.environ.get("DATABASE_URL_DIRECT")
_pooler_url = os.environ.get("DATABASE_URL")
_db_url = _direct_url if _reachable(_direct_url) else _pooler_url
if not _db_url:
    raise RuntimeError("DATABASE_URL (or DATABASE_URL_DIRECT) is required. Set it in .env.")
_db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
# ConfigParser's interpolation treats "%" specially (used in the URL-encoded
# password); escape it so set_main_option doesn't choke on it.
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Transaction-pooler connections don't support server-side prepared
        # statements — see research.md -> "Supabase transaction pooler".
        connect_args={"prepare_threshold": None},
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
