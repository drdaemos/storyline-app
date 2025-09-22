# Storyline

A CLI interactive LLM-driven roleplaying chat with a configurable NPC character - creating a stage for creative writing for small stories (usually with two main characters).

## Usage

Prerequisites:

- Python >= 3.12
- Node >= 24.0

Build Python backend and Vue frontend:

```
./build.sh
```

Run for development with hot reload:

```
./dev.sh
```

Run in production:

```
uv run main.py serve [--host ""] [--port <int>]
```

## Architecture

The system utilizes an LLM-based pipeline consisting of the following components in a more-or-less sequential fashion:

1. Retrieve conversation memory (list of summarized user actions and character actions).
2. Run an evaluation prompt (evaluate the user request to determine the action, intent, next steps to take and how it affects the character state) - this has the full memory of previous evaluations and user messages.
4. Feed last evaluation to the response prompt (generate the response text based on the action plan and character state).
5. Update conversation memory with (user message, character evaluation, character response) exchange.
6. Respond to user and await for the next message.

Every N exchanges the conversation memory is summarized and further plot beats are generated (this is where the storytelling operates on a level of act).

Basically, pipeline operates on multiple levels:

- Character works with the lowest level: dialogue, actions, internal thinking - following user input and their own idea of story beats the fit the scene
- (every N exchanges) The scene is reevaluated based on the idea of point in narrative (e.g. is there a rising conflict / tension / escalation?). Act transition may be planned here. Next plot beats are generated for the following scene.

## Things not yet explored

- Using randomized external events to move the story and make both characters react
- Using /commands to enable out of character / story transition actions (outside the default pipeline)
- /rewind command to go back one step (remove last exchange from memory)
- Remove evaluation from memory (to save tokens / avoid extra response generation in eval)
- Additional prompt / logic to select the continuation option
- Additional actions in the UI should just send the slash /command - no extra endpoints
- Introduce Play Rulebook - support for skill checks / other forms of guiding the roleplay. Separate per genre: adventure / slice-of-life / romance etc.
