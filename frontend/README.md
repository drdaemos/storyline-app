# Storyline web interface

Vue 3, TypeScript and Vite. It is the hosted counterpart of the terminal UI: it offers the same operations and renders the same events of the room protocol, and a test keeps it that way.

## Run

Run everything from the repository root.

```
npm --prefix frontend install
npm --prefix frontend run dev          # http://localhost:3000, proxies /api and /health to localhost:8000
npm --prefix frontend run lint
npm --prefix frontend run type-check
npm --prefix frontend run test:run
npm --prefix frontend run build        # writes ../static
```

Sign-in uses Clerk only when `VITE_CLERK_PUBLISHABLE_KEY` is set (see `.env.default`). Without it the app runs with no auth and sends no token.

## Structure

```
src/
  protocol/   protocol.json (generated), types.ts, parity.test.ts
  api/        client.ts (one function per operation), sse.ts (stream parser, reconnecting stream), auth.ts
  room/       roomState.ts (state + reducers, pure), useRoom.ts, useStoryFiles.ts, format.ts
  markdown/   Markdown rendering (HTML disabled), fresh ink, lore header stripping
  components/ the room's parts; they read room state and call the client, with no protocol logic
  views/      ShelfView (/), RoomView (/stories/:name)
  auth/       Clerk gate, token bridge, sign-in screen
  theme/      the look, and nothing else does
```

## The protocol

`src/protocol/protocol.json` comes from the Python source of truth. Regenerate it from the repository root:

```
uv run python -m storyline.room.export
```

`src/protocol/types.ts` is written by hand. `parity.test.ts` fails when `protocol.json` gains an event with no reducer in `EVENT_REDUCERS` (`room/roomState.ts`), an operation with no function in `OPERATION_CLIENT` (`api/client.ts`), or a field that `types.ts` does not list, and when the reverse is true. Fix the failure by adding the reducer, client function or type, not by editing the test.

## The theme rule

Every colour, font, texture, shadow and radius is a CSS custom property defined in `src/theme/tokens.css`. Fonts are loaded in `src/theme/fonts.css`. Page-wide and Markdown styles are in `base.css` and `prose.css`, all drawn from the tokens. Components use `var(--name)` and never a literal colour, font family or shadow; `theme/theme.test.ts` fails if one does, or if a component uses a variable the theme does not define.

To change the look, replace the `src/theme/` folder with one that defines the same variable names and exports `clerkAppearance` from `index.ts`. No component changes.
