# Storyline

A CLI interactive LLM-driven roleplaying chat with a configurable NPC character.

## Architecture

Built on `haystack-ai`, utilizes an LLM-based pipeline consisting of the following components in a more-or-less sequential fashion:

1. Retrieve conversation memory (list of summarized user actions and character actions).
2. Run a planning prompt (evaluate the user request to determine the action, intent, next steps to take and how it affects the character state).
3. Update the character state.
4. Feed that to the response prompt (generate the response text based on the action plan and character state).
5. Update conversation memory with the data from current step and store it.
6. Respond to user and await the next message.

## Problems and Ideas

**Problem**: Character tends to avoid moving the plot unless given a direct instruction or hint towards the next thing.

Solution 1: Create a separate "plot director / playwright" system to evaluate the response (or rather, an action plan) and loop the logic execution until the plan is moving the plot enough and is engaging.

Solution 2: Add a document store and a separate system to analyze (or search for?) existing stories and summarize them to extract plot points and character behaviour.

*maybe use solution 1 to trigger solution 2*
  
------

**Problem**: Character repeats the same phrases over and over again (which fit stylistically, but in a real interaction they won't happen multiple times)

Solution 1: Add a document store (embedding-based?) to store last character responses and validate if the next response matches it too closely (at least partially) + rerun the query if detects repetition. How to score the similarity and set up the threshold?