---
applyTo: "**"
---

# Pull Request — STRICT TEMPLATE

ACK_TEMPLATE_V1

> Respond **only** with the sections below, **verbatim and in this order**.  
> If something can't be verified from the PR (title/body/diff/commits), write **MISSING – <action>**.  
> **Do not add** extra headings, prose, or emojis. If you can't comply, output `FORMAT_VIOLATION`.

> Large PR rule: If `files changed > 40`, fully review the top N files by diff size and mark the rest as  
> **MISSING – manual per-file review required**. State N and the selection basis.

## Summary
Brief description of what this PR accomplishes and why it's needed. 1–3 sentences on what changed and why.

## Diff Coverage
- Files changed: <count>. Confirm you reviewed **ALL** of them. If any were skipped, say **why** (or apply the Large PR rule).

## Changes Made
- List key changes made in this PR
- Include any new dependencies or configuration changes
- Mention any infrastructure changes

### Per-file Review
For **each changed file** (or each of the top-N under the Large PR rule):
- **path:** `<repo-relative path>`
  - What changed (1–2 bullets).
  - Potential issues or nitpicks.
  - Concrete suggestions with quotes like `L<line>` or key names.

### Type of Change
Choose all that apply:
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Infrastructure change
- [ ] Refactor
- [ ] Security fix
If unclear, mark **MISSING – classify the change type**.

## Risks & Security
- Secrets or tokens added? Yes/No.
  - If Yes: **BLOCKS MERGE** — secrets must be moved to environment variables or Azure Key Vault.
- Hardcoded connection strings? Yes/No.
- Hardcoded API keys or endpoints? Yes/No.
- Input validation present for all user inputs? Yes/No.
- `.gitignore` properly configured for `local.settings.json`? Yes/No.

### Testing
- Are unit/integration tests added or updated? If not applicable, say `N/A`; otherwise **MISSING – add/point to tests**.
- Manual test steps described? If not: **MISSING – describe how to test**.

## Code Quality
- [ ] Code follows project standards (Python PEP 8, type hints)
- [ ] Self-review completed
- [ ] No secrets or sensitive data in code
- [ ] Error handling implemented
- [ ] DRY principle followed (no duplicate code across functions)
- [ ] Proper logging used (not print statements)

## Documentation
- [ ] Code is properly commented
- [ ] README updated (if applicable)
- [ ] Function purpose documented
If updates needed, list exact sections/files. If unknown, **MISSING – specify docs to update**.

## Checklist (use [ ] / [x])
- [ ] All changed files reviewed
- [ ] No secrets committed (API keys, connection strings, tokens)
- [ ] Dependencies pinned in requirements.txt
- [ ] Tests or rationale for no tests
- [ ] Docs/README updated if needed

## Merge Readiness
Choose one: **Block** / **Needs follow-up items** / **LGTM**. Brief rationale.
