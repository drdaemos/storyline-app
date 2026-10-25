# Storyline

An AI writer room: an AI writer collaborates with you on stories kept as plain files in a workspace. Use it in the terminal (`storyline write`) or in the browser (`storyline serve`).

See `AGENTS.md` for development commands and `frontend/README.md` for the web UI.

## Deploy on Railway

The repository deploys as one service built from `Dockerfile` (configured by `railway.json`): the Vue frontend is built and served by the FastAPI server at `/`, and `/health` is the healthcheck.

1. Create a Railway project from this repository.
2. Add a **volume** to the service and mount it at `/data`. Stories live there; without it they are lost on every deploy.
3. Set service variables:
   - A model provider key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY`) and, optionally, `STORYLINE_MODEL` (and `STORYLINE_REVIEW_MODEL` for the roleplay reviewer).
   - For a hosted multi-user deployment: `AUTH_ENABLED=true`, `CLERK_SECRET_KEY`, `VITE_CLERK_PUBLISHABLE_KEY`, and `CLERK_AUTHORIZED_PARTIES` set to your public origin (e.g. `https://storyline.up.railway.app`).
   - Leave `AUTH_ENABLED` unset to run as a single local user with no sign-in; do not expose that publicly.
4. Generate a domain under Settings → Networking. Railway supplies `PORT`; the server listens on it.

`VITE_CLERK_PUBLISHABLE_KEY` is baked into the frontend at build time, so changing it needs a redeploy. A service with a volume restarts with a short outage on each deploy and cannot have replicas.
