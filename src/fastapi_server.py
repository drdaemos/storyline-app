import asyncio
import json
import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.auth import UserIdDep
from src.catalog_application_service import CatalogApplicationService
from src.character_creation_assistant import CharacterCreationAssistant
from src.character_creator import CharacterCreator
from src.character_loader import CharacterLoader
from src.character_manager import CharacterManager
from src.memory.scenario_registry import ScenarioRegistry
from src.memory.world_lore_registry import WorldLoreRegistry
from src.models.api_models import (
    CharacterCreationRequest,
    CharacterCreationStreamEvent,
    CharacterSummary,
    ConfigureSessionModelsRequest,
    CreateCharacterRequest,
    CreateCharacterResponse,
    GenerateCharacterRequest,
    GenerateCharacterResponse,
    GenerateScenariosRequest,
    GenerateScenariosResponse,
    HealthStatus,
    InteractRequest,
    ListScenariosResponse,
    PartialScenario,
    SaveScenarioRequest,
    SaveScenarioResponse,
    SaveWorldLoreRequest,
    SaveWorldLoreResponse,
    RulesetDefinition,
    Scenario,
    ScenarioCreationRequest,
    ScenarioCreationStreamEvent,
    ScenarioGenerationStreamEvent,
    ScenarioSummary,
    SessionDetails,
    SessionInfo,
    SessionMessage,
    SessionSummaryResponse,
    StartSessionRequest,
    StartSessionResponse,
    WorldLoreAsset,
    WorldLoreCreationRequest,
    WorldLoreCreationStreamEvent,
)
from src.models.character import Character, PartialCharacter
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.scenario_creation_assistant import ScenarioCreationAssistant
from src.scenario_generator import ScenarioGenerator
from src.session_application_service import SessionApplicationService
from src.simulation.service import SimulationService
from src.world_lore_creation_assistant import WorldLoreCreationAssistant

app = FastAPI(title="Storyline API", description="Interactive character chat API", version="0.1.0")

# Mount static files for the web interface
static_dir = Path(__file__).parent.parent / "static" / "assets"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

character_loader = CharacterLoader()
character_manager = CharacterManager()
scenario_registry = ScenarioRegistry()
world_lore_registry = WorldLoreRegistry()
simulation_service = SimulationService.create_default()
session_service = SessionApplicationService.create_default(
    simulation_service=simulation_service,
    scenario_registry=scenario_registry,
    character_loader=character_loader,
)


def _catalog_service() -> CatalogApplicationService:
    return CatalogApplicationService.create_default(
        character_loader=character_loader,
        character_manager=character_manager,
        scenario_registry=scenario_registry,
        world_lore_registry=world_lore_registry,
        simulation_repository=simulation_service.repository,
    )


@app.get("/health")
async def health_check() -> HealthStatus:
    """Health check endpoint that verifies simulation database connectivity."""
    runtime_status = "ok"
    events_status = "ok"
    overall_status = "healthy"
    details = {}

    try:
        if session_service.health_check():
            details["simulation_db_status"] = "connected"
        else:
            runtime_status = "error"
            events_status = "error"
            overall_status = "unhealthy"
            details["simulation_error"] = "Database connectivity failed"
    except Exception as e:
        runtime_status = "error"
        events_status = "error"
        overall_status = "unhealthy"
        details["simulation_error"] = str(e)

    return HealthStatus(status=overall_status, conversation_memory=runtime_status, summary_memory=events_status, details=details)


@app.get("/api")
async def api_info() -> dict[str, str]:
    """API information endpoint."""
    return {"message": "Storyline API - Interactive Character Chat", "version": "0.1.0"}


@app.get("/api/characters")
async def list_characters(user_id: UserIdDep) -> list[CharacterSummary]:
    """List available characters with their basic info."""
    try:
        return _catalog_service().list_characters(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list characters: {str(e)}") from e


@app.get("/api/personas")
async def list_personas(user_id: UserIdDep) -> list[CharacterSummary]:
    """List available persona characters with their basic info."""
    try:
        return _catalog_service().list_personas(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list personas: {str(e)}") from e


@app.get("/api/rulesets")
async def list_rulesets(_user_id: UserIdDep) -> list[RulesetDefinition]:
    """List available rulesets with schemas for ruleset-aware UI forms."""
    try:
        return [RulesetDefinition(**item.model_dump()) for item in _catalog_service().list_rulesets()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list rulesets: {str(e)}") from e


@app.get("/api/characters/{character_name}")
async def get_character_info(character_name: str, user_id: UserIdDep) -> dict:
    """Get information about a specific character."""
    try:
        character_info = _catalog_service().get_character_info(character_name, user_id)
        if not character_info:
            raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")

        # Return full character data as dict
        return character_info.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get character info: {str(e)}") from e


@app.post("/api/characters")
async def create_character(request: CreateCharacterRequest, user_id: UserIdDep) -> CreateCharacterResponse:
    """Create a new character from either structured data or freeform YAML text."""
    try:
        payload = request.data if isinstance(request.data, str) else request.data.model_dump()
        filename, character_name = _catalog_service().create_character(
            payload,
            user_id,
            is_yaml_text=request.is_yaml_text,
            is_persona=request.is_persona,
        )
        return CreateCharacterResponse(message=f"Character '{character_name}' created successfully", character_filename=filename)

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
        payload = request.data if isinstance(request.data, str) else request.data.model_dump()
        updated_character_id, character_name = _catalog_service().update_character(
            character_id,
            payload,
            user_id,
            is_yaml_text=request.is_yaml_text,
        )
        return CreateCharacterResponse(message=f"Character '{character_name}' updated successfully", character_filename=updated_character_id)

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
        # Get the appropriate prompt processor
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",  # Temp name for processor creation
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type,
        )

        # Create character creator with the selected processor
        character_creator = CharacterCreator(prompt_processor=dependencies.primary_processor, character_manager=character_manager)

        # Track which fields were originally missing to report what was generated
        original_fields = set(request.partial_character.keys())

        # Generate the complete character
        complete_character = character_creator.generate(request.partial_character)
        all_character_fields = set(complete_character.model_dump().keys())

        # Determine which fields were generated
        generated_fields = []
        character_dict = complete_character.model_dump()
        for field in all_character_fields:
            if field not in original_fields or not request.partial_character.get(field):
                if character_dict.get(field):  # Field was populated
                    generated_fields.append(field)

        return GenerateCharacterResponse(character=complete_character, generated_fields=generated_fields)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate character: {str(e)}") from e


@app.post("/api/characters/create-stream")
async def create_character_stream(request: CharacterCreationRequest, _user_id: UserIdDep) -> StreamingResponse:
    """
    Interactive character creation with AI assistant via Server-Sent Events.

    The response will be streamed as Server-Sent Events with the following format:
    - data: {"type": "message", "message": "AI response text chunk"}
    - data: {"type": "update", "updates": {"name": "...", "backstory": "..."}}
    - data: {"type": "complete"}
    - data: {"type": "error", "error": "error_message"}
    """
    try:
        # Get the appropriate prompt processor
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",  # Temp name for processor creation
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type,
        )

        # Create character creation assistant with the selected processor
        assistant = CharacterCreationAssistant(prompt_processor=dependencies.primary_processor)

        # Create async generator for streaming response
        async def generate_sse_response() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events for streaming character creation."""
            try:
                # Create queue for streaming chunks
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                ai_response_parts: list[str] = []
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    """Called by assistant when a chunk is available."""
                    ai_response_parts.append(chunk)
                    # Use call_soon_threadsafe to safely add to queue from executor thread
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                # Run the assistant processing in a separate task
                async def run_assistant() -> tuple[str, PartialCharacter]:
                    try:
                        # Process message with streaming
                        response, updates = await loop.run_in_executor(
                            None,
                            lambda: assistant.process_message(
                                user_message=request.user_message,
                                current_character=request.current_character,
                                conversation_history=request.conversation_history,
                                streaming_callback=streaming_callback,
                            ),
                        )
                        return response, updates
                    finally:
                        # Signal completion
                        await chunk_queue.put(None)

                # Start the assistant task
                assistant_task = asyncio.create_task(run_assistant())

                # Stream message chunks as they become available
                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:  # Completion signal
                        break

                    # Remove character_update tags from chunk but preserve spacing
                    # Don't use clean_response_text() as it strips whitespace which breaks streaming
                    clean_chunk = re.sub(r"<character_update>[\s\S]*?</character_update>", "", chunk)

                    if clean_chunk:  # Only send non-empty chunks
                        event_data = CharacterCreationStreamEvent(type="message", message=clean_chunk)
                        yield f"data: {event_data.model_dump_json()}\n\n"

                # Wait for assistant task to complete and get the updates
                full_response, updated_character = await assistant_task

                # Send character updates if any
                if updated_character != request.current_character:
                    update_event = CharacterCreationStreamEvent(type="update", updates=updated_character)
                    yield f"data: {update_event.model_dump_json()}\n\n"

                # Send completion marker
                complete_event = CharacterCreationStreamEvent(type="complete")
                yield f"data: {complete_event.model_dump_json()}\n\n"

            except Exception as e:
                error_event = CharacterCreationStreamEvent(type="error", error=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process character creation: {str(e)}") from e


@app.post("/api/scenarios/generate")
async def generate_scenarios(request: GenerateScenariosRequest, user_id: UserIdDep) -> GenerateScenariosResponse:
    """Generate scenario intros for a given character."""
    try:
        # Load the character from registry
        character = character_loader.load_character(request.character_name, user_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character '{request.character_name}' not found")

        # Load the persona if provided
        persona = None
        if request.persona_id:
            persona = character_loader.load_character(request.persona_id, user_id)
            # Don't fail if persona not found, just proceed without it

        # Get the appropriate prompt processor
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",  # Temp name for processor creation
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type,
        )

        # Create scenario generator with the selected processor
        scenario_generator = ScenarioGenerator(processors=[dependencies.primary_processor, dependencies.backup_processor], logger=dependencies.chat_logger)

        # Generate scenarios
        scenarios = scenario_generator.generate_scenarios(character, count=request.count, mood=request.mood, persona=persona)

        return GenerateScenariosResponse(character_name=character.name, scenarios=scenarios)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate scenarios: {str(e)}") from e


@app.post("/api/scenarios/generate-stream")
async def generate_scenarios_stream(request: GenerateScenariosRequest, user_id: UserIdDep) -> StreamingResponse:
    """
    Generate scenario intros for a given character with streaming via Server-Sent Events.

    The response will be streamed as Server-Sent Events with the following format:
    - data: {"type": "chunk", "chunk": "XML text chunk"}
    - data: {"type": "scenario", "scenario": {...}}
    - data: {"type": "complete"}
    - data: {"type": "error", "error": "error_message"}
    """
    try:
        # Load the character from registry
        character = character_loader.load_character(request.character_name, user_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character '{request.character_name}' not found")

        # Load the persona if provided
        persona = None
        if request.persona_id:
            persona = character_loader.load_character(request.persona_id, user_id)
            # Don't fail if persona not found, just proceed without it

        # Get the appropriate prompt processor
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",  # Temp name for processor creation
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type,
        )

        # Create scenario generator with the selected processor
        scenario_generator = ScenarioGenerator(processors=[dependencies.primary_processor, dependencies.backup_processor], logger=dependencies.chat_logger)

        # Create async generator for streaming response
        async def generate_sse_response() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events for streaming scenario generation."""
            try:
                # Create queues for streaming chunks and scenario events
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                scenario_queue: asyncio.Queue[dict[str, str] | None] = asyncio.Queue()
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    """Called by generator when a chunk is available."""
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                def scenario_callback(scenario: object) -> None:
                    """Called by generator when a complete scenario is parsed."""
                    from src.models.api_models import Scenario

                    if isinstance(scenario, Scenario):
                        scenario_data = {"type": "scenario", "scenario": scenario.model_dump()}
                        loop.call_soon_threadsafe(lambda: asyncio.create_task(scenario_queue.put(scenario_data)))

                # Run the scenario generation in a separate task
                async def run_generation() -> list[object]:
                    try:
                        scenarios = await loop.run_in_executor(
                            None,
                            lambda: scenario_generator.generate_scenarios_streaming(
                                character, count=request.count, mood=request.mood, persona=persona, streaming_callback=streaming_callback, scenario_callback=scenario_callback
                            ),
                        )
                        return scenarios
                    finally:
                        # Signal completion
                        await chunk_queue.put(None)
                        await scenario_queue.put(None)

                # Start the generation task
                generation_task = asyncio.create_task(run_generation())

                # Stream chunks and scenarios as they become available
                chunk_done = False
                scenario_done = False

                while not (chunk_done and scenario_done):
                    # Use asyncio.wait to handle both queues concurrently
                    chunk_task = asyncio.create_task(chunk_queue.get()) if not chunk_done else None
                    scenario_task = asyncio.create_task(scenario_queue.get()) if not scenario_done else None

                    tasks = [task for task in [chunk_task, scenario_task] if task is not None]
                    if not tasks:
                        break

                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                    # Cancel pending tasks to avoid resource leaks
                    for task in pending:
                        task.cancel()

                    for task in done:
                        if task == chunk_task and chunk_task is not None:
                            chunk = await chunk_task
                            if chunk is None:  # Completion signal
                                chunk_done = True
                            else:
                                # Send chunk event
                                event_data = ScenarioGenerationStreamEvent(type="chunk", chunk=chunk)
                                yield f"data: {event_data.model_dump_json()}\n\n"
                        elif task == scenario_task and scenario_task is not None:
                            scenario_data = await scenario_task
                            if scenario_data is None:  # Completion signal
                                scenario_done = True
                            else:
                                # Send scenario event
                                yield f"data: {json.dumps(scenario_data)}\n\n"

                # Wait for generation task to complete
                await generation_task

                # Send completion marker
                complete_event = ScenarioGenerationStreamEvent(type="complete")
                yield f"data: {complete_event.model_dump_json()}\n\n"

            except Exception as e:
                error_event = ScenarioGenerationStreamEvent(type="error", error=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process scenario generation: {str(e)}") from e


@app.post("/api/scenarios/create-stream")
async def create_scenario_stream(request: ScenarioCreationRequest, user_id: UserIdDep) -> StreamingResponse:
    """
    Interactive scenario creation with AI assistant via Server-Sent Events.

    The response will be streamed as Server-Sent Events with the following format:
    - data: {"type": "message", "message": "AI response text chunk"}
    - data: {"type": "update", "updates": {"summary": "...", "intro_message": "..."}}
    - data: {"type": "complete"}
    - data: {"type": "error", "error": "error_message"}
    """
    try:
        selected_character_names = request.character_names or []
        primary_character_name = request.character_name or ""
        if selected_character_names and primary_character_name not in selected_character_names:
            primary_character_name = selected_character_names[0]

        # Load the primary character from registry
        character = character_loader.load_character(primary_character_name, user_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character '{primary_character_name}' not found")

        # Load the currently selected persona if provided
        persona = None
        if request.persona_id:
            persona = character_loader.load_character(request.persona_id, user_id)
            # Don't fail if persona not found, just proceed without it

        # Get the appropriate prompt processor
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",  # Temp name for processor creation
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type,
        )

        # Create scenario creation assistant with the selected processor
        assistant = ScenarioCreationAssistant(prompt_processor=dependencies.primary_processor)

        # Ensure character_id is set in current_scenario
        current_scenario = request.current_scenario
        if not current_scenario.character_id:
            current_scenario = current_scenario.model_copy(update={"character_id": primary_character_name})
        if not current_scenario.character_ids:
            character_ids = selected_character_names or [primary_character_name]
            current_scenario = current_scenario.model_copy(update={"character_ids": character_ids})
        if request.persona_id and not current_scenario.persona_id:
            current_scenario = current_scenario.model_copy(update={"persona_id": request.persona_id})

        # Get available personas for AI suggestions
        available_personas = request.available_personas

        # Create async generator for streaming response
        async def generate_sse_response() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events for streaming scenario creation."""
            try:
                # Create queue for streaming chunks
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                ai_response_parts: list[str] = []
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    """Called by assistant when a chunk is available."""
                    ai_response_parts.append(chunk)
                    # Use call_soon_threadsafe to safely add to queue from executor thread
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                # Run the assistant processing in a separate task
                async def run_assistant() -> tuple[str, PartialScenario]:
                    try:
                        # Process message with streaming
                        response, updates = await loop.run_in_executor(
                            None,
                            lambda: assistant.process_message(
                                user_message=request.user_message,
                                current_scenario=current_scenario,
                                character=character,
                                persona=persona,
                                available_personas=available_personas,
                                conversation_history=request.conversation_history,
                                streaming_callback=streaming_callback,
                            ),
                        )
                        return response, updates
                    finally:
                        # Signal completion
                        await chunk_queue.put(None)

                # Start the assistant task
                assistant_task = asyncio.create_task(run_assistant())

                # Stream message chunks as they become available
                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:  # Completion signal
                        break

                    # Remove scenario_update tags from chunk but preserve spacing
                    clean_chunk = re.sub(r"<scenario_update>[\s\S]*?</scenario_update>", "", chunk)

                    if clean_chunk:  # Only send non-empty chunks
                        event_data = ScenarioCreationStreamEvent(type="message", message=clean_chunk)
                        yield f"data: {event_data.model_dump_json()}\n\n"

                # Wait for assistant task to complete and get the updates
                full_response, updated_scenario = await assistant_task

                # Send scenario updates if any
                if updated_scenario != current_scenario:
                    update_event = ScenarioCreationStreamEvent(type="update", updates=updated_scenario)
                    yield f"data: {update_event.model_dump_json()}\n\n"

                # Send completion marker
                complete_event = ScenarioCreationStreamEvent(type="complete")
                yield f"data: {complete_event.model_dump_json()}\n\n"

            except Exception as e:
                error_event = ScenarioCreationStreamEvent(type="error", error=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process scenario creation: {str(e)}") from e


@app.post("/api/scenarios/save")
async def save_scenario(request: SaveScenarioRequest, user_id: UserIdDep) -> SaveScenarioResponse:
    """Save a completed scenario to the database."""
    try:
        scenario_id = _catalog_service().save_scenario(request=request, user_id=user_id)
        return SaveScenarioResponse(scenario_id=scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scenario: {str(e)}") from e


@app.get("/api/scenarios/list/{character_name}")
async def list_scenarios_for_character(character_name: str, user_id: UserIdDep) -> ListScenariosResponse:
    """List all saved scenarios for a character."""
    try:
        scenario_summaries = _catalog_service().list_scenarios_for_character(character_name, user_id)
        return ListScenariosResponse(character_name=character_name, scenarios=scenario_summaries)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list scenarios: {str(e)}") from e


@app.get("/api/scenarios/list")
async def list_all_scenarios(user_id: UserIdDep) -> ListScenariosResponse:
    """List all saved scenarios for the user."""
    try:
        scenario_summaries = _catalog_service().list_all_scenarios(user_id)
        return ListScenariosResponse(character_name="all", scenarios=scenario_summaries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list scenarios: {str(e)}") from e


@app.get("/api/world-lore")
async def list_world_lore(user_id: UserIdDep) -> list[WorldLoreAsset]:
    try:
        return _catalog_service().list_world_lore(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list world lore: {str(e)}") from e


@app.get("/api/world-lore/{world_lore_id}")
async def get_world_lore(world_lore_id: str, user_id: UserIdDep) -> WorldLoreAsset:
    try:
        item = _catalog_service().get_world_lore(world_lore_id, user_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"World lore '{world_lore_id}' not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get world lore: {str(e)}") from e


@app.post("/api/world-lore")
async def save_world_lore(request: SaveWorldLoreRequest, user_id: UserIdDep) -> SaveWorldLoreResponse:
    try:
        world_lore_id = _catalog_service().save_world_lore(request, user_id)
        return SaveWorldLoreResponse(world_lore_id=world_lore_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save world lore: {str(e)}") from e


@app.post("/api/world-lore/create-stream")
async def create_world_lore_stream(request: WorldLoreCreationRequest, _user_id: UserIdDep) -> StreamingResponse:
    """Interactive world lore creation with AI assistant via Server-Sent Events."""
    try:
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type,
        )
        assistant = WorldLoreCreationAssistant(prompt_processor=dependencies.primary_processor)

        async def generate_sse_response() -> AsyncGenerator[str, None]:
            try:
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                async def run_assistant() -> tuple[str, object]:
                    try:
                        response, updates = await loop.run_in_executor(
                            None,
                            lambda: assistant.process_message(
                                user_message=request.user_message,
                                current_world_lore=request.current_world_lore,
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
                    clean_chunk = re.sub(r"<world_lore_update>[\s\S]*?</world_lore_update>", "", chunk)
                    if clean_chunk:
                        event_data = WorldLoreCreationStreamEvent(type="message", message=clean_chunk)
                        yield f"data: {event_data.model_dump_json()}\n\n"

                _full_response, updated_world_lore = await assistant_task

                if updated_world_lore != request.current_world_lore:
                    update_event = WorldLoreCreationStreamEvent(type="update", updates=updated_world_lore)
                    yield f"data: {update_event.model_dump_json()}\n\n"

                complete_event = WorldLoreCreationStreamEvent(type="complete")
                yield f"data: {complete_event.model_dump_json()}\n\n"
            except Exception as e:
                error_event = WorldLoreCreationStreamEvent(type="error", error=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process world lore creation: {str(e)}") from e


@app.delete("/api/world-lore/{world_lore_id}")
async def delete_world_lore(world_lore_id: str, user_id: UserIdDep) -> dict[str, str]:
    try:
        deleted = _catalog_service().delete_world_lore(world_lore_id, user_id)
        if not deleted:
            raise HTTPException(status_code=400, detail=f"World lore '{world_lore_id}' cannot be deleted")
        return {"message": f"World lore '{world_lore_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete world lore: {str(e)}") from e


@app.get("/api/scenarios/detail/{scenario_id}")
async def get_scenario_detail(scenario_id: str, user_id: UserIdDep) -> Scenario:
    """Get a specific scenario by ID."""
    try:
        scenario = _catalog_service().get_scenario_detail(scenario_id, user_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
        return scenario

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scenario: {str(e)}") from e


@app.delete("/api/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str, user_id: UserIdDep) -> dict[str, str]:
    """Delete a scenario by ID."""
    try:
        deleted = _catalog_service().delete_scenario(scenario_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

        return {"message": f"Scenario '{scenario_id}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete scenario: {str(e)}") from e


@app.get("/api/sessions")
async def list_sessions(user_id: UserIdDep) -> list[SessionInfo]:
    """List all sessions from the simulation runtime store."""
    try:
        sessions = session_service.list_sessions(user_id=user_id)
        return [
            SessionInfo(
                session_id=session["session_id"],
                character_name=session["character_name"],
                message_count=session["message_count"],
                last_message_time=session["last_message_time"],
                last_character_response=session["last_character_response"],
            )
            for session in sessions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}") from e


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, user_id: UserIdDep) -> SessionDetails:
    """Get details of a specific session."""
    try:
        session_details = session_service.get_session_details(session_id=session_id, user_id=user_id, limit=50)
        if not session_details:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        return SessionDetails(
            session_id=session_id,
            character_name=session_details["character_name"],
            message_count=session_details["message_count"],
            last_messages=[SessionMessage(**msg) for msg in session_details["messages"]],
            last_message_time=session_details["last_message_time"],
            suggested_actions=session_details.get("suggested_actions", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session details: {str(e)}") from e


@app.get("/api/sessions/{session_id}/summary")
async def get_session_summary(session_id: str, user_id: UserIdDep) -> SessionSummaryResponse:
    """Get a runtime summary assembled from simulation state and narrator events."""
    try:
        summary_text, has_summary = session_service.get_session_summary(session_id=session_id, user_id=user_id)
        return SessionSummaryResponse(session_id=session_id, summary_text=summary_text, has_summary=has_summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session summary: {str(e)}") from e


@app.get("/api/sessions/{session_id}/persona")
async def get_session_persona(session_id: str, user_id: UserIdDep) -> dict[str, str | None]:
    """Get the persona information for a session from simulation session participants."""
    try:
        return session_service.get_session_persona(session_id=session_id, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session persona: {str(e)}") from e


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str, user_id: UserIdDep) -> dict[str, str]:
    """Clear a specific session."""
    deleted = session_service.clear_session(session_id=session_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"message": f"Session '{session_id}' cleared successfully"}


@app.post("/api/sessions/start")
async def start_session_with_scenario(request: StartSessionRequest, user_id: UserIdDep) -> StartSessionResponse:
    """
    Start a new session with a scenario.

    This endpoint creates a new session and initializes it with either:
    - A stored scenario (by scenario_id)
    - A raw intro message

    At least one of scenario_id or intro_message must be provided.
    Persona is required when starting from a raw intro message.
    """
    try:
        session_id = session_service.start_session(request=request, user_id=user_id)
        return StartSessionResponse(session_id=session_id)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}") from e


@app.put("/api/sessions/{session_id}/models")
async def configure_session_models(session_id: str, request: ConfigureSessionModelsRequest, user_id: UserIdDep) -> dict[str, str]:
    """Update per-session small/large model keys."""
    updated = session_service.configure_session_models(
        session_id=session_id,
        user_id=user_id,
        small_model_key=request.small_model_key,
        large_model_key=request.large_model_key,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"message": "Session model configuration updated"}


@app.post("/api/interact")
async def interact(request: InteractRequest, user_id: UserIdDep) -> StreamingResponse:
    """
    Interact with a character and get streaming response via Server-Sent Events.

    The response will be streamed as Server-Sent Events with the following format:
    - data: {"type": "chunk", "content": "response_text"}
    - data: {"type": "session", "session_id": "session_id_value"}
    - data: {"type": "thinking", "stage": "summarizing|deliberating|responding"}
    - data: {"type": "error", "error": "error_message"}
    - data: {"type": "complete", "full_response": "full_response_text", "message_count": n, "suggested_actions": [...]}
    """
    try:
        session_id = request.session_id

        async def generate_sse_response() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events for simulation response."""
            try:
                yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking', 'stage': 'resolving'})}\n\n"

                interaction_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session_service.run_interaction(
                        session_id=session_id,
                        user_id=user_id,
                        user_message=request.user_message,
                    ),
                )

                chunk_data = {"type": "chunk", "content": interaction_result.narration_text}
                yield f"data: {json.dumps(chunk_data)}\n\n"
                completion_data = {
                    "type": "complete",
                    "full_response": interaction_result.narration_text,
                    "suggested_actions": interaction_result.suggested_actions,
                    "meta_text": interaction_result.meta_text,
                    "message_count": interaction_result.message_count,
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
            except Exception as e:
                error_data = {"type": "error", "error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process interaction: {str(e)}") from e


# Root route - serve the Vue.js app
@app.get("/")
async def serve_root() -> FileResponse:
    """Serve the frontend application for the root route."""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    raise HTTPException(status_code=404, detail="Frontend not found")


# Frontend routing - serve the Vue.js app for all other non-API routes
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
