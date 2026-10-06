"""Model resolution for the writer agent.

OpenRouter's chat-completions API drops Anthropic's server-side web search blocks from responses, so a Claude turn that
searched and then called one of our tools cannot be replayed: Anthropic rejects the altered thinking blocks.
OpenRouter's Anthropic-compatible Messages endpoint returns every block intact, so Claude models are routed through it.
"""

import os
from functools import cache

from pydantic_ai.exceptions import UserError
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

OPENROUTER_ANTHROPIC_PREFIX = "openrouter:anthropic/"
OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"


@cache
def resolve_model(model_name: str) -> Model | str:
    """Return the model to run for a model name, keeping names Pydantic AI resolves correctly on its own."""
    if not model_name.startswith(OPENROUTER_ANTHROPIC_PREFIX):
        return model_name
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise UserError("Set the `OPENROUTER_API_KEY` environment variable to use OpenRouter models.")
    provider = AnthropicProvider(api_key=api_key, base_url=OPENROUTER_ANTHROPIC_BASE_URL)
    return AnthropicModel(model_name.removeprefix("openrouter:"), provider=provider)
