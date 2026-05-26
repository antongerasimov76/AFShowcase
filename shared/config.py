"""Shared configuration module for Azure Functions."""
import os


# Azure OpenAI settings – must be supplied via environment variables.
OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_KEY", "")

# Supported Azure Blob Storage accounts mapped to their env-var names.
_BLOB_CONN_ENV_VARS = {
    "getaianswerb0488d": "BLOB_CONN_GETAIANSWER",
    "m9aitasks": "BLOB_CONN_M9AITASKS",
}


def get_blob_connection_string(account_name: str) -> str:
    """Get blob storage connection string for the given account.

    Raises:
        ValueError: if account_name is not a supported storage account.
        RuntimeError: if the corresponding env var is not set.
    """
    env_var = _BLOB_CONN_ENV_VARS.get(account_name)
    if env_var is None:
        raise ValueError(f"Unknown storage account: {account_name}")
    conn_str = os.environ.get(env_var, "")
    if not conn_str:
        raise RuntimeError(f"Missing environment variable: {env_var}")
    return conn_str


def get_openai_headers() -> dict:
    """Get headers for Azure OpenAI API calls.

    Raises:
        RuntimeError: if AZURE_OPENAI_KEY or AZURE_OPENAI_ENDPOINT is not set.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing environment variable: AZURE_OPENAI_KEY")
    if not OPENAI_ENDPOINT:
        raise RuntimeError("Missing environment variable: AZURE_OPENAI_ENDPOINT")
    return {
        "Content-Type": "application/json",
        "api-key": OPENAI_API_KEY,
    }
