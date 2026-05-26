"""Centralized configuration — loads secrets from environment variables."""

import os


def get_required_env(name: str) -> str:
    """Return env var value or raise if missing."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set")
    return value


OPENAI_API_KEY = get_required_env("OPENAI_API_KEY")
OPENAI_ENDPOINT = get_required_env("OPENAI_ENDPOINT")
BLOB_CONNECTION_STRING_PRIMARY = os.environ.get("BLOB_CONNECTION_STRING_PRIMARY", "")
BLOB_CONNECTION_STRING_SECONDARY = os.environ.get("BLOB_CONNECTION_STRING_SECONDARY", "")
