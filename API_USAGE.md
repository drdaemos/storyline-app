# FastAPI Integration Guide

The Storyline app now includes a FastAPI-based REST API with Server-Sent Events streaming for real-time character interactions.

## Starting the Server

### Using the CLI Command

```bash
# Basic usage
python -m src.cli serve

# Custom host and port
python -m src.cli serve --host localhost --port 3000

# Enable auto-reload for development
python -m src.cli serve --reload
```

### Direct Server Start

```bash
# Using uvicorn directly
uvicorn src.fastapi_server:app --host 0.0.0.0 --port 8000 --reload

# Using Python
python src/fastapi_server.py
```

## Web Interface

Once the server is running, you can access:

- **Web Interface**: http://localhost:8000/
- **API Documentation**: http://localhost:8000/docs
- **Alternative API Docs**: http://localhost:8000/redoc

The web interface provides a user-friendly chat interface with:
- Character selection
- AI processor selection (Google Gemini, OpenAI, Cohere, OpenRouter)
- Real-time streaming responses
- Session management
- Message history

## API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface (HTML) |
| GET | `/api` | API information |
| GET | `/characters` | List available characters |
| GET | `/characters/{name}` | Get character information |
| POST | `/interact` | Chat with a character (SSE streaming) |
| GET | `/sessions` | List active sessions |
| DELETE | `/sessions/{session_id}` | Clear a session |

### Character Interaction

The main `/interact` endpoint supports Server-Sent Events for real-time streaming:

```javascript
// Example JavaScript client
const response = await fetch('/interact', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        character_name: "Alice",
        user_message: "Hello! How are you?",
        session_id: "optional-session-id",
        processor_type: "google"
    })
});

// Handle Server-Sent Events
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\\n');
    
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'chunk') {
                console.log(data.content); // Character response chunk
            } else if (data.type === 'complete') {
                console.log('Response completed');
                break;
            }
        }
    }
}
```

### Request/Response Format

#### Interact Request
```json
{
    "character_name": "Alice",
    "user_message": "Hello there!",
    "session_id": "optional-session-123",
    "processor_type": "google"
}
```

#### SSE Response Events
```javascript
// Session info
data: {"type": "session", "session_id": "generated-uuid"}

// Response chunks (streamed)
data: {"type": "chunk", "content": "Hello! "}
data: {"type": "chunk", "content": "How are "}
data: {"type": "chunk", "content": "you today?"}

// Completion
data: {"type": "complete", "full_response": "Hello! How are you today?", "message_count": 3}

// Error (if any)
data: {"type": "error", "error": "Error description"}
```

## Client Examples

### Python Client

```python
import requests
import json

def chat_with_character(character_name, message, session_id=None):
    response = requests.post('http://localhost:8000/interact', 
        json={
            'character_name': character_name,
            'user_message': message,
            'session_id': session_id,
            'processor_type': 'google'
        },
        stream=True
    )
    
    for line in response.iter_lines(decode_unicode=True):
        if line.startswith('data: '):
            data = json.loads(line[6:])
            if data['type'] == 'chunk':
                print(data['content'], end='', flush=True)
            elif data['type'] == 'complete':
                print('\\n--- Response completed ---')
                return data['session_id']

# Usage
session_id = chat_with_character('Alice', 'Hello!')
chat_with_character('Alice', 'How are you?', session_id)
```

### cURL Examples

```bash
# List characters
curl http://localhost:8000/characters

# Get character info
curl http://localhost:8000/characters/Alice

# Interactive chat (will stream response)
curl -X POST http://localhost:8000/interact \\
  -H "Content-Type: application/json" \\
  -d '{
    "character_name": "Alice",
    "user_message": "Hello!",
    "processor_type": "google"
  }' \\
  --no-buffer

# List active sessions
curl http://localhost:8000/sessions

# Clear a session
curl -X DELETE http://localhost:8000/sessions/session-uuid
```

## Features

### Real-time Streaming
- Server-Sent Events (SSE) for real-time response streaming
- Character responses are streamed token by token as they're generated
- No polling required - responses arrive as soon as they're available

### Session Management
- Automatic session creation with UUID generation
- Persistent conversation memory across requests
- Session listing and clearing functionality
- Optional custom session IDs

### Multiple AI Processors
- Google Gemini (default)
- OpenAI GPT models
- Cohere models  
- OpenRouter models
- Configurable per request

### Character System
- Full integration with existing character loader
- Dynamic character information endpoint
- Support for all character attributes (personality, backstory, etc.)

### Error Handling
- Comprehensive error responses
- Graceful fallback between primary/backup processors
- Input validation with detailed error messages

## Testing

Run the test suite for the FastAPI integration:

```bash
# Run all FastAPI tests
python -m pytest tests/test_fastapi_integration.py -v

# Run with coverage
python -m pytest tests/test_fastapi_integration.py --cov=src.fastapi_server

# Test the server with the provided test script
python test_fastapi.py
```

## Development

### Running in Development Mode

```bash
# Auto-reload on file changes
python -m src.cli serve --reload

# Or with uvicorn directly
uvicorn src.fastapi_server:app --reload --host 0.0.0.0 --port 8000
```

### Adding New Endpoints

1. Add your endpoint function to `src/fastapi_server.py`
2. Add appropriate request/response models using Pydantic
3. Add tests in `tests/test_fastapi_integration.py`
4. Update this documentation

### CORS Configuration

For cross-origin requests, the server includes basic CORS headers. For production use, consider configuring proper CORS settings:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Production Deployment

### Using Gunicorn + Uvicorn Workers

```bash
gunicorn src.fastapi_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "src.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Set these environment variables for production:

```bash
# AI Provider API Keys
GOOGLE_API_KEY=your_google_key
OPENAI_API_KEY=your_openai_key  
COHERE_API_KEY=your_cohere_key
OPENROUTER_API_KEY=your_openrouter_key

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

## Troubleshooting

### Common Issues

1. **Character not found**: Ensure character files exist in the `characters/` directory
2. **AI processor errors**: Check that required API keys are set in environment variables
3. **Connection refused**: Make sure the server is running on the correct host/port
4. **CORS errors**: Configure CORS middleware for cross-origin requests

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or use the test script for diagnostics:

```bash
python test_fastapi.py
```

The test script will validate all endpoints and provide detailed error information if issues occur.