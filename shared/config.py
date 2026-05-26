"""Shared configuration module for Azure Functions."""
import os


# Azure OpenAI settings
OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"
)
OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_KEY", "")

# Azure Blob Storage
BLOB_CONNECTION_STRINGS = {
    "getaianswerb0488d": os.environ.get("BLOB_CONN_GETAIANSWER", ""),
    "m9aitasks": os.environ.get("BLOB_CONN_M9AITASKS", ""),
}


def get_blob_connection_string(account_name: str) -> str:
    """Get blob storage connection string for the given account."""
    conn_str = BLOB_CONNECTION_STRINGS.get(account_name)
    if not conn_str:
        raise ValueError(f"Unknown storage account: {account_name}")
    return conn_str


def get_openai_headers() -> dict:
    """Get headers for Azure OpenAI API calls."""
    return {
        "Content-Type": "application/json",
        "api-key": OPENAI_API_KEY,
    }
