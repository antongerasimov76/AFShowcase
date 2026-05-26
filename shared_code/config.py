"""Centralized configuration module.

All secrets and endpoints are loaded from environment variables.
For local development, set them in local.settings.json (which is .gitignored).
For production, set them in Azure Function App Application Settings.
"""
import os


def get_required_env(name: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Required environment variable '{name}' is not set.")
    return value


# Azure OpenAI
OPENAI_API_KEY = get_required_env("OPENAI_API_KEY")
OPENAI_ENDPOINT = get_required_env("OPENAI_ENDPOINT")

# Azure Blob Storage
BLOB_CONNECTION_STRING_PRIMARY = get_required_env("BLOB_CONNECTION_STRING_PRIMARY")
BLOB_CONNECTION_STRING_SECONDARY = os.environ.get("BLOB_CONNECTION_STRING_SECONDARY", "")
