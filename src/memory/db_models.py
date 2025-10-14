"""SQLAlchemy models for conversation and summary memory."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.orm.session import sessionmaker as SessionMaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    type: Mapped[str] = mapped_column(String, nullable=False, default="conversation")
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("type IN ('conversation', 'evaluation')", name="check_message_type"),
        Index("idx_character_session", "character_id", "session_id"),
        Index("idx_session_created_at", "session_id", "created_at"),
        Index("idx_session_offset", "session_id", "offset"),
        Index("idx_user_sessions", "user_id", "session_id"),
    )


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_character_session_summaries", "character_id", "session_id"),
        Index("idx_session_offsets", "session_id", "start_offset", "end_offset"),
        Index("idx_session_created_at_summaries", "session_id", "created_at"),
        Index("idx_user_summaries", "user_id", "session_id"),
    )


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Same as filename in characters folder
    character_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # All character fields as JSON
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_character_schema_version", "schema_version"),
        Index("idx_character_updated_at", "updated_at"),
        Index("idx_user_characters", "user_id"),
    )


def create_database_engine(database_url: str) -> Engine:
    """Create SQLAlchemy engine from database URL."""
    from sqlalchemy import create_engine

    return create_engine(database_url, echo=False)


def create_session_factory(engine: Engine) -> SessionMaker:
    """Create SQLAlchemy session factory."""
    return sessionmaker(bind=engine)


def init_database(engine: Engine) -> None:
    """Initialize database with all tables."""
    Base.metadata.create_all(engine)
