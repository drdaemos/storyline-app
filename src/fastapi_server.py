import asyncio
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.character_creator import CharacterCreator
from src.character_loader import CharacterLoader
from src.character_manager import CharacterManager
from src.character_responder import CharacterResponder
from src.memory.conversation_memory import ConversationMemory
from src.models.api_models import (
    CreateCharacterRequest,
    CreateCharacterResponse,
    GenerateCharacterRequest,
    GenerateCharacterResponse,
    HealthStatus,
    InteractRequest,
    SessionDetails,
    SessionInfo,
    SessionMessage,
)
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.memory.summary_memory import SummaryMemory

app = FastAPI(title="Storyline API", description="Interactive character chat API", version="0.1.0")

# Mount static files for the web interface
static_dir = Path(__file__).parent.parent / "static" / "assets"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

character_loader = CharacterLoader()
character_manager = CharacterManager()


@app.get("/health")
async def health_check() -> HealthStatus:
    """Health check endpoint that verifies database connectivity."""
    conversation_status = "ok"
    summary_status = "ok"
    overall_status = "healthy"
    details = {}

    try:
        # Test conversation memory database
        conversation_memory = ConversationMemory()
        if conversation_memory.health_check():
            details["conversation_db_status"] = "connected"
        else:
            conversation_status = "error"
            overall_status = "unhealthy"
            details["conversation_error"] = "Database connectivity failed"
    except Exception as e:
        conversation_status = "error"
        overall_status = "unhealthy"
        details["conversation_error"] = str(e)

    try:
        # Test summary memory database
        summary_memory = SummaryMemory()
        if summary_memory.health_check():
            details["summary_db_status"] = "connected"
        else:
            summary_status = "error"
            overall_status = "unhealthy"
            details["summary_error"] = "Database connectivity failed"
    except Exception as e:
        summary_status = "error"
        overall_status = "unhealthy"
        details["summary_error"] = str(e)

    return HealthStatus(
        status=overall_status,
        conversation_memory=conversation_status,
        summary_memory=summary_status,
        details=details
    )


@app.get("/api")
async def api_info() -> dict[str, str]:
    """API information endpoint."""
    return {"message": "Storyline API - Interactive Character Chat", "version": "0.1.0"}


@app.get("/api/characters")
async def list_characters() -> list[str]:
    """List available characters."""
    try:
        return character_loader.list_characters()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list characters: {str(e)}") from e


@app.get("/api/characters/{character_name}")
async def get_character_info(character_name: str) -> dict[str, str]:
    """Get information about a specific character."""
    try:
        character_info = character_loader.get_character_info(character_name)
        if not character_info:
            raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")

        return {
            "name": character_info.name,
            "role": character_info.role,
            "backstory": character_info.backstory,
            "personality": character_info.personality,
            "appearance": character_info.appearance,
            "setting_description": character_info.setting_description or "Not specified"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get character info: {str(e)}") from e


@app.post("/api/characters")
async def create_character(request: CreateCharacterRequest) -> CreateCharacterResponse:
    """Create a new character from either structured data or freeform YAML text."""
    try:
        # Delegate to service layer
        if request.is_yaml_text:
            if not isinstance(request.data, str):
                raise HTTPException(
                    status_code=400,
                    detail="When is_yaml_text is true, data must be a string"
                )
            character_data = character_manager.validate_yaml_text(request.data)
        else:
            if not isinstance(request.data, Character):
                raise HTTPException(
                    status_code=400,
                    detail="When is_yaml_text is false, data must be structured character data"
                )
            character_data = request.data.model_dump()

        filename = character_manager.create_character_file(character_data)

        return CreateCharacterResponse(
            message=f"Character '{character_data['name']}' created successfully",
            character_filename=filename
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create character: {str(e)}") from e


@app.post("/api/characters/generate")
async def generate_character(request: GenerateCharacterRequest) -> GenerateCharacterResponse:
    """Generate a complete character from partial character data using AI."""
    try:
        # Get the appropriate prompt processor
        from src.models.character_responder_dependencies import CharacterResponderDependencies
        dependencies = CharacterResponderDependencies.create_default(
            character_name="temp",  # Temp name for processor creation
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type
        )

        # Create character creator with the selected processor
        character_creator = CharacterCreator(
            prompt_processor=dependencies.primary_processor,
            character_manager=character_manager
        )

        # Track which fields were originally missing to report what was generated
        original_fields = set(request.partial_character.keys())
        all_character_fields = {'name', 'role', 'backstory', 'personality', 'appearance',
                               'relationships', 'key_locations', 'setting_description'}

        # Generate the complete character
        complete_character = character_creator.generate(request.partial_character)

        # Determine which fields were generated
        generated_fields = []
        character_dict = complete_character.model_dump()
        for field in all_character_fields:
            if field not in original_fields or not request.partial_character.get(field):
                if character_dict.get(field):  # Field was populated
                    generated_fields.append(field)

        return GenerateCharacterResponse(
            character=complete_character,
            generated_fields=generated_fields
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate character: {str(e)}") from e


@app.get("/api/sessions")
async def list_sessions() -> list[SessionInfo]:
    """List all sessions from conversation memory."""
    try:
        conversation_memory = ConversationMemory()
        character_loader = CharacterLoader()
        available_characters = character_loader.list_characters()
        sessions: list[SessionInfo] = []

        for character_filename in available_characters:
            # Load the character to get the actual name used in the database
            character = character_loader.load_character(character_filename)
            character_name = character.name if character else character_filename.capitalize()

            character_sessions = conversation_memory.get_character_sessions(character_name, limit=50)

            for session_info in character_sessions:
                # Get the last character response from this session (conversation type only, not evaluations)
                last_character_response = None
                try:
                    recent_messages = conversation_memory.get_recent_messages(
                        session_info["session_id"],
                        limit=1,
                        type="conversation"
                    )
                    last_character_response = recent_messages[0]["content"] if len(recent_messages) > 0 else None
                except Exception:
                    # If there's an issue getting recent messages, just set to None
                    last_character_response = None

                sessions.append(SessionInfo(
                    session_id=session_info["session_id"],
                    character_name=character_filename,  # Use filename for frontend consistency
                    message_count=session_info["message_count"],
                    last_message_time=session_info["last_message_time"],
                    last_character_response=last_character_response
                ))

        # Sort by last message time (newest first)
        sessions.sort(key=lambda x: x.last_message_time, reverse=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}") from e

    return sessions

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> SessionDetails:
    """Get details of a specific session."""
    memory = ConversationMemory()
    session_details = memory.get_session_details(session_id)
    if not session_details or session_details.get("message_count", 0) == 0:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        session_messages = memory.get_recent_messages(session_id, limit=50, type="conversation")

        last_messages = [
            SessionMessage(
                role=msg["role"],
                content=msg["content"],
                created_at=msg["created_at"] # type: ignore
            ) for msg in session_messages
        ]

        return SessionDetails(
            session_id=session_id,
            character_name=session_details["character_id"],
            message_count=session_details["message_count"],
            last_messages=last_messages,
            last_message_time=session_details["last_message_time"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session details: {str(e)}") from e


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str) -> dict[str, str]:
    """Clear a specific session."""
    memory = ConversationMemory()
    messages = memory.get_session_messages(session_id, limit=1)  # Validate session exists
    if len(messages) == 0:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        memory.delete_session(session_id)
        SummaryMemory().delete_session_summaries(session_id)
        return {"message": f"Session '{session_id}' cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}") from e


@app.post("/api/interact")
async def interact(request: InteractRequest) -> StreamingResponse:
    """
    Interact with a character and get streaming response via Server-Sent Events.

    The response will be streamed as Server-Sent Events with the following format:
    - data: {"type": "chunk", "content": "response_text"}
    - data: {"type": "session", "session_id": "session_id_value"}
    - data: {"type": "thinking", "stage": "summarizing|deliberating|responding"}
    - data: {"type": "error", "error": "error_message"}
    - data: {"type": "complete", "full_response": "full_response_text", "message_count": n}
    """
    try:
        responder = get_character_responder(
            session_id=request.session_id,
            character_name=request.character_name,
            processor_type=request.processor_type,
            backup_processor_type=request.backup_processor_type
        )

        # Create async generator for streaming response
        async def generate_sse_response() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events for streaming response."""
            try:
                # Send session info first
                yield f"data: {json.dumps({'type': 'session', 'session_id': responder.session_id})}\n\n"

                # Create queues for streaming chunks and events
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                event_queue: asyncio.Queue[dict[str, str] | None] = asyncio.Queue()
                character_response = ""
                loop = asyncio.get_event_loop()

                def streaming_callback(chunk: str) -> None:
                    """Called by responder when a chunk is available."""
                    # Use call_soon_threadsafe to safely add to queue from executor thread
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(chunk_queue.put(chunk)))

                def event_callback(event_type: str, **kwargs: str) -> None:
                    """Called by responder when an event occurs."""
                    event_data = {"type": event_type, **kwargs}
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(event_queue.put(event_data)))

                # Run the character response in a separate task
                async def run_character_response() -> None:
                    nonlocal character_response
                    try:
                        character_response = await loop.run_in_executor(
                            None,
                            lambda: responder.respond(request.user_message, streaming_callback, event_callback)
                        )
                    finally:
                        # Signal completion
                        await chunk_queue.put(None)
                        await event_queue.put(None)

                # Start the character response task
                response_task = asyncio.create_task(run_character_response())

                # Stream chunks and events as they become available
                chunk_done = False
                event_done = False

                while not (chunk_done and event_done):
                    # Use asyncio.wait to handle both queues concurrently
                    chunk_task = asyncio.create_task(chunk_queue.get()) if not chunk_done else None
                    event_task = asyncio.create_task(event_queue.get()) if not event_done else None

                    tasks = [task for task in [chunk_task, event_task] if task is not None]
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
                                chunk_data = {"type": "chunk", "content": chunk}
                                yield f"data: {json.dumps(chunk_data)}\n\n"
                        elif task == event_task and event_task is not None:
                            event = await event_task
                            if event is None:  # Completion signal
                                event_done = True
                            else:
                                yield f"data: {json.dumps(event)}\n\n"

                # Wait for response task to complete and send completion marker
                await response_task
                completion_data = {
                    "type": "complete",
                    "full_response": character_response,
                    "message_count": len(responder.memory)
                }
                yield f"data: {json.dumps(completion_data)}\n\n"

            except Exception as e:
                error_data = {
                    "type": "error",
                    "error": str(e)
                }
                responder.chat_logger.log_exception(e) if responder.chat_logger else None
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process interaction: {str(e)}") from e

def get_character_responder(session_id: str | None, character_name: str, processor_type: str, backup_processor_type: str | None = None) -> CharacterResponder:
    # Load character if not already loaded
    character = character_loader.load_character(character_name)
    if not character:
        raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")
    dependencies = CharacterResponderDependencies.create_default(
        character_name=character.name,
        session_id=session_id,
        logs_dir=None,
        processor_type=processor_type,
        backup_processor_type=backup_processor_type
    )

    session_id = dependencies.session_id
    return CharacterResponder(character, dependencies)

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
