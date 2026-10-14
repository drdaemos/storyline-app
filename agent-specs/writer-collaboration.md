# Writer collaboration design

How the writer agent works with the user. Agreed with the user on 2026-10-09 after the `bloodlines` session, where
the agent settled the city, protagonist, cast, three-act arc, a hidden twist, world rules and style in its first turn,
even though the user had asked it not to rush.

## Goals

The user co-writes and directs. They mostly talk to the agent rather than writing themselves, as if dictating, and
sometimes speak or act as a character. They edit files lightly at most. They want to:

- see why each suggestion serves the request, its likely effects and trade-offs, and any uncertain assumption that materially affects the choice, so misunderstandings can be corrected;
- take one decision at a time, because five open items at once is too many to process;
- build trust gradually: the agent starts careful, learns from their reactions, and takes on more where it has earned it;
- see the agenda at all times, like a todo list with statuses.

How much the agent decides alone, how much prose goes in one turn, and how the user takes part all differ per story
and per writer. The system adapts through a negotiated, learned working agreement rather than fixed rules.

## Principles

- **The model chooses.** No code routes turns or gates tools. The model knows what it has (tools and loadable prompt
  pieces) and decides what to use. Behaviour is explained in prompts, with examples.
- **Small core prompt, pieces on demand.** The core holds identity, the loop and the memory rules. Phase-specific
  guidance lives in skills the model loads when the work calls for them.
- **Everything that has to last is in files.** The story, the agenda and the collaboration all persist in the story
  directory and survive conversation compaction.

## The loop

Each turn:

1. **Read the message and decide what kind it is:** a decision, an idea, a correction, a question, an in-character
   contribution, or a signal about the collaboration ("just do it", praise, frustration). If ambiguity affects the next
   decision, ask one focused question about the uncertain point.
2. **Remember:** story facts go into canon (lore, plan). The user's reaction goes into `collaboration.md`: accepted as
   offered, changed, or rejected, and what that suggests.
3. **Pick one next thing** from the agenda.
4. **Check why the next action serves the request:** identify the supporting instruction or story fact, the intended
   effect and the assumptions it depends on. When presenting a consequential choice, explain why it fits and its likely
   effects, and compare the options' main trade-offs. Raise uncertain assumptions only when they materially affect the choice.
5. **Hand back:** end on the one question or decision the user needs to make, and update the agenda.

Each turn does concrete work. A turn that only asks questions wastes the user's time; a turn that settles several
things at once takes the story away from them.

## Trust

Trust is tracked per kind of decision. Each kind has a level:

| Level | Behaviour |
|---|---|
| options | Bring two or three genuinely different options with brief explanations of their trade-offs and a recommendation, then wait. |
| propose | Bring one recommendation with a brief explanation of how it serves the story, then wait for a yes. |
| decide and tell | Decide, and say what was decided so the user can overrule it. |
| decide quietly | Decide without mentioning it. |

Default kinds and starting levels, confirmed with the user in the first reply:

| Kind | Starting level |
|---|---|
| World and premise | options |
| Main characters | options |
| Plot turns | options |
| Tone and content intensity | options |
| Voice and style | propose |
| Side characters and minor details | decide and tell |
| Scene-level prose | decide and tell, once the outline is agreed |

The list is a starting point and grows from the user's reactions. When reactions inside one kind diverge, the agent
proposes splitting it. For example, the user waves through every side character but rewrites every antagonist, so
"antagonists" becomes its own kind. The user confirms each split.

- **Promotion is offered, never taken.** After a run of suggestions in one kind accepted unchanged, the agent offers
  to move that kind up a level, and the user confirms.
- **Stepping back is immediate.** A correction, a rejection or visible frustration in a kind moves it down a level
  without asking, and the agent says so.
- **Explicit instructions override the levels.** For example: "Decide the minor characters yourself", "write three
  scenes in one go", or "ask me before anyone dies".

## Files

| File | Role |
|---|---|
| `script.md` | The story text and nothing else. |
| Lore files (`*.md` with a summary/keywords header) | Settled canon: characters, places, world rules, research notes. Proposals stay out of lore until the user accepts them. |
| `plan.md` | The story's direction: the user's request in their own words, intentions, and the arc and next scenes once agreed. |
| `style.md` | Lasting preferences about the prose, from the user's feedback. |
| `collaboration.md` | The working agreement, the trust table (kind, level, why) and what the agent has learned about working with this user. Readable and editable by the user. |
| `agenda.json` | The agenda: ordered items with a status and, once settled, the outcome. |

`plan.md`, `style.md` and `collaboration.md` travel in every turn's story snapshot, and so does the agenda.

## Agenda

Each item has an id, a title, a status and an optional outcome. Statuses:

| Status | Meaning | Shown as |
|---|---|---|
| open | Not started. | ○ |
| working | The agent is on it this turn. | ● |
| waiting | Put to the user; the agent is waiting for their decision. | ◐ … waiting on you |
| settled | Decided; `outcome` holds the decision in a few words. | ✓ title — outcome |
| dropped | No longer needed. | ✗ (dim) |

The agent maintains the agenda with tools: replace the whole list, or update one item. While a story is open, the TUI
shows the agenda in a panel and refreshes it whenever an agenda tool runs. Early items are decisions and research.
Once writing starts, items become scenes.

## Prompt pieces

Core (`agent/prompts/writer.md`, always loaded): who the agent is, the files, the loop, trust, how to read the user's
messages, the shape of a reply.

Skills (`agent/skills/<name>/SKILL.md`, loaded by the model through `load_capability`):

| Skill | When |
|---|---|
| `assess-request` | A new story, or a request that changes the story's foundations: identify useful next decisions, clarify uncertainties that affect the work, propose the agenda and the starting agreement. |
| `research` | Learning a genre, trope or setting: search, report what to use, twist or avoid, and record notes in lore. |
| `develop-element` | Working out one element (setting, a character, conflict, voice) into options with brief explanations of their trade-offs. |
| `outline` | Proposing the arc and the next scenes once the foundations are settled. |
| `write-scene` | Drafting prose. |
| `revise` | Changing existing prose after feedback. |

In-character input is handled in the core prompt because it can arrive at any time.

## Testing

The user tests the collaboration by hand. Scripted evals keep the prose diagnostics and the checks for single moments
that still fit, such as "the first reply writes no prose". Scenarios that encoded the old behaviour, such as a bare
"Write me a story" producing prose in turn 1, are changed. Simulated users were considered and rejected.

## Open

- Whether to show trust levels and what the agent has learned about the user in the app as well as in
  `collaboration.md`.
- Model choice: Muse Spark is the default, and how well it follows this loop is untested.
