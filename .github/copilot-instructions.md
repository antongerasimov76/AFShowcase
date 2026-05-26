# Coding Agent Rules

## /pre-merge-review invocation

When a user triggers `/pre-merge-review` (via `@copilot /pre-merge-review` comment):

1. Invoke the `pre-merge-review` agent and let it complete fully.
2. The agent will post its own PR comment via `github/add-pr-comment`. That is the final deliverable.
3. **Do NOT reformat, summarize, or simplify** the agent's output. Do NOT post your own version.
4. **Do NOT edit any files** in the repository.
5. **Do NOT commit or push** anything.
6. **Do NOT create branches.**
7. **STOP immediately** after the agent finishes. Do not continue with "improvements" or "fixes."

The pre-merge-review agent is READ-ONLY. Its findings are observations for humans. They are NOT tasks for you to implement.

---

# Code Review Agent Instructions (EARTH Stage 1)

> For **copilot-pull-request-reviewer** - the automated shallow review bot.
> This agent does NOT follow output format instructions, so only specify WHAT to check.

## Review Focus Areas

### 1. Security (Critical Priority)
- **No Hardcoded Credentials**: API keys, connection strings, account keys, tokens must NEVER be in source code
  - Must use environment variables, Azure Key Vault, or `local.settings.json` (which is .gitignored)
  - Flag ANY string that looks like a key, connection string, or secret
- **Input Validation**: Validate all request bodies and parameters before use
- **API Key Protection**: Azure Functions auth level should be appropriate (Function/Admin, not Anonymous for sensitive endpoints)
- **Blob Storage Access**: Use Managed Identity or environment-based connection strings, never hardcoded

### 2. Architecture & Code Quality (Python Azure Functions)
- **Function Size**: Each function should be focused and under 50 lines where possible
- **Separation of Concerns**: Business logic should be in separate modules, not inline in function handlers
- **DRY Principle**: No duplicate code across functions (shared utilities should be in a common module)
- **Error Handling**: Proper try/except with meaningful error messages and appropriate HTTP status codes
- **Type Hints**: Use Python type hints for function parameters and return values
- **Logging**: Use `logging` module with appropriate levels (info, warning, error)
- **Constants**: No magic strings or numbers — use named constants or configuration

### 3. Azure Functions Best Practices
- **HTTP Triggers**: Validate request method and content type
- **Durable Functions**: Proper orchestrator patterns (fan-out/fan-in, chaining, monitoring)
- **Connection Reuse**: Reuse HTTP clients and blob service clients across invocations
- **Timeout Handling**: Handle long-running operations with Durable Functions, not synchronous waits
- **Configuration**: Use Application Settings / environment variables for all config values
- **Requirements**: All dependencies pinned to specific versions in `requirements.txt`

### 4. Azure OpenAI Integration
- **Prompt Injection Prevention**: Sanitize user inputs before including in prompts
- **Token Limits**: Handle response truncation gracefully
- **Error Handling**: Handle rate limiting (429), timeouts, and API errors
- **Model Selection**: Use appropriate model for the task (don't use expensive models for simple tasks)
- **API Versioning**: Use stable API versions, not preview unless needed

### 5. Azure Blob Storage
- **Connection Management**: Reuse `BlobServiceClient` instances
- **Error Handling**: Handle `ResourceNotFoundError`, `StorageErrorException`
- **Large Files**: Stream large files, don't load entirely into memory
- **Naming**: Use consistent blob naming conventions

### 6. Testing
- **Unit Tests**: Business logic should be testable in isolation
- **Integration Tests**: Test function endpoints with test data
- **Mocking**: Mock external services (Azure OpenAI, Blob Storage) in tests
- **Test Data**: Use fixtures, not hardcoded values

## Anti-Patterns to Flag

### Security (CRITICAL)
- Hardcoded API keys (e.g., `GPT4V_KEY = "..."`)
- Hardcoded connection strings (e.g., `DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...`)
- Hardcoded endpoints with keys in query strings
- Secrets committed to version control
- Missing `.gitignore` entries for `local.settings.json`

### Code Quality
- Copy-paste code across multiple functions (violates DRY)
- Functions over 100 lines (should be decomposed)
- Bare `except:` clauses (swallowing all exceptions)
- `print()` instead of `logging`
- Commented-out code blocks without explanation
- TODO comments without issue references
- Magic numbers and hardcoded URLs
- Unused imports

### Azure Functions
- Synchronous blocking calls in async functions
- Creating new `BlobServiceClient` on every request (should reuse)
- Missing `host.json` configuration for timeouts/retries
- Anonymous auth level on sensitive endpoints
- Missing CORS configuration where needed

### AI/LLM Integration
- Unsanitized user input in prompts (injection risk)
- No token limit checks before API calls
- Missing retry logic for transient failures
- Hardcoded model names (should be configurable)
