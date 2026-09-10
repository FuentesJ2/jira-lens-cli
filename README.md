# jira-context-harness

Local sidecar project for agent-facing JIRA context retrieval.

This project is intentionally outside the `mfd` and `mfd-test-framework` repositories so the harness can evolve without polluting either repo.

## Python compatibility

The harness is currently written to run on Python 3.8+ so it can work in older local environments without requiring a Python upgrade first.

## Initial goals

1. Provide a human-usable CLI for fetching JIRA issue context.
2. Wrap the same core logic in a local MCP server for agent use.
3. Start with single-issue fetches for test cases and requirements.
4. Defer graph expansion, link crawling, and attachment workflows until later slices.

## Planned structure

- `src/jira_context_harness/`: application code
- `tests/`: scaffolded tests
- `docs/`: architecture notes and planning artifacts

## Current status

Phase 1 is in progress.

The CLI can now fetch a single Jira issue over the Jira Cloud REST API v3 issue endpoint when credentials are supplied through environment variables. MCP tool registration is not implemented yet.

## Phase 1 CLI usage

Set environment variables:

```text
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USER_EMAIL=you@example.com
JIRA_API_TOKEN=your_api_token
```

### Local execution without installation

If you have not installed the package yet, run the launcher from the project root:

```text
python run_cli.py fetch test-case MFD-1234
```

This is the most reliable Phase 1 path for local validation because it does not depend on `pip install -e .` or shell `PATH` setup.

### Installed execution

If you want the `jira-context` command to exist directly in PowerShell, install the project in editable mode from the project root:

```text
python -m pip install -e .
```

Then this form will work:

```text
jira-context fetch test-case MFD-1234
```

### Important gotcha

Do not run `python cli.py ...` from inside `src/jira_context_harness`. That bypasses the package import path and will fail on `from jira_context_harness...` imports.

If your local Python is older than the version originally assumed during scaffolding, package metadata and language features must match that reality. The current scaffold avoids `dataclass(slots=True)` so the launcher path works in older local interpreters.

Fetch normalized JSON:

```text
python run_cli.py fetch test-case MFD-1234 > test-case-normalized.json
```

Fetch the raw API response for trust and inspection:

```text
python run_cli.py fetch test-case MFD-1234 --view raw > test-case-raw.json
```

Fetch both normalized output and the raw API payload:

```text
python run_cli.py fetch test-case MFD-1234 --view both > test-case-both.json
```

Render a quick human-readable summary:

```text
python run_cli.py fetch test-case MFD-1234 --format text
```