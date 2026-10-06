"""Tests for writer model resolution."""

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.anthropic import AnthropicModel

from storyline.agent import resolve_model


@pytest.fixture(autouse=True)
def _fresh_resolution():
    resolve_model.cache_clear()
    yield
    resolve_model.cache_clear()


def test_openrouter_claude_models_use_the_anthropic_messages_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    model = resolve_model("openrouter:anthropic/claude-opus-5.5")

    assert isinstance(model, AnthropicModel)
    assert model.model_name == "anthropic/claude-opus-5.5"
    assert model.base_url.startswith("https://openrouter.ai/api")


def test_other_model_names_are_left_to_pydantic_ai() -> None:
    assert resolve_model("openrouter:meta/muse-spark-1.3") == "openrouter:meta/muse-spark-1.3"
    assert resolve_model("anthropic:claude-opus-5-5") == "anthropic:claude-opus-5-5"


def test_openrouter_claude_models_require_the_openrouter_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(UserError, match="OPENROUTER_API_KEY"):
        resolve_model("openrouter:anthropic/claude-opus-5.5")
