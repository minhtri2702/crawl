"""
Database configuration module.
Loads database settings from environment variables,
with built-in defaults for standalone .exe deployment.
"""

import os
from dotenv import load_dotenv

# Try to load .env if it exists (for development), but don't require it
load_dotenv()


class DatabaseConfig:
    """Database configuration loaded from environment variables."""

    # Built-in default config for standalone .exe deployment
    DEFAULT_HOST = "100.94.58.103"
    DEFAULT_PORT = 5433
    DEFAULT_DATABASE = "crawler_db"
    DEFAULT_USERNAME = "crawler_admin"
    DEFAULT_PASSWORD = "0000"

    def __init__(self):
        self.host = os.getenv("DB_HOST", self.DEFAULT_HOST)
        self.port = int(os.getenv("DB_PORT", str(self.DEFAULT_PORT)))
        self.database = os.getenv("DB_NAME", self.DEFAULT_DATABASE)
        self.username = os.getenv("DB_USER", self.DEFAULT_USERNAME)
        self.password = os.getenv("DB_PASSWORD", self.DEFAULT_PASSWORD)

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
