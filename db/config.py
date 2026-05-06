"""
Database configuration module.
Loads database settings from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfig:
    """Database configuration loaded from environment variables."""

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5433"))
        self.database = os.getenv("DB_NAME", "crawler_db")
        self.username = os.getenv("DB_USER", "crawler_admin")
        self.password = os.getenv("DB_PASSWORD", "0000")

    @property
    def database_url(self) -> str:
        """Get the SQLAlchemy database URL."""
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def __repr__(self) -> str:
        return (
            f"DatabaseConfig(host={self.host}, port={self.port}, "
            f"database={self.database}, username={self.username})"
        )
