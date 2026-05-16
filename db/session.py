"""
Database session management module.
Provides SQLAlchemy engine and session factory.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import Pool
import logging

logger = logging.getLogger(__name__)

from db.config import DatabaseConfig

config = DatabaseConfig()

engine = create_engine(
    config.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@event.listens_for(engine, "connect")
def set_postgresql_options(dbapi_connection, connection_record):
    """Set PostgreSQL session options on new connections."""
    try:
        cursor = dbapi_connection.cursor()
        # Set statement timeout to 30 seconds
        cursor.execute("SET statement_timeout = '30000'")
        # Set lock timeout to 10 seconds
        cursor.execute("SET lock_timeout = '10000'")
        cursor.close()
    except Exception as e:
        logger.warning("Failed to set PostgreSQL options: %s", e)


Base = declarative_base()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all database tables (use with caution)."""
    Base.metadata.drop_all(bind=engine)
