"""Tracing of agent runs with Logfire.

Traces show every model request with its instructions, messages, tool calls and token usage, which is what prompt
iteration needs. They are exported only when a Logfire token is configured (``LOGFIRE_TOKEN`` or ``logfire auth``);
console output stays off because the terminal UI owns the screen. Scrubbing is off because story text routinely
contains words such as "secret" or "password" that would otherwise be redacted from the traces.
"""

import logfire

SERVICE_NAME = "storyline"


def configure_tracing() -> None:
    """Record Pydantic AI agent runs and export them when a Logfire token is present."""
    logfire.configure(service_name=SERVICE_NAME, send_to_logfire="if-token-present", console=False, scrubbing=False)
    logfire.instrument_pydantic_ai()
