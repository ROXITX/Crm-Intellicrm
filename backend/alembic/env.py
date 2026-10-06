from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401  (register tables)
from app.core.config import settings
from app.core.db import Base

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # full-text GIN indexes are expression indexes created by hand in migration 0003
    return not (type_ == "index" and name and name.endswith("_fts"))


def run_migrations_online():
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
