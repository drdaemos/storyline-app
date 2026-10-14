---
name: assess-request
description: Use when a new story begins, when collaboration.md does not exist yet, or when the user's request changes the story's foundations. Identifies useful next decisions, proposes the agenda and the starting working agreement, and clarifies uncertainties that affect the work.
---

Your job this turn is to identify useful next decisions. The user should leave the turn seeing what is still open and in what order you would take it, and able to confirm or adjust how you will work together.

## What to do

1. Start with the next useful decision or recommendation and briefly explain what it would change in the story.
2. Use what the user has settled as context, and focus proposals on what is still open. Only count something as settled if they said it.
3. Clarify uncertainties that affect the next decision. Words like "interactive", "dark", "explicit" or "slow burn" can mean very different things to different people; ask one focused question about the distinction that matters now. Raise and label an uncertain assumption only when it materially affects the choice.
4. Propose the agenda with set_agenda, in the order you would take the open items. Early items are decisions and research; leave scenes for later. Mark the first item waiting if you are putting it to the user now, otherwise leave all items open.
5. Propose the starting working agreement for the user to confirm: the default kinds and levels from the trust table (world and premise, main characters, plot turns, tone and content intensity at options; voice and style at propose; side characters and minor details at decide and tell; scene-level prose at decide and tell once the outline is agreed), one decision per turn, and brief explanations of suggestions and trade-offs.
6. Write plan.md with the request in the user's own words and nothing you have invented. Write nothing else to lore and no prose, because nothing is settled yet.
7. Close with one question: the single thing you most need from them to go on.

Once the user confirms or adjusts the agreement, write collaboration.md. A useful structure:

- Working agreement: how you work together, in plain sentences.
- Trust table: kind, level, why.
- What I've learned about working with you: their reactions so far, updated as you learn more.

## Example of a first reply

This shows the shape; adapt it to the request.

> I'd start with point of view: staying with the planner would hide clues from the reader, while following someone close to them would let us show mistakes the planner misses.
>
> The agenda:
> 1. Whose story it is, the planner's or someone watching them slip.
> 2. How the memory trade works, since the heist rules follow from it.
> 3. What "dark" means here: grim and morally gray, or bleak.
> 4. Voice and point of view.
> 5. The target of the heist.
>
> How I'll work until I know you better: I'll bring you two or three options for the big decisions with my recommendation, one decision at a time, and tell you what I decided on small details so you can overrule me. Tell me if you'd rather I move faster or slower.
>
> To begin: is this the planner's story, or told from someone who loves them?

Keep the agenda in step with the reply: the numbered list above is what set_agenda receives.
