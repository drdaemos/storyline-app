"""Model resolution for the writer agent.

OpenRouter's chat-completions API drops Anthropic's server-side web search blocks from responses, so a Claude turn that
searched and then called one of our tools cannot be replayed: Anthropic rejects the altered thinking blocks.
OpenRouter's Anthropic-compatible Messages endpoint returns every block intact, so Claude models are routed through it.
"""

import os
from functools import cache

from pydantic_ai.exceptions import UserError
from pydantic_ai.models import Model, parse_model_id
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers import infer_provider_class
from pydantic_ai.providers.anthropic import AnthropicProvider

OPENROUTER_ANTHROPIC_PREFIX = "openrouter:anthropic/"
OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"


class ModelNameError(ValueError):
    """Raised when a model name is not one Pydantic AI can resolve, so a turn on it could never run."""


def validate_model_name(model_name: str) -> None:
    """Raise ``ModelNameError`` unless the name is a ``provider:model`` one for a provider Pydantic AI knows.

    Only the name is checked: no API key is needed, and a model the provider does not offer still fails at its first turn.
    """
    provider_name, model_id = parse_model_id(model_name)
    if provider_name is None or not model_id:
        raise ModelNameError(f"Unknown model: {model_name}. Name a model as provider:model, for example openrouter:meta/muse-spark-1.3.")
    try:
        infer_provider_class(provider_name)
    except ValueError:
        raise ModelNameError(f"Unknown model provider {provider_name!r} in {model_name!r}.") from None


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
