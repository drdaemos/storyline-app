import asyncio
import json
import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.auth import UserIdDep
from src.character_creation_assistant import CharacterCreationAssistant
from src.character_creator import CharacterCreator
from src.character_loader import CharacterLoader
from src.character_manager import CharacterManager
from src.memory.character_state_repository import CharacterStateRepository
from src.memory.conversation_memory import ConversationMemory
from src.memory.event_repository import EventRepository
from src.memory.ruleset_registry import RulesetRegistry
from src.memory.scenario_registry import ScenarioRegistry
from src.memory.session_repository import SessionRepository
from src.memory.world_lore_registry import WorldLoreRegistry
from src.models.api_models import (
    CharacterCreationRequest,
    CharacterCreationStreamEvent,
    CharacterSummary,
    CreateCharacterRequest,
    CreateCharacterResponse,
    CreateRulesetRequest,
    CreateWorldLoreRequest,
    GenerateCharacterRequest,
    GenerateCharacterResponse,
    HealthStatus,
    ListScenariosResponse,
    PartialScenario,
    ProcessorOption,
    ProcessorOptionsResponse,
    RulesetSummary,
    SaveScenarioRequest,
    SaveScenarioResponse,
    Scenario,
    ScenarioCreationRequest,
    ScenarioCreationStreamEvent,
    ScenarioSummary,
    SessionCharacterSummary,
    SessionDetails,
    SessionInfo,
    SessionMessage,
    SessionStateResponse,
    StartSessionRequest,
    StartSessionResponse,
    TurnRequest,
    WorldLoreSummary,
)
from src.models.character import Character, PartialCharacter
from src.models.prompt_processor_factory import PromptProcessorFactory
from src.models.simulation import Ruleset
from src.pipeline.session_initializer import SessionInitializer
from src.pipeline.turn_pipeline import TurnPipeline
from src.scenario_creation_assistant import ScenarioCreationAssistant
from src.services.event_stream_service import EventStreamService
from src.services.ruleset_service import RulesetService
from src.services.session_state_service import SessionStateService

app = FastAPI(title="Storyline API", description="Interactive character chat API", version="0.2.0")

# Mount static files for the web interface
static_dir = Path(__file__).parent.parent / "static" / "assets"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

# --- Shared service instances ---
character_loader = CharacterLoader()
character_manager = CharacterManager()
conversation_memory = ConversationMemory()
scenario_registry = ScenarioRegistry()
ruleset_registry = RulesetRegistry()
world_lore_registry = WorldLoreRegistry()
session_repository = SessionRepository()
character_state_repository = CharacterStateRepository()
event_repository = EventRepository()

# Composed services
session_state_service = SessionStateService(session_repository, character_state_repository)
ruleset_service = RulesetService(ruleset_registry)
event_stream_service = EventStreamService(event_repository)


# ───────────────────────────── Health & Info ──────────────────────────────


@app.get("/health")
async def health_check() -> HealthStatus:
    """Health check endpoint that verifies database connectivity."""
    conversation_status = "ok"
    overall_status = "healthy"
    details: dict[str, str] = {}

    try:
        mem = ConversationMemory()
        if mem.health_check():
            details["conversation_db_status"] = "connected"
        else:
            conversation_status = "error"
            overall_status = "unhealthy"
            details["conversation_error"] = "Database connectivity failed"
    except Exception as e:
        conversation_status = "error"
        overall_status = "unhealthy"
        details["conversation_error"] = str(e)

    return HealthStatus(status=overall_status, conversation_memory=conversation_status, details=details)


@app.get("/api")
async def api_info() -> dict[str, str]:
    """API information endpoint."""
    return {"message": "Storyline API - Interactive Character Chat", "version": "0.2.0"}


@app.get("/api/prompt-processors")
async def list_prompt_processors(_user_id: UserIdDep) -> ProcessorOptionsResponse:
    """List available prompt processor IDs for Large/Mini selection."""
    try:
        processor_options = PromptProcessorFactory.get_available_processor_options()
        return ProcessorOptionsResponse(
            processor_types=[option.id for option in processor_options],
            processor_options=[
                ProcessorOption(id=option.id, display_name=option.display_name)
                for option in processor_options
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list prompt processors: {str(e)}") from e


# ───────────────────────────── Characters ─────────────────────────────


@app.get("/api/characters")
async def list_characters(user_id: UserIdDep) -> list[CharacterSummary]:
    """List available characters with their basic info."""
    try:
        return character_loader.list_character_summaries(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list characters: {str(e)}") from e


@app.get("/api/personas")
async def list_personas(user_id: UserIdDep) -> list[CharacterSummary]:
    """List available persona characters with their basic info."""
    try:
        return character_loader.list_persona_summaries(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list personas: {str(e)}") from e


@app.get("/api/characters/{character_name}")
async def get_character_info(character_name: str, user_id: UserIdDep) -> dict:
    """Get information about a specific character."""
    try:
        character_info = character_loader.get_character_info(character_name, user_id)
        if not character_info:
            raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")
        return character_info.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get character info: {str(e)}") from e


@app.post("/api/characters")
async def create_character(request: CreateCharacterRequest, user_id: UserIdDep) -> CreateCharacterResponse:
    """Create a new character from either structured data or freeform YAML text."""
    try:
        from src.models.character import Character

        if request.is_yaml_text:
            if not isinstance(request.data, str):
                raise HTTPException(status_code=400, detail="When is_yaml_text is true, data must be a string")
            character_data = character_manager.validate_yaml_text(request.data)
        else:
            if not isinstance(request.data, Character):
                raise HTTPException(status_code=400, detail="When is_yaml_text is false, data must be structured character data")
            character_data = request.data.model_dump()

        filename = character_manager.create_character_file(character_data, user_id=user_id, is_persona=request.is_persona)
        return CreateCharacterResponse(message=f"Character '{character_data['name']}' created successfully", character_filename=filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create character: {str(e)}") from e


@app.put("/api/characters/{character_id}")
async def update_character(character_id: str, request: CreateCharacterRequest, user_id: UserIdDep) -> CreateCharacterResponse:
    """Update an existing character's data."""
    try:
        from src.models.character import Character

        if request.is_yaml_text:
            if not isinstance(request.data, str):
                raise HTTPException(status_code=400, detail="When is_yaml_text is true, data must be a string")
            character_data = character_manager.validate_yaml_text(request.data)
        else:
            if not isinstance(request.data, Character):
                raise HTTPException(status_code=400, detail="When is_yaml_text is false, data must be structured character data")
            character_data = request.data.model_dump()

        updated_character_id = character_manager.update_character(character_id, character_data, user_id=user_id)
        return CreateCharacterResponse(message=f"Character '{character_data['name']}' updated successfully", character_filename=updated_character_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update character: {str(e)}") from e


@app.post("/api/characters/generate")
async def generate_character(request: GenerateCharacterRequest, user_id: UserIdDep) -> GenerateCharacterResponse:
    """Generate a complete character from partial character data using AI."""
    try:
        processor = PromptProcessorFactory.create_processor(request.processor_type)
        character_creator = CharacterCreator(prompt_processor=processor, character_manager=character_manager)

        original_fields = set(request.partial_character.keys())
        complete_character = character_creator.generate(request.partial_character)
        all_character_fields = set(complete_character.model_dump().keys())

        generated_fields = []
        character_dict = complete_character.model_dump()
        for field in all_character_fields:
            if field not in original_fields or not request.partial_character.get(field):
                if character_dict.get(field):
                    generated_fields.append(field)

        return GenerateCharacterResponse(character=complete_character, generated_fields=generated_fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate character: {str(e)}") from e


@app.post("/api/characters/create-stream")
async def create_character_stream(request: CharacterCreationRequest, _user_id: UserIdDep) -> StreamingResponse:
    """Interactive character creation with AI assistant via Server-Sent Events."""
    try:
        processor = PromptProcessorFactory.create_processor(request.processor_type)
        assistant = CharacterCreationAssistant(prompt_processor=processor)

        async def generate_sse_response() -> AsyncGenerator[str, None]:
            try:
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                ai_response_parts: list[str] = []
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    ai_response_parts.append(chunk)
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                async def run_assistant() -> tuple[str, PartialCharacter]:
                    try:
                        response, updates = await loop.run_in_executor(
                            None,
                            lambda: assistant.process_message(
                                user_message=request.user_message,
                                current_character=request.current_character,
                                ruleset_context=request.ruleset_context,
                                conversation_history=request.conversation_history,
                                streaming_callback=streaming_callback,
                            ),
                        )
                        return response, updates
                    finally:
                        await chunk_queue.put(None)

                assistant_task = asyncio.create_task(run_assistant())

                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:
                        break
                    clean_chunk = re.sub(r"<character_update>[\s\S]*?</character_update>", "", chunk)
                    if clean_chunk:
                        event_data = CharacterCreationStreamEvent(type="message", message=clean_chunk)
                        yield f"data: {event_data.model_dump_json()}\n\n"

                full_response, updated_character = await assistant_task
                if updated_character != request.current_character:
                    update_event = CharacterCreationStreamEvent(type="update", updates=updated_character)
                    yield f"data: {update_event.model_dump_json()}\n\n"

                complete_event = CharacterCreationStreamEvent(type="complete")
                yield f"data: {complete_event.model_dump_json()}\n\n"
            except Exception as e:
                error_event = CharacterCreationStreamEvent(type="error", error=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process character creation: {str(e)}") from e


# ───────────────────────────── Scenarios ──────────────────────────────


@app.post("/api/scenarios/create-stream")
async def create_scenario_stream(request: ScenarioCreationRequest, user_id: UserIdDep) -> StreamingResponse:
    """Interactive scenario creation with AI assistant via Server-Sent Events."""
    try:
        current_scenario = request.current_scenario
        character_ids = current_scenario.character_ids
        if not character_ids:
            raise HTTPException(status_code=422, detail="current_scenario.character_ids must contain at least one ID")

        characters: list[Character] = []
        for cid in character_ids:
            char = character_loader.load_character(cid, user_id)
            if not char:
                raise HTTPException(status_code=404, detail=f"Character '{cid}' not found")
            characters.append(char)

        persona = None
        if request.persona_id:
            persona = character_loader.load_character(request.persona_id, user_id)

        if not current_scenario.ruleset_id:
            raise HTTPException(status_code=422, detail="current_scenario.ruleset_id is required")

        ruleset_service = RulesetService(ruleset_registry)
        ruleset = ruleset_service.load_ruleset(current_scenario.ruleset_id, user_id)
        if not ruleset:
            raise HTTPException(status_code=404, detail=f"Ruleset '{current_scenario.ruleset_id}' not found")

        if request.persona_id and not current_scenario.persona_id:
            current_scenario = current_scenario.model_copy(update={"persona_id": request.persona_id})

        processor = PromptProcessorFactory.create_processor(request.processor_type)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        available_personas = request.available_personas

        async def generate_sse_response() -> AsyncGenerator[str, None]:
            try:
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                ai_response_parts: list[str] = []
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    ai_response_parts.append(chunk)
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                async def run_assistant() -> tuple[str, PartialScenario]:
                    try:
                        response, updates = await loop.run_in_executor(
                            None,
                            lambda: assistant.process_message(
                                user_message=request.user_message,
                                current_scenario=current_scenario,
                                characters=characters,
                                persona=persona,
                                available_personas=available_personas,
                                ruleset=ruleset,
                                conversation_history=request.conversation_history,
                                streaming_callback=streaming_callback,
                            ),
                        )
                        return response, updates
                    finally:
                        await chunk_queue.put(None)

                assistant_task = asyncio.create_task(run_assistant())

                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:
                        break
                    clean_chunk = re.sub(r"<scenario_update>[\s\S]*?</scenario_update>", "", chunk)
                    if clean_chunk:
                        event_data = ScenarioCreationStreamEvent(type="message", message=clean_chunk)
                        yield f"data: {event_data.model_dump_json()}\n\n"

                full_response, updated_scenario = await assistant_task
                if updated_scenario != current_scenario:
                    update_event = ScenarioCreationStreamEvent(type="update", updates=updated_scenario)
                    yield f"data: {update_event.model_dump_json()}\n\n"

                complete_event = ScenarioCreationStreamEvent(type="complete")
                yield f"data: {complete_event.model_dump_json()}\n\n"
            except Exception as e:
                error_event = ScenarioCreationStreamEvent(type="error", error=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process scenario creation: {str(e)}") from e


@app.post("/api/scenarios/save")
async def save_scenario(request: SaveScenarioRequest, user_id: UserIdDep) -> SaveScenarioResponse:
    """Save a completed scenario to the database."""
    try:
        if not request.scenario.summary or not request.scenario.intro_message:
            raise HTTPException(status_code=400, detail="Scenario must have summary and intro_message")
        if not request.scenario.character_ids:
            raise HTTPException(status_code=400, detail="Scenario must have at least one character_id")
        if not request.scenario.ruleset_id:
            raise HTTPException(status_code=400, detail="Scenario must have a ruleset_id")

        scenario_id = scenario_registry.save_scenario(
            scenario_data=request.scenario.model_dump(),
            scenario_id=request.scenario_id,
            user_id=user_id,
            ruleset_id=request.scenario.ruleset_id,
            character_ids=request.scenario.character_ids,
        )
        return SaveScenarioResponse(scenario_id=scenario_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scenario: {str(e)}") from e


@app.get("/api/scenarios/list")
async def list_scenarios(user_id: UserIdDep) -> ListScenariosResponse:
    """List all saved scenarios for the user."""
    try:
        scenarios = scenario_registry.get_all_scenarios(user_id)
        scenario_summaries = [
            ScenarioSummary(
                id=s["id"],
                summary=s["scenario_data"].get("summary", "Untitled"),
                character_ids=s.get("character_ids") or [],
                ruleset_id=s.get("ruleset_id") or "",
                created_at=s["created_at"],
                updated_at=s["updated_at"],
            )
            for s in scenarios
        ]
        return ListScenariosResponse(scenarios=scenario_summaries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list scenarios: {str(e)}") from e


@app.get("/api/scenarios/detail/{scenario_id}")
async def get_scenario_detail(scenario_id: str, user_id: UserIdDep) -> Scenario:
    """Get a specific scenario by ID."""
    try:
        scenario_data = scenario_registry.get_scenario(scenario_id, user_id)
        if not scenario_data:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
        return Scenario(**scenario_data["scenario_data"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scenario: {str(e)}") from e


@app.delete("/api/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str, user_id: UserIdDep) -> dict[str, str]:
    """Delete a scenario by ID."""
    try:
        if not scenario_registry.scenario_exists(scenario_id, user_id):
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
        deleted = scenario_registry.delete_scenario(scenario_id, user_id)
        if not deleted:
            raise HTTPException(status_code=403, detail="Cannot delete scenario - you may not have permission")
        return {"message": f"Scenario '{scenario_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete scenario: {str(e)}") from e


# ───────────────────────────── Rulesets ───────────────────────────────


@app.get("/api/rulesets")
async def list_rulesets(user_id: UserIdDep) -> list[RulesetSummary]:
    """List all rulesets for the user."""
    try:
        rulesets = ruleset_registry.get_all_rulesets(user_id)
        return [
            RulesetSummary(
                id=r["id"],
                name=r["name"],
                drive_count=len(r.get("state_schemas", {}).get("drives", [])),
                skill_count=len(r.get("state_schemas", {}).get("skills", [])),
                created_at=r.get("created_at", ""),
            )
            for r in rulesets
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list rulesets: {str(e)}") from e


@app.post("/api/rulesets")
async def create_ruleset(request: CreateRulesetRequest, user_id: UserIdDep) -> dict[str, str]:
    """Create a new ruleset."""
    try:
        ruleset_id = ruleset_registry.save_ruleset(
            name=request.ruleset.name,
            rules_text=request.ruleset.rules_text,
            state_schemas=request.ruleset.state_schemas.model_dump(),
            config=request.ruleset.config.model_dump(),
            user_id=user_id,
        )
        return {"id": ruleset_id, "message": "Ruleset created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create ruleset: {str(e)}") from e


@app.get("/api/rulesets/{ruleset_id}")
async def get_ruleset(ruleset_id: str, user_id: UserIdDep) -> dict[str, Any]:
    """Get a specific ruleset by ID."""
    try:
        ruleset = ruleset_registry.get_ruleset(ruleset_id, user_id)
        if not ruleset:
            raise HTTPException(status_code=404, detail=f"Ruleset '{ruleset_id}' not found")
        return ruleset
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ruleset: {str(e)}") from e


@app.put("/api/rulesets/{ruleset_id}")
async def update_ruleset(ruleset_id: str, request: CreateRulesetRequest, user_id: UserIdDep) -> dict[str, str]:
    """Update an existing ruleset."""
    try:
        existing = ruleset_registry.get_ruleset(ruleset_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Ruleset '{ruleset_id}' not found")
        ruleset_registry.save_ruleset(
            name=request.ruleset.name,
            rules_text=request.ruleset.rules_text,
            state_schemas=request.ruleset.state_schemas.model_dump(),
            config=request.ruleset.config.model_dump(),
            ruleset_id=ruleset_id,
            user_id=user_id,
        )
        return {"id": ruleset_id, "message": "Ruleset updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ruleset: {str(e)}") from e


@app.delete("/api/rulesets/{ruleset_id}")
async def delete_ruleset(ruleset_id: str, user_id: UserIdDep) -> dict[str, str]:
    """Delete a ruleset by ID."""
    try:
        deleted = ruleset_registry.delete_ruleset(ruleset_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Ruleset '{ruleset_id}' not found")
        return {"message": f"Ruleset '{ruleset_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete ruleset: {str(e)}") from e


# ───────────────────────────── World Lore ─────────────────────────────


@app.get("/api/world-lore")
async def list_world_lore(user_id: UserIdDep) -> list[WorldLoreSummary]:
    """List all world lore entries for the user."""
    try:
        entries = world_lore_registry.get_all_lore(user_id)
        return [
            WorldLoreSummary(
                id=e["id"],
                name=e["name"],
                tags=e.get("tags", []),
                content_preview=e.get("content", "")[:100],
            )
            for e in entries
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list world lore: {str(e)}") from e


@app.post("/api/world-lore")
async def create_world_lore(request: CreateWorldLoreRequest, user_id: UserIdDep) -> dict[str, str]:
    """Create a new world lore entry."""
    try:
        lore_id = world_lore_registry.save_lore(
            name=request.lore.name,
            content=request.lore.content,
            tags=request.lore.tags,
            user_id=user_id,
        )
        return {"id": lore_id, "message": "World lore created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create world lore: {str(e)}") from e


@app.get("/api/world-lore/tags")
async def get_world_lore_tags(user_id: UserIdDep) -> list[str]:
    """Get all unique tags across world lore entries."""
    try:
        return world_lore_registry.get_all_tags(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tags: {str(e)}") from e


@app.get("/api/world-lore/{lore_id}")
async def get_world_lore(lore_id: str, user_id: UserIdDep) -> dict[str, Any]:
    """Get a specific world lore entry by ID."""
    try:
        lore = world_lore_registry.get_lore(lore_id, user_id)
        if not lore:
            raise HTTPException(status_code=404, detail=f"World lore '{lore_id}' not found")
        return lore
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get world lore: {str(e)}") from e


@app.put("/api/world-lore/{lore_id}")
async def update_world_lore(lore_id: str, request: CreateWorldLoreRequest, user_id: UserIdDep) -> dict[str, str]:
    """Update an existing world lore entry."""
    try:
        existing = world_lore_registry.get_lore(lore_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"World lore '{lore_id}' not found")
        world_lore_registry.save_lore(
            name=request.lore.name,
            content=request.lore.content,
            tags=request.lore.tags,
            lore_id=lore_id,
            user_id=user_id,
        )
        return {"id": lore_id, "message": "World lore updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update world lore: {str(e)}") from e


@app.delete("/api/world-lore/{lore_id}")
async def delete_world_lore(lore_id: str, user_id: UserIdDep) -> dict[str, str]:
    """Delete a world lore entry by ID."""
    try:
        deleted = world_lore_registry.delete_lore(lore_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"World lore '{lore_id}' not found")
        return {"message": f"World lore '{lore_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete world lore: {str(e)}") from e


# ───────────────────────────── Sessions ───────────────────────────────


def _build_session_info_list(
    user_id: str,
    allowed_scenario_ids: set[str] | None = None,
) -> list[SessionInfo]:
    """Build SessionInfo rows, optionally filtering to an allowed scenario set."""
    mem = ConversationMemory()
    sessions: list[SessionInfo] = []
    scenario_name_cache: dict[str, str | None] = {}

    user_sessions = mem.get_user_sessions(user_id, limit=50)

    for session_info in user_sessions:
        session_id = session_info["session_id"]
        session_db = session_repository.get_session(session_id, user_id)
        scenario_id = session_db.get("scenario_id") if session_db else None

        if not scenario_id:
            scenario_id = mem.get_session_scenario_id(session_id, user_id)

        if allowed_scenario_ids is not None:
            if not scenario_id or scenario_id not in allowed_scenario_ids:
                continue

        last_character_response = None
        try:
            recent_messages = mem.get_recent_messages(session_id, user_id, limit=1)
            last_character_response = recent_messages[0]["content"] if len(recent_messages) > 0 else None
        except Exception:
            last_character_response = None

        scenario_name = None
        if scenario_id:
            if scenario_id not in scenario_name_cache:
                scenario_data = scenario_registry.get_scenario(scenario_id, user_id)
                scenario_name_cache[scenario_id] = (
                    scenario_data["scenario_data"].get("summary", "Untitled")
                    if scenario_data
                    else None
                )
            scenario_name = scenario_name_cache[scenario_id]

        turn_count = session_db.get("turn_counter") if session_db else None

        sessions.append(
            SessionInfo(
                session_id=session_id,
                character_name=scenario_name or "Session",
                message_count=session_info["message_count"],
                last_message_time=session_info["last_message_time"],
                last_character_response=last_character_response,
                scenario_name=scenario_name,
                turn_count=turn_count,
            )
        )

    return sessions


def _normalize_session_status(status: str | None) -> str | None:
    """Normalize session status query params and validate supported values."""
    if status is None:
        return None

    normalized = status.strip().lower()
    if normalized == "complete":
        normalized = "completed"

    if normalized not in {"active", "paused", "completed"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Allowed values: active, paused, completed",
        )

    return normalized


def _build_character_session_info_list(
    user_id: str,
    scenario_ids: set[str],
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[SessionInfo]:
    """Build character-scoped session list using DB-level filtering and pagination."""
    mem = ConversationMemory()
    sessions: list[SessionInfo] = []
    scenario_name_cache: dict[str, str | None] = {}

    session_rows = session_repository.get_user_sessions(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
        scenario_ids=scenario_ids,
    )

    for session_row in session_rows:
        session_id = session_row["id"]
        scenario_id = session_row.get("scenario_id")

        session_details = mem.get_session_details(session_id, user_id)
        message_count = session_details["message_count"] if session_details else 0
        last_message_time = session_details["last_message_time"] if session_details else session_row["updated_at"]

        last_character_response = None
        try:
            recent_messages = mem.get_recent_messages(session_id, user_id, limit=1)
            last_character_response = recent_messages[0]["content"] if len(recent_messages) > 0 else None
        except Exception:
            last_character_response = None

        scenario_name = None
        if scenario_id:
            if scenario_id not in scenario_name_cache:
                scenario_data = scenario_registry.get_scenario(scenario_id, user_id)
                scenario_name_cache[scenario_id] = (
                    scenario_data["scenario_data"].get("summary", "Untitled")
                    if scenario_data
                    else None
                )
            scenario_name = scenario_name_cache[scenario_id]

        sessions.append(
            SessionInfo(
                session_id=session_id,
                character_name=scenario_name or "Session",
                message_count=message_count,
                last_message_time=last_message_time,
                last_character_response=last_character_response,
                scenario_name=scenario_name,
                turn_count=session_row.get("turn_counter"),
            )
        )

    return sessions


@app.get("/api/characters/{character_id}/sessions")
async def list_sessions_for_character(
    character_id: str,
    user_id: UserIdDep,
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SessionInfo]:
    """List sessions that include the given character (as NPC or persona)."""
    try:
        character_info = character_loader.get_character_info(character_id, user_id)
        if not character_info:
            raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

        normalized_status = _normalize_session_status(status)
        scenario_ids = scenario_registry.get_scenario_ids_for_character(character_id, user_id)
        if len(scenario_ids) == 0:
            return []

        return _build_character_session_info_list(
            user_id=user_id,
            scenario_ids=scenario_ids,
            status=normalized_status,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list character sessions: {str(e)}") from e


@app.get("/api/sessions")
async def list_sessions(user_id: UserIdDep) -> list[SessionInfo]:
    """List all sessions from conversation memory."""
    try:
        sessions = _build_session_info_list(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}") from e

    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, user_id: UserIdDep) -> SessionDetails:
    """Get details of a specific session."""
    memory = ConversationMemory()
    session_details = memory.get_session_details(session_id, user_id)
    if not session_details or session_details.get("message_count", 0) == 0:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        session_messages = memory.get_recent_messages(session_id, user_id, limit=50)
        last_messages = [
            SessionMessage(role=msg["role"], content=msg["content"], created_at=msg["created_at"])
            for msg in session_messages
        ]
        return SessionDetails(
            session_id=session_id,
            character_name="Session",
            message_count=session_details["message_count"],
            last_messages=last_messages,
            last_message_time=session_details["last_message_time"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session details: {str(e)}") from e


@app.get("/api/sessions/{session_id}/state")
async def get_session_state(session_id: str, user_id: UserIdDep) -> SessionStateResponse:
    """Get the full simulation state for a session."""
    try:
        world_state = session_state_service.get_world_state(session_id, user_id)
        if not world_state:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        turn_counter = session_state_service.get_turn_counter(session_id, user_id)
        all_states = session_state_service.get_all_character_states(session_id)
        narration_history = session_state_service.get_narration_history(session_id, user_id)

        session_db = session_repository.get_session(session_id, user_id)
        status = session_db.get("status", "active") if session_db else "active"

        character_states = {
            cid: state.model_dump() for cid, state in all_states.items()
        }

        return SessionStateResponse(
            session_id=session_id,
            world_state=world_state,
            turn_counter=turn_counter,
            status=status,
            character_states=character_states,
            narration_history=narration_history,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session state: {str(e)}") from e


@app.get("/api/sessions/{session_id}/characters")
async def get_session_characters(session_id: str, user_id: UserIdDep) -> list[SessionCharacterSummary]:
    """Get character summaries for a session."""
    try:
        world_state = session_state_service.get_world_state(session_id, user_id)
        if not world_state:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        all_states = session_state_service.get_all_character_states(session_id)
        summaries: list[SessionCharacterSummary] = []

        for char_id, state in all_states.items():
            char_info = character_loader.get_character_info(char_id, user_id)
            char_name = char_info.name if char_info else char_id

            summaries.append(SessionCharacterSummary(
                character_id=char_id,
                character_name=char_name,
                is_present=state.is_present,
                drives=state.drives,
                active_intent_goal=state.active_intent.goal if state.active_intent else None,
            ))

        return summaries
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session characters: {str(e)}") from e


@app.get("/api/sessions/{session_id}/persona")
async def get_session_persona(session_id: str, user_id: UserIdDep) -> dict[str, str | None]:
    """Get the persona information for a session."""
    try:
        session_details = conversation_memory.get_session_details(session_id, user_id)
        if not session_details or session_details.get("message_count", 0) == 0:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        scenario_id = conversation_memory.get_session_scenario_id(session_id, user_id)
        if not scenario_id:
            return {"persona_id": None, "persona_name": None}

        scenario_data = scenario_registry.get_scenario(scenario_id, user_id)
        if not scenario_data:
            return {"persona_id": None, "persona_name": None}

        persona_id = scenario_data["scenario_data"].get("persona_id")
        if not persona_id:
            return {"persona_id": None, "persona_name": None}

        try:
            persona = character_loader.load_character(persona_id, user_id)
            return {"persona_id": persona_id, "persona_name": persona.name}
        except FileNotFoundError:
            return {"persona_id": persona_id, "persona_name": None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session persona: {str(e)}") from e


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str, user_id: UserIdDep) -> dict[str, str]:
    """Clear a specific session."""
    memory = ConversationMemory()
    messages = memory.get_session_messages(session_id, user_id, limit=1)
    if len(messages) == 0:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        memory.delete_session(session_id, user_id)
        # Also clean up simulation state if it exists
        session_repository.delete_session(session_id, user_id)
        return {"message": f"Session '{session_id}' cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}") from e


@app.post("/api/sessions/start")
async def start_session(request: StartSessionRequest, user_id: UserIdDep) -> StartSessionResponse:
    """Start a new simulation session from a stored scenario."""
    try:
        initializer = SessionInitializer(
            session_state_service=session_state_service,
            ruleset_service=ruleset_service,
            event_stream_service=event_stream_service,
            character_loader=character_loader,
            scenario_registry=scenario_registry,
            conversation_memory=conversation_memory,
            world_lore_registry=world_lore_registry,
        )

        result = initializer.initialize(
            scenario_id=request.scenario_id,
            user_id=user_id,
        )

        return StartSessionResponse(session_id=result["session_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}") from e


# ───────────────────────────── Turn Pipeline ──────────────────────────


@app.post("/api/turn")
async def execute_turn(request: TurnRequest, user_id: UserIdDep) -> StreamingResponse:
    """Execute a simulation turn with streaming narration via Server-Sent Events.

    SSE events:
    - {"type": "status", "step": "..."}
    - {"type": "narration_chunk", "text": "..."}
    - {"type": "narration_complete", "text": "..."}
    - {"type": "continuation_options", "options": [...]}
    - {"type": "turn_complete", "turn": int}
    - {"type": "error", "message": "..."}
    """
    try:
        # Load ruleset for this session if one exists
        session_db = session_repository.get_session(request.session_id, user_id)
        if not session_db:
            raise HTTPException(status_code=404, detail=f"Session '{request.session_id}' not found")

        scenario_data = scenario_registry.get_scenario(session_db.get("scenario_id", ""), user_id)
        ruleset: Ruleset | None = None
        if scenario_data:
            ruleset_id = scenario_data.get("scenario_data", {}).get("ruleset_id", "")
            if ruleset_id:
                ruleset = ruleset_service.load_ruleset(ruleset_id, user_id)

        # Create processors
        large_processor = PromptProcessorFactory.create_processor(request.processor_type)
        mini_processor = large_processor
        if request.mini_processor_type:
            mini_processor = PromptProcessorFactory.create_processor(request.mini_processor_type)

        scenario_id = session_db.get("scenario_id", "")

        pipeline = TurnPipeline(
            large_processor=large_processor,
            mini_processor=mini_processor,
            session_state=session_state_service,
            ruleset_service=ruleset_service,
            event_stream=event_stream_service,
            character_loader=character_loader,
            scenario_registry=scenario_registry,
        )

        async def generate_sse_response() -> AsyncGenerator[str, None]:
            try:
                loop = asyncio.get_event_loop()
                event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

                def run_pipeline() -> None:
                    try:
                        for event in pipeline.execute_turn(
                            session_id=request.session_id,
                            user_input=request.user_input,
                            scenario_id=scenario_id,
                            ruleset=ruleset,
                            user_id=user_id,
                        ):
                            loop.call_soon_threadsafe(
                                lambda e=event: asyncio.create_task(event_queue.put(e))
                            )
                    finally:
                        loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(event_queue.put(None))
                        )

                # Run pipeline in executor
                asyncio.ensure_future(loop.run_in_executor(None, run_pipeline))

                # Stream events
                while True:
                    event = await event_queue.get()
                    if event is None:
                        break
                    yield f"data: {json.dumps(event)}\n\n"

                # Store user message in conversation log
                conversation_memory.add_message(
                    session_id=request.session_id,
                    role="user",
                    content=request.user_input,
                    user_id=user_id,
                )

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute turn: {str(e)}") from e


# ───────────────────────────── Static / Frontend ──────────────────────


@app.get("/")
async def serve_root() -> FileResponse:
    """Serve the frontend application for the root route."""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.get("/{path:path}")
async def serve_frontend(path: str = "") -> FileResponse:
    """Serve the frontend application for all non-API routes."""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.exception_handler(Exception)
async def general_exception_handler(request: object, exc: Exception) -> dict[str, str]:
    """Handle general exceptions."""
    return {"error": "Internal server error", "detail": str(exc)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)), reload=True)
