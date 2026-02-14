"""SQLAlchemy models for conversation and summary memory."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.orm.session import sessionmaker as SessionMaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Message(Base):
    """Stores narration log entries (user input + narrator output)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    scenario_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'narration')", name="check_message_role"),
        Index("idx_session_created_at", "session_id", "created_at"),
        Index("idx_session_offset", "session_id", "offset"),
        Index("idx_user_sessions", "user_id", "session_id"),
        Index("idx_message_scenario", "scenario_id"),
    )


class Summary(Base):
    """Legacy summary storage — retained until old pipeline is removed."""

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

    id: Mapped[str] = mapped_column(String, primary_key=True)
    character_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    is_persona: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_character_schema_version", "schema_version"),
        Index("idx_character_updated_at", "updated_at"),
        Index("idx_user_characters", "user_id"),
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    # New fields for multi-character scenarios
    ruleset_id: Mapped[str | None] = mapped_column(String, nullable=True)
    character_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_scenario_user", "user_id"),
        Index("idx_scenario_updated_at", "updated_at"),
        Index("idx_scenario_ruleset", "ruleset_id"),
    )


# --- New simulation tables ---


class RulesetDB(Base):
    """Ruleset definitions with state schemas."""

    __tablename__ = "rulesets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rules_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state_schemas: Mapped[dict] = mapped_column(JSON, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_ruleset_user", "user_id"),
    )


class WorldLoreDB(Base):
    """Individual world lore entries with freeform tags."""

    __tablename__ = "world_lore"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_lore_user", "user_id"),
    )


class SessionDB(Base):
    """Explicit session table with world state, turn counter, snapshots."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    world_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    turn_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narration_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    location_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'paused', 'completed')", name="check_session_status"),
        Index("idx_session_user", "user_id"),
        Index("idx_session_scenario", "scenario_id"),
        Index("idx_session_status", "status"),
    )


class CharacterStateDB(Base):
    """Per-character per-session runtime state."""

    __tablename__ = "character_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    character_id: Mapped[str] = mapped_column(String, nullable=False)
    drives: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    emotional_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active_intent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    intended_destination: Mapped[str | None] = mapped_column(String, nullable=True)
    last_departure_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_charstate_session", "session_id"),
        Index("idx_charstate_session_character", "session_id", "character_id", unique=True),
    )


class EventDB(Base):
    """Per-character event stream entries (observations and reflections)."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    character_id: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    tick: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    decay_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    initial_decay: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    source_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    visibility: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("type IN ('observation', 'reflection')", name="check_event_type"),
        Index("idx_event_session_character", "session_id", "character_id"),
        Index("idx_event_session_tick", "session_id", "tick"),
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
