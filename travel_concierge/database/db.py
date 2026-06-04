# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Database engine and session factory for Travel Concierge.

Usage
-----
    from travel_concierge.database.db import get_session, init_db

    # Create all tables (run once at startup / in tests)
    init_db()

    # Use a session
    with get_session() as session:
        session.add(guest)
        session.commit()

Configuration
-------------
Set the ``DATABASE_URL`` environment variable to override the default
SQLite file.  Examples::

    DATABASE_URL=sqlite:///travel_concierge.db          # default (local dev)
    DATABASE_URL=postgresql+psycopg2://user:pw@host/db  # production
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from travel_concierge.database.models import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# Absolute path so the same DB file is used regardless of working directory.
_PROJECT_ROOT = os.path.dirname(        # .../deploy-travel-concierge
    os.path.dirname(                    # .../travel_concierge
        os.path.dirname(                # .../database
            os.path.abspath(__file__)
        )
    )
)
_DEFAULT_URL = f"sqlite:///{os.path.join(_PROJECT_ROOT, 'travel_concierge.db')}"

def _build_engine() -> Engine:
    url = os.getenv("DATABASE_URL", _DEFAULT_URL)
    connect_args = {}
    if url.startswith("sqlite"):
        # Required for SQLite when used with multiple threads (e.g. ADK async)
        connect_args["check_same_thread"] = False
    # Redact credentials from the log line
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info("Building DB engine: %s", safe_url)
    engine = create_engine(url, echo=False, connect_args=connect_args)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_fk_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine: Engine = _build_engine()

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables defined in models.py (idempotent)."""
    logger.info("Initialising database schema (create_all)")
    Base.metadata.create_all(bind=engine)
    logger.debug("Schema initialisation complete")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a transactional database session.

    Commits on clean exit, rolls back on exception, and always closes.

    Example::

        with get_session() as session:
            session.add(some_object)
            # commit is called automatically
    """
    session: Session = SessionLocal()
    logger.debug("Session opened")
    try:
        yield session
        session.commit()
        logger.debug("Session committed")
    except Exception as exc:
        logger.warning("Session rollback due to: %s", exc)
        session.rollback()
        raise
    finally:
        session.close()
        logger.debug("Session closed")
