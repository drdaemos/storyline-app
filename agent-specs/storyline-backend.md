# Storyline backend architecture

Backend is composed of Python packages, each serving a different responsibility.

src/
    storyline/
        agent/              - writer agent, prompts and loop logic
        workspace/          - stories in a workspace (one package per subdirectory), story selection, script and lore operations
        tui/                - terminal interface for writing stories
        web/                - web server for the Storyline UI
        cli.py              - main application entrypoint with CLI options
        