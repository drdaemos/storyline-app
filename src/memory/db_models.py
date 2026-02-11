"""SQLAlchemy models for conversation and summary memory."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    meta_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    type: Mapped[str] = mapped_column(String, nullable=False, default="conversation")
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    scenario_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Optional link to scenario
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("type IN ('conversation', 'evaluation')", name="check_message_type"),
        Index("idx_character_session", "character_id", "session_id"),
        Index("idx_session_created_at", "session_id", "created_at"),
        Index("idx_session_offset", "session_id", "offset"),
        Index("idx_user_sessions", "user_id", "session_id"),
        Index("idx_message_scenario", "scenario_id"),
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

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    character_id: Mapped[str] = mapped_column(String, nullable=False)  # AI character this scenario is for
    scenario_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # Full scenario as JSON
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_scenario_character", "character_id"),
        Index("idx_scenario_user", "user_id"),
        Index("idx_scenario_updated_at", "updated_at"),
    )


class RulesetRecord(Base):
    __tablename__ = "sim_rulesets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rulebook_text: Mapped[str] = mapped_column(Text, nullable=False)
    character_stat_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    scene_state_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    mechanics_guidance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_sim_rulesets_name", "name"),
        Index("idx_sim_rulesets_updated", "updated_at"),
    )


class WorldLoreRecord(Base):
    __tablename__ = "sim_world_lore"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    lore_text: Mapped[str] = mapped_column(Text, nullable=False)
    lore_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_sim_world_lore_name", "name"),
        Index("idx_sim_world_lore_updated", "updated_at"),
    )


class SimulationScenario(Base):
    __tablename__ = "sim_scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    character_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ruleset_id: Mapped[str] = mapped_column(String, ForeignKey("sim_rulesets.id"), nullable=False)
    world_lore_id: Mapped[str] = mapped_column(String, ForeignKey("sim_world_lore.id"), nullable=False)
    scene_seed: Mapped[dict] = mapped_column(JSON, nullable=False)
    stakes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tone: Mapped[str] = mapped_column(String, nullable=False, default="")
    intro_seed: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_sim_scenarios_user", "user_id"),
        Index("idx_sim_scenarios_character", "character_id"),
        Index("idx_sim_scenarios_ruleset", "ruleset_id"),
        Index("idx_sim_scenarios_world_lore", "world_lore_id"),
    )


class SimulationSession(Base):
    __tablename__ = "sim_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str | None] = mapped_column(String, ForeignKey("sim_scenarios.id"), nullable=True)
    ruleset_id: Mapped[str] = mapped_column(String, ForeignKey("sim_rulesets.id"), nullable=False)
    world_lore_id: Mapped[str] = mapped_column(String, ForeignKey("sim_world_lore.id"), nullable=False)
    current_scene_id: Mapped[str] = mapped_column(String, nullable=False)
    current_turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    small_model_key: Mapped[str] = mapped_column(String, nullable=False)
    large_model_key: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_sim_sessions_user", "user_id"),
        Index("idx_sim_sessions_scenario", "scenario_id"),
        Index("idx_sim_sessions_current_scene", "current_scene_id"),
    )


class SimulationSessionCharacter(Base):
    __tablename__ = "sim_session_characters"

    session_id: Mapped[str] = mapped_column(String, ForeignKey("sim_sessions.id"), primary_key=True)
    character_id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # npc | user_persona
    stat_block: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_sim_session_characters_role", "role"),
    )


class SimulationScenarioCharacter(Base):
    __tablename__ = "sim_scenario_characters"

    scenario_id: Mapped[str] = mapped_column(String, ForeignKey("sim_scenarios.id"), primary_key=True)
    character_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class SimulationScene(Base):
    __tablename__ = "sim_scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sim_sessions.id"), nullable=False)
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("session_id", "scene_index", name="uq_sim_scene_session_index"),
        Index("idx_sim_scenes_session_created", "session_id", "created_at"),
    )


class SimulationObservation(Base):
    __tablename__ = "sim_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sim_sessions.id"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("sim_scenes.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False)
    reinforcement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("importance >= 1 AND importance <= 5", name="check_sim_observation_importance"),
        Index("idx_sim_observations_session_char", "session_id", "character_id"),
        Index("idx_sim_observations_session_created", "session_id", "created_at"),
    )


class SimulationAction(Base):
    __tablename__ = "sim_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sim_sessions.id"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("sim_scenes.id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_sim_actions_session_turn", "session_id", "turn_index"),
        Index("idx_sim_actions_scene_actor", "scene_id", "actor_id"),
    )


class SimulationSceneRelation(Base):
    __tablename__ = "sim_scene_relations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sim_sessions.id"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("sim_scenes.id"), nullable=False)
    character_a_id: Mapped[str] = mapped_column(String, nullable=False)
    character_b_id: Mapped[str] = mapped_column(String, nullable=False)
    trust: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tension: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closeness: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("scene_id", "character_a_id", "character_b_id", name="uq_sim_scene_relation_pair"),
        Index("idx_sim_scene_relations_session", "session_id"),
    )


class SimulationTurnEvent(Base):
    __tablename__ = "sim_turn_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sim_sessions.id"), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(String, ForeignKey("sim_scenes.id"), nullable=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    step_name: Mapped[str] = mapped_column(String, nullable=False)
    user_action_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_key: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_sim_turn_events_session_turn", "session_id", "turn_index"),
        Index("idx_sim_turn_events_type", "event_type"),
        UniqueConstraint("session_id", "user_action_id", name="uq_sim_session_user_action_id"),
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
    _run_sqlite_compat_migrations(engine)


def _run_sqlite_compat_migrations(engine: Engine) -> None:
    """Best-effort additive migrations for existing SQLite DB files."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        existing_tables = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "messages" in existing_tables:
            cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(messages)").fetchall()}
            if "scenario_id" not in cols:
                connection.exec_driver_sql("ALTER TABLE messages ADD COLUMN scenario_id VARCHAR")
            if "meta_text" not in cols:
                connection.exec_driver_sql("ALTER TABLE messages ADD COLUMN meta_text TEXT")
        if "sim_scenarios" in existing_tables:
            cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(sim_scenarios)").fetchall()}
            if "character_id" not in cols:
                connection.exec_driver_sql("ALTER TABLE sim_scenarios ADD COLUMN character_id VARCHAR")
                connection.exec_driver_sql("UPDATE sim_scenarios SET character_id = '' WHERE character_id IS NULL")
            if "scenario_data" not in cols:
                connection.exec_driver_sql("ALTER TABLE sim_scenarios ADD COLUMN scenario_data JSON")
                connection.exec_driver_sql("UPDATE sim_scenarios SET scenario_data = '{}' WHERE scenario_data IS NULL")
