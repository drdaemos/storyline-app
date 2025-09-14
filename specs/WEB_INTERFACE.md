# Implementation Specification for Character Chat Interface

## Functional Requirements

### Character Management

- Display all available characters from backend
- Support character selection to view associated sessions
- Create new characters through manual form entry
- Import character definitions via YAML format
- Generate character avatars based on appearance description
- AI-assisted character field generation (fills empty fields based on existing content)

### Session Management

- Display all sessions for selected character with metadata (timestamp, last message preview)
- Create new chat sessions with unique session IDs
- Continue existing sessions maintaining conversation  context
- Delete/clear specific sessions through API
- Session persistence handled entirely by backend

### Chat Interface

- Real-time streaming responses using Server-Sent Events
- Display thinking indicator during AI processing
- Support message regeneration (re-request last AI response)
- Rewind functionality to remove last user-AI exchange
- Markdown rendering support for formatted responses
- Auto-scroll to latest message
- Prevent message sending while AI is responding

### Settings & Configuration

- Select AI processor (google, openai, cohere, etc.) per session
- Persist non-critical settings in localStorage
- Settings accessible via dropdown menu
- Settings apply to new sessions only (not retroactive)

## User Flows
### Primary Flow: Start Conversation

1. User selects character from grid
2. System displays available sessions for character
3. User clicks session or "Start New Session"
4. System navigates directly to chat interface
5. User sends message
6. System streams AI response in real-time

### Secondary Flow: Character Creation

1. User clicks "Create New" character card
2. System presents creation form
3. User fills fields OR imports YAML
4. User optionally generates avatar
5. User saves character
6. System returns to character selection

### Alternative Flow: Session Management

- User views session list for character
- User can continue existing session
- User can start new session
- User can rewind last exchange in active chat
- User can regenerate last AI response

## Business Rules
### Character Creation

- Name field is mandatory
- Maximum 10 key locations per character
- Appearance field required for photo generation
- AI generation only fills empty fields (incremental)
- User relationship is predefined and required

### Chat Behavior

- One active response at a time
- Cannot send message while AI is thinking
- Rewind removes both user and AI messages as a pair
- Regenerate only available for last AI message
- Session ID persists in URL for bookmarking/sharing

### Data Management

- All conversation data stored on backend automatically
- No sensitive data in localStorage
- Sessions tied to character name
- Character list cached until page refresh
- Settings changes don't affect active sessions

## Error Handling
### Network Failures

- Display user-friendly error message
- Offer retry option for failed requests
- Maintain local message state during temporary disconnection

### Validation Errors

- Prevent empty message submission
- Validate character name before saving
- Show inline validation for required fields
- Prevent navigation with unsaved changes (confirmation dialog)

### Stream Interruptions

- Allow manual retry for interrupted streams
- Clear thinking indicator on error
- Preserve partial responses when possible
- Provide feedback when regeneration fails

## Technology Stack

- Vue.js 3 (Composition API preferred)
- Native Fetch API for HTTP requests
- EventSource API for Server-Sent Events
- LocalStorage for settings persistence
- CSS with CSS Variables for theming (no preprocessors)

## Project Structure

src/
├── App.vue
├── views/
│   ├── StartView.vue
│   ├── ChatView.vue
│   └── CharacterCreationView.vue
├── components/
│   ├── CharacterCard.vue
│   ├── SessionList.vue
│   ├── ChatMessage.vue
│   ├── ChatInput.vue
│   └── SettingsMenu.vue
├── composables/
│   ├── useApi.js
│   ├── useLocalSettings.js
│   └── useEventStream.js
└── utils/
    └── formatters.js

## Core Composables
### useApi.js

Wrapper for API calls with error handling:

getCharacters() → GET /characters
getCharacterInfo(name) → GET /characters/{character_name}
getSessions() → GET /sessions
createCharacter(payload) → POST /characters
deleteSession(id) → DELETE /sessions/{session_id}
handleInteraction(payload) → POST /interact (returns EventSource)

### useLocalSettings.js
LocalStorage management for:

aiProcessor (default: 'google')
theme (future expansion)
lastSelectedCharacter (convenience)

### useEventStream.js
SSE handling for chat responses:

Initialize EventSource connection
Parse streaming chunks: {"type": "chunk", "content": "..."}
Handle completion: {"type": "complete"}
Error recovery and reconnection logic
Cleanup on component unmount

## Views Specification
### StartView.vue
State Management:

characters: ref([]) - loaded from API
sessions: ref([]) - loaded from API
selectedCharacter: ref(null)
showSettings: ref(false)

Key Methods:

loadCharacters() - Fetch and display available characters
selectCharacter(name) - Load sessions for selected character
navigateToChat(sessionId) - Route to chat with params

Behavior:

On mount: Load characters immediately
Character selection triggers session loading
Direct navigation to chat on session/new click
Settings menu toggle with click-outside detection

### ChatView.vue
Props/Route Params:

characterName: string
sessionId: string | 'new'

State Management:

messages: ref([]) - conversation history
isThinking: ref(false) - shows thinking indicator
streamingContent: ref('') - accumulates current response
eventSource: ref(null) - SSE connection

Key Methods:

sendMessage(text) - Initiate interaction with backend
handleStreamChunk(data) - Append to streamingContent
completeStream() - Move streaming to messages array
rewindLastExchange() - Remove last user-AI pair
regenerateLastMessage() - Re-request last AI response

SSE Integration:
```
const eventSource = new EventSource('/interact', {
  method: 'POST',
  body: JSON.stringify({
    character_name: characterName,
    user_message: userInput,
    session_id: sessionId === 'new' ? null : sessionId,
    processor_type: localSettings.aiProcessor
  })
})

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'chunk') {
    streamingContent.value += data.content
  } else if (data.type === 'complete') {
    completeStream()
    eventSource.close()
  }
}
```

### CharacterCreationView.vue
State Management:

Form fields as individual refs
locations: ref(['']) - dynamic array (max 10)
yamlImport: ref('') - for YAML import feature

Key Methods:

addLocation() - Push empty string to locations array
removeLocation(index) - Splice from locations array
generatePhoto() - Call backend when appearance filled
generateCharacter() - AI-fill empty fields based on existing
importYaml() - Send YAML to backend for processing
saveCharacter() - Submit to backend API

YAML Import Feature:

Add tab/toggle for "Import YAML" vs "Manual Entry"
Textarea for YAML paste
"Process YAML" button sends to backend endpoint (needs API addition)
Backend parses and returns populated fields

## Component Specifications
### CharacterCard.vue
Props:

character: Object
selected: Boolean

Emits:

select - When clicked

### SessionList.vue
Props:

sessions: Array
characterName: String

Emits:

select-session - With session ID
new-session - For new session creation

Computed:

Format relative timestamps (e.g., "2 hours ago")
Truncate preview messages

### ChatMessage.vue
Props:

message: Object - {author, content, isUser, timestamp}
isStreaming: Boolean - Show typing animation
showActions: Boolean - Show regenerate button

Emits:

regenerate - Request message regeneration

### SettingsMenu.vue
Props:

show: Boolean

Emits:

update:show - For v-model binding
setting-changed - With {key, value}

Settings:

AI Processor dropdown (persisted to localStorage)
Future: Theme selection, notification preferences

Routing Configuration:

```
const routes = [
  { path: '/', component: StartView },
  { path: '/chat/:characterName/:sessionId', component: ChatView },
  { path: '/create', component: CharacterCreationView }
]
```

## API Integration Notes

Session Management:

- New sessions: Send session_id: null to /interact
- Backend generates and returns session ID in response
- Store in URL params for sharing/bookmarking

Streaming Responses:

- Use native EventSource, no libraries needed
- Accumulate chunks in temporary variable
- Move to messages array on completion

Error Handling:

- Network errors: Show toast/alert, offer retry
- Invalid character/session: Redirect to start

## Mobile Responsiveness

- Use CSS Grid with minmax() for character cards
- Fixed bottom chat input with position: sticky
- Touch-friendly 44px minimum target sizes
- Viewport meta tag for proper scaling
- CSS media query at 768px breakpoint

## Performance Optimizations

- Lazy load character images with loading="lazy"
- Virtual scrolling for long chat histories (if needed)
- Debounce YAML import processing (500ms)
- Memoize formatted timestamps
- Use v-show instead of v-if for frequently toggled elements

## State Persistence

LocalStorage keys:

storyline_ai_processor: Selected AI
storyline_last_character: For convenience
storyline_theme: Future expansion

No conversation data stored locally
Settings loaded in App.vue setup

## Build Configuration

Vite as build tool (comes with Vue 3)
No additional plugins needed
Environment variables for API base URL
Production build with proper CSP headers

## Backend API spec (might not be sufficient, will be expanded to support flows)

{
  "openapi": "3.1.0",
  "info": {
    "title": "Storyline API",
    "description": "Interactive character chat API",
    "version": "0.1.0"
  },
  "paths": {
    "/health": {
      "get": {
        "summary": "Health Check",
        "description": "Health check endpoint that verifies database connectivity.",
        "operationId": "health_check_health_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HealthStatus"
                }
              }
            }
          }
        }
      }
    },
    "/": {
      "get": {
        "summary": "Root",
        "description": "Root endpoint serving the web interface.",
        "operationId": "root__get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api": {
      "get": {
        "summary": "Api Info",
        "description": "API information endpoint.",
        "operationId": "api_info_api_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": {
                    "type": "string"
                  },
                  "type": "object",
                  "title": "Response Api Info Api Get"
                }
              }
            }
          }
        }
      }
    },
    "/characters": {
      "get": {
        "summary": "List Characters",
        "description": "List available characters.",
        "operationId": "list_characters_characters_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "items": {
                    "type": "string"
                  },
                  "type": "array",
                  "title": "Response List Characters Characters Get"
                }
              }
            }
          }
        }
      },
      "post": {
        "summary": "Create Character",
        "description": "Create a new character from either structured data or freeform YAML text.",
        "operationId": "create_character_characters_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/CreateCharacterRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/CreateCharacterResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/characters/{character_name}": {
      "get": {
        "summary": "Get Character Info",
        "description": "Get information about a specific character.",
        "operationId": "get_character_info_characters__character_name__get",
        "parameters": [
          {
            "name": "character_name",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Character Name"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  },
                  "title": "Response Get Character Info Characters  Character Name  Get"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/sessions": {
      "get": {
        "summary": "List Sessions",
        "description": "List all sessions from conversation memory.",
        "operationId": "list_sessions_sessions_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "items": {
                    "$ref": "#/components/schemas/SessionInfo"
                  },
                  "type": "array",
                  "title": "Response List Sessions Sessions Get"
                }
              }
            }
          }
        }
      }
    },
    "/sessions/{session_id}": {
      "delete": {
        "summary": "Clear Session",
        "description": "Clear a specific session.",
        "operationId": "clear_session_sessions__session_id__delete",
        "parameters": [
          {
            "name": "session_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Session Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  },
                  "title": "Response Clear Session Sessions  Session Id  Delete"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/interact": {
      "post": {
        "summary": "Interact",
        "description": "Interact with a character and get streaming response via Server-Sent Events.\n\nThe response will be streamed as Server-Sent Events with the following format:\n- data: {\"type\": \"chunk\", \"content\": \"response_text\"}\n- data: {\"type\": \"complete\"}",
        "operationId": "interact_interact_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/InteractRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "Character": {
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1,
            "title": "Name",
            "description": "Name of the character"
          },
          "role": {
            "type": "string",
            "minLength": 1,
            "title": "Role",
            "description": "Profession or role in the story"
          },
          "backstory": {
            "type": "string",
            "minLength": 1,
            "title": "Backstory",
            "description": "Previous experiences, events and relationships"
          },
          "personality": {
            "type": "string",
            "title": "Personality",
            "description": "Personality traits and characteristics",
            "default": ""
          },
          "appearance": {
            "type": "string",
            "title": "Appearance",
            "description": "Physical description",
            "default": ""
          },
          "relationships": {
            "additionalProperties": {
              "type": "string"
            },
            "type": "object",
            "title": "Relationships",
            "description": "Relationships with other characters"
          },
          "key_locations": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Key Locations",
            "description": "Important locations for the character"
          },
          "setting_description": {
            "type": "string",
            "title": "Setting Description",
            "description": "Description of the world/setting the character exists in",
            "default": ""
          }
        },
        "type": "object",
        "required": [
          "name",
          "role",
          "backstory"
        ],
        "title": "Character",
        "description": "Pydantic model for representing a character in the role-playing interaction."
      },
      "CreateCharacterRequest": {
        "properties": {
          "data": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/Character"
              },
              {
                "type": "string"
              }
            ],
            "title": "Data",
            "description": "Either structured character data or freeform YAML text"
          },
          "is_yaml_text": {
            "type": "boolean",
            "title": "Is Yaml Text",
            "description": "Set to true if 'data' contains freeform YAML text",
            "default": false
          }
        },
        "type": "object",
        "required": [
          "data"
        ],
        "title": "CreateCharacterRequest",
        "description": "Request model for creating a character card."
      },
      "CreateCharacterResponse": {
        "properties": {
          "message": {
            "type": "string",
            "title": "Message"
          },
          "character_filename": {
            "type": "string",
            "title": "Character Filename"
          }
        },
        "type": "object",
        "required": [
          "message",
          "character_filename"
        ],
        "title": "CreateCharacterResponse",
        "description": "Response model for character creation."
      },
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "HealthStatus": {
        "properties": {
          "status": {
            "type": "string",
            "title": "Status"
          },
          "conversation_memory": {
            "type": "string",
            "title": "Conversation Memory"
          },
          "summary_memory": {
            "type": "string",
            "title": "Summary Memory"
          },
          "details": {
            "anyOf": [
              {
                "additionalProperties": {
                  "type": "string"
                },
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Details"
          }
        },
        "type": "object",
        "required": [
          "status",
          "conversation_memory",
          "summary_memory"
        ],
        "title": "HealthStatus"
      },
      "InteractRequest": {
        "properties": {
          "character_name": {
            "type": "string",
            "minLength": 1,
            "title": "Character Name",
            "description": "Name of the character to interact with"
          },
          "user_message": {
            "type": "string",
            "minLength": 1,
            "title": "User Message",
            "description": "User's message to the character"
          },
          "session_id": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Session Id",
            "description": "Optional session ID for conversation continuity"
          },
          "processor_type": {
            "type": "string",
            "title": "Processor Type",
            "description": "AI processor type (google, openai, cohere, etc.)",
            "default": "google"
          }
        },
        "type": "object",
        "required": [
          "character_name",
          "user_message"
        ],
        "title": "InteractRequest"
      },
      "SessionInfo": {
        "properties": {
          "session_id": {
            "type": "string",
            "title": "Session Id"
          },
          "character_name": {
            "type": "string",
            "title": "Character Name"
          },
          "message_count": {
            "type": "integer",
            "title": "Message Count"
          },
          "last_message_time": {
            "type": "string",
            "title": "Last Message Time"
          },
          "last_character_response": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Last Character Response"
          }
        },
        "type": "object",
        "required": [
          "session_id",
          "character_name",
          "message_count",
          "last_message_time"
        ],
        "title": "SessionInfo"
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      }
    }
  }
}