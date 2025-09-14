import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.character_loader import CharacterLoader
from src.character_responder import CharacterResponder
from src.models.character_responder_dependencies import CharacterResponderDependencies

app = FastAPI(title="Storyline API", description="Interactive character chat API", version="0.1.0")

# Mount static files for the web interface
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Global variables to store character responders by session
character_sessions: dict[str, CharacterResponder] = {}
character_loader = CharacterLoader()


class InteractRequest(BaseModel):
    character_name: str = Field(..., min_length=1, description="Name of the character to interact with")
    user_message: str = Field(..., min_length=1, description="User's message to the character")
    session_id: str | None = Field(None, description="Optional session ID for conversation continuity")
    processor_type: str = Field("google", description="AI processor type (google, openai, cohere, etc.)")


class SessionInfo(BaseModel):
    session_id: str
    character_name: str
    message_count: int


class ErrorResponse(BaseModel):
    error: str
    detail: str


@app.get("/")
async def root():  # noqa: ANN201
    """Root endpoint serving the web interface."""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "Storyline API - Interactive Character Chat", "version": "0.1.0"}


@app.get("/api")
async def api_info() -> dict[str, str]:
    """API information endpoint."""
    return {"message": "Storyline API - Interactive Character Chat", "version": "0.1.0"}


@app.get("/characters")
async def list_characters() -> list[str]:
    """List available characters."""
    try:
        return character_loader.list_characters()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list characters: {str(e)}") from e


@app.get("/characters/{character_name}")
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


@app.get("/sessions")
async def list_sessions() -> list[SessionInfo]:
    """List active sessions."""
    sessions = []
    for session_id, responder in character_sessions.items():
        sessions.append(SessionInfo(
            session_id=session_id,
            character_name=responder.character.name,
            message_count=len(responder.memory)
        ))
    return sessions


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict[str, str]:
    """Clear a specific session."""
    if session_id not in character_sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        responder = character_sessions[session_id]
        responder.clear_current_session()
        del character_sessions[session_id]
        return {"message": f"Session '{session_id}' cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}") from e


@app.post("/interact")
async def interact(request: InteractRequest) -> StreamingResponse:
    """
    Interact with a character and get streaming response via Server-Sent Events.

    The response will be streamed as Server-Sent Events with the following format:
    - data: {"type": "chunk", "content": "response_text"}
    - data: {"type": "complete"}
    """
    try:
        # Load character if not already loaded
        character = character_loader.load_character(request.character_name)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character '{request.character_name}' not found")

        # Generate session ID if not provided
        session_id = request.session_id
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())

        # Get or create character responder for this session
        if session_id not in character_sessions:
            dependencies = CharacterResponderDependencies.create_default(
                character_name=character.name,
                session_id=session_id,
                use_persistent_memory=True,
                logs_dir=None,
                processor_type=request.processor_type
            )
            character_sessions[session_id] = CharacterResponder(character, dependencies)

        responder = character_sessions[session_id]

        # Create async generator for streaming response
        async def generate_sse_response() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events for streaming response."""
            try:
                # Send session info first
                yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

                # Create a queue for streaming chunks
                chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
                response_complete = False
                character_response = ""

                def streaming_callback(chunk: str) -> None:
                    """Called by responder when a chunk is available."""
                    asyncio.create_task(chunk_queue.put(chunk))

                # Run the character response in a separate task
                async def run_character_response() -> None:
                    nonlocal character_response, response_complete
                    try:
                        loop = asyncio.get_event_loop()
                        character_response = await loop.run_in_executor(
                            None,
                            lambda: responder.respond(request.user_message, streaming_callback)
                        )
                    finally:
                        response_complete = True
                        await chunk_queue.put(None)  # Signal completion

                # Start the character response task
                response_task = asyncio.create_task(run_character_response())

                # Stream chunks as they become available
                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:  # Completion signal
                        break

                    chunk_data = {
                        "type": "chunk",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"

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


@app.exception_handler(Exception)
async def general_exception_handler(request: object, exc: Exception) -> dict[str, str]:
    """Handle general exceptions."""
    return {"error": "Internal server error", "detail": str(exc)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
