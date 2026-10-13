---
RULES FOR AI AGENTS: This file is read-only for you. Do not edit it.
---

# Storyline as a Writer Room system

General design for the new version of the creative writing AI system was influenced by the following:

- Typical turn-based roleplay doesn’t work like I want. Too boring, too sloppy, can’t autonomously drive the story forward even if I beg for it. Constantly requiring my input at arbitrary moments.
- It's context / execution is too stiff - things like prompts / stages / character profiles are hard-coded or predefined, and I have to constantly correct it while the changes are not persisted anywhere outside the story.
- There is no separation of my OOC guidance vs what I perform as a persona in the context. Agent usually understands the separation, but this context is left within the same sequence of turns.
- We don’t technically have to one shot this. When I guide actively, the story ends up being better (subjectively). If model asks Qs and properly tracks learnings and does research on its own, it works better overall compared to me predefining everything in the starter prompt.
- Problem itself is very complex and reader dependent. I don’t know all the answers and don’t want to basically write my story before I read it. I usually have a rough concept in mind and want to explore it, but something else does the magic of simulating the world and progressing the story forward. Sometimes I even just want to read without any further input from my side.
- I haven’t yet found the way to introduce llm-as-a-judge into the flow, but I’m sure it may improve quality and conformance to learnings. Currently nothing post-reads model outputs and does the reflection akin to ChatGPT dreaming stuff.
- It would be awesome not to hardcode system at all - maybe we can have an abstract infra layer and then a model both does the creative writing AND builds the system and gathers learnings around it. Decides how to store it, how to improve and measure outputs etc. I can act as the initial input and one of the judges.
- I envision this system may work similarly to AI coding agents. However, we have to be careful about the context window growth as it very quickly drains the API budgets.
- There should be a very clever way to manage context window and auto-reduce it without involving the user. Request-response system here is not mapped to the actual story development, but serves as a technical layer to optimize content delivery and context usage.
- Agent should be able to evolve it's tools / prompts over time, accumlating preferences, knowledge, research on the creative writing topic. We can supply Storyline with a seed file / basic setup and allow to export the current configuration, but it will be mostly agent working on this, not user directly.

As for my personal preferences:

- I’m more than comfortable delegating my persona choices. I have set the general idea and shape of characters before writing, and I want to see how it may act out, but I don’t want to plan ahead myself. 
- During the play, I may give additional direction (and I guess there should be an interrupt moment for this) or feedback. I want to evolve beyond turn based model where ai has to guess when to relinquish control and how much to write and how to process my inputs. 
- Instead, during writing, maybe a prompt is looping and has a set of tools - “edit story”, “ask feedback”, “ask for direction” (or this could complete the response turn) and I also have a ways to “steer” the model mid-response. The actual story text doesn’t have to immutable (and can actually be adjusted retrospectively, that's okay), so the model can think separately from writing the story.

## Tech stack

I believe that Writer Room version should use the following tech stack:

- PydanticAI + Harness as the LLM / AI Agent abstraction layer. I didn't really like Langchain back in the days and now prefer something more customizable.
- Must use types, typed objects, modern Python, uv, ruff, must be covered with practical tests.
- DB stuff should use alembic, PostgreSQL but should be limited use and mostly for stable infra, not for story work (except for keeping runtime session stuff).
- Clerk is for auth stuff + DB-stored users.
- User interaction must be streaming + agent-rich, like in Codex / Claude Code, with showed tool calls and stuff.
- Core system should be mostly uniform / have feature parity for both UI (via API) and CLI.

## Minimal implementation

We can start with the pure CLI harness that works in a local file-based workspace and supports the following:

- Storing runtime configuration in the local .config files
- Abstracted LLM connection
- Terminal UI similar to coding harnesses like Claude Code, Codex, OpenCode
- Minimal toolset of `edit_file`, `list_lore`, `read_manuscript`, `interview_user`
- Plan-Act-Evaluate looping
