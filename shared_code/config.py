"""Centralized configuration — loads secrets from environment variables."""

import os


def get_required_env(name: str) -> str:
    """Return env var value or raise ValueError if missing."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Required environment variable '{name}' is not set")
    return value


def get_openai_api_key() -> str:
    """Lazily resolve the OpenAI API key from environment."""
    return get_required_env("OPENAI_API_KEY")


def get_openai_endpoint() -> str:
    """Lazily resolve the OpenAI endpoint from environment."""
    return get_required_env("OPENAI_ENDPOINT")
