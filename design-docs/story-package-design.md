---
RULES FOR AI AGENTS: This file is read-only for you. Do not edit it.
---

# Storyline with Story Packages

Core idea: splitting stories to separate characters, personas, lorebooks, rulesets and settings, and reassembling all of this dynamically makes no sense. All these parts are often interconnected and have to come as a package.

What can be separate is all the tech behind running this package - when to adjust the story, what to request from the user, how to retrieve context etc. This is what Storyline should become.

Authorship is also intended to be continuous and Storyline agent should dynamically adjust story per user instructions / preferences or learning from user's feedback in a per-user way.

## Design considerations

- Packages should support varying taxonomy of context files, as one story might be structured different to another.
- There should be a stable entry point into package and a way to partially retrieve context (to avoid bloating the agent context window immediately on first prompt).
- There should be a way to apply per-user agent created adjustments to the story (ideally, hiding the overridden context completely to avoid context poisoning). 
- Storyline should have an authorship module that can create such packages (and this module will probably carry the generic story generation logic).

## Core idea

Technically, all these considerations can be satisfied just with text files.
