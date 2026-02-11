"""Database configuration management with environment variable support."""

import os
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.session import sessionmaker as SessionMaker

from .db_models import create_database_engine, create_session_factory, init_database


class DatabaseConfig:
    """Database configuration manager."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize database configuration.

        Args:
            memory_dir: Directory for SQLite files (ignored if using PostgreSQL)
        """
        self.memory_dir = memory_dir or Path.cwd() / "memory"
        self._memory_dir_explicit = memory_dir is not None
        self._engine: Engine | None = None
        self._session_factory: SessionMaker | None = None

    def get_database_url(self) -> str:
        """
        Get database URL from environment variables or default to SQLite.

        Environment variables:
        - DATABASE_URL: Full database URL (takes precedence)
        - DB_TYPE: sqlite or postgresql
        - DB_HOST: Database host (for PostgreSQL)
        - DB_PORT: Database port (for PostgreSQL)
        - DB_NAME: Database name
        - DB_USER: Database user (for PostgreSQL)
        - DB_PASSWORD: Database password (for PostgreSQL)

        Returns:
            Database URL string
        """
        # If an explicit memory_dir is provided, always use an isolated SQLite DB there.
        # This avoids cross-test/process data leakage from environment-level DB settings.
        if self._memory_dir_explicit:
            db_name = os.getenv("DB_NAME", "conversations.db")
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            db_path = self.memory_dir / db_name
            return f"sqlite:///{db_path}"

        # Check for explicit DATABASE_URL first
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return database_url

        # Build URL from components
        db_type = os.getenv("DB_TYPE", "sqlite").lower()

        if db_type == "postgresql":
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "5432")
            name = os.getenv("DB_NAME", "storyline")
            user = os.getenv("DB_USER", "postgres")
            password = os.getenv("DB_PASSWORD", "")

            if password:
                return f"postgresql://{user}:{password}@{host}:{port}/{name}"
            else:
                return f"postgresql://{user}@{host}:{port}/{name}"

        # Default to SQLite
        db_name = os.getenv("DB_NAME", "conversations.db")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.memory_dir / db_name
        return f"sqlite:///{db_path}"

    def get_engine(self) -> Engine:
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            database_url = self.get_database_url()
            self._engine = create_database_engine(database_url)
            init_database(self._engine)
        return self._engine

    def get_session_factory(self) -> SessionMaker:
        """Get or create SQLAlchemy session factory."""
        if self._session_factory is None:
            self._session_factory = create_session_factory(self.get_engine())
        return self._session_factory

    def create_session(self) -> Session:
        """Create a new database session."""
        return self.get_session_factory()()

    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            with self.create_session() as session:
                session.execute("SELECT 1")
            return True
        except Exception:
            return False

    def dispose(self) -> None:
        """Dispose of the database engine and close all connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def __del__(self) -> None:
        """Destructor to ensure engine is disposed when object is garbage collected."""
        try:
            self.dispose()
        except Exception:
            # Ignore errors during cleanup in destructor
            pass
