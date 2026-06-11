"""Process-level test safety: hermetic environment for every test.

DatabaseConfig resolves DATABASE_URL / DB_* lazily from the environment, so a
developer's exported vars (or a stray load_dotenv) would silently redirect
registries away from their per-test memory_dir. Scrub them for every test.

LLM SDK clients refuse to construct without an API key in env; tests must never
depend on a developer's real keys, so dummy keys are provided when absent
(outbound calls stay forbidden — processors are mocked per testing rules).
"""

import os

import pytest

_DB_ENV_VARS = ("DATABASE_URL", "DB_TYPE", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
_API_KEY_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "COHERE_API_KEY")


@pytest.fixture(autouse=True)
def _isolate_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _DB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name in _API_KEY_VARS:
        if not os.environ.get(name):
            monkeypatch.setenv(name, "test-key")
