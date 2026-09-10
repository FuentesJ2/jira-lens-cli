# jira-context-harness

Local sidecar project for agent-facing JIRA context retrieval.

This project is intentionally outside the `mfd` and `mfd-test-framework` repositories so the harness can evolve without polluting either repo.

## Python compatibility

The harness currently targets Python 3.10+.

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

The CLI can now fetch a single Jira issue against either Jira Cloud or an internal Jira Server/Data Center-style host by trying the appropriate issue endpoint variants. MCP tool registration is not implemented yet.

The currently known browser issue URL for this workflow is `https://avjira/browse/MFD-7754`. If that is the authoritative Jira host, the harness may need to target Jira Server or Data Center REST endpoints instead of Jira Cloud v3.

## Phase 1 CLI usage

Set environment variables:

```text
JIRA_BASE_URL=https://avjira
JIRA_USER_EMAIL=your_jira_username
JIRA_PASSWORD=
JIRA_API_TOKEN=your_api_token
JIRA_PROJECT_SCOPE=MFD
JIRA_DEPLOYMENT=server_dc
JIRA_AUTH_MODE=basic
```

### Local execution without installation

If you have not installed the package yet, run the launcher from the project root:

```text
python run_cli.py fetch test-case MFD-1234
```

This is the most reliable Phase 1 path for local validation because it does not depend on `pip install -e .` or shell `PATH` setup.

On first run, if required Jira settings are missing, the CLI will prompt for them interactively, save them to a local `.env` file in the project root, and then retry the same fetch command.

The secret prompt now depends on the selected deployment and auth mode:

1. Jira Cloud + basic auth: `Atlassian API token`
2. Internal Jira + basic auth: `Jira password`
3. Internal Jira + bearer auth: `Jira personal access token`

Normal team onboarding defaults to `https://avjira`, `server_dc`, `basic`, and `MFD`, so most users should only need to provide username and password.

If you need to update the saved configuration later, run:

```text
python run_cli.py configure
```

If someone needs to override the default internal Jira assumptions, use:

```text
python run_cli.py configure --advanced
```

To diagnose whether your saved credentials can authenticate to Jira at all, run:

```text
python run_cli.py probe-auth > jira-auth-probe.json
```

To discover which Jira fields actually store test steps, requirement panels, attachments, test plans, and related Synapse data for a specific issue, run:

```text
python run_cli.py discover-fields MFD-7754 > jira-field-discovery.json
```

If you also want the full all-fields Jira response in the same output file, run:

```text
python run_cli.py discover-fields MFD-7754 --include-raw > jira-field-discovery-full.json
```

If the standard Jira issue response still does not expose the structured step grid, probe the TestRay or Synapse plugin endpoints directly:

```text
python run_cli.py probe-synapse MFD-7754 > jira-synapse-probe.json
```

This command targets the plugin base path used in the team docs: `https://avjira/rest/synapse/latest/public/`.
It now probes the documented TestRay DC test-case resources first, including `/testCase/{issueKey}/steps`, `/linkedRequirements`, `/linkedTestSuites`, `/linkedTestPlans`, `/automationReference`, `/getDefects`, and `/testRun/adhoc/getTestRuns/{issueKey}`.

If those plugin probes still do not expose the step grid, inspect the actual Jira browse page HTML for embedded step markup or plugin endpoint clues:

```text
python run_cli.py inspect-page MFD-7754 --include-html > jira-issue-page-inspection.json
```

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

Another important gotcha is output redirection: onboarding prompts are written to stderr so commands like `python run_cli.py fetch test-case MFD-1234 --view raw > test-case-raw.json` can still create a clean JSON file on stdout.

For internal Jira hosts such as `https://avjira`, the harness may need Jira Server or Data Center REST paths. The current client now tries the common issue endpoint variants automatically, starting with `/rest/api/2` for non-Cloud hosts.

If auth fails, `probe-auth` captures useful headers such as `X-Seraph-LoginReason` and `WWW-Authenticate` so you can tell the difference between bad credentials, missing login, and Jira-side auth policy issues.

For internal Jira, do not paste an Atlassian Cloud API token into the `Jira password` prompt. They are different credentials.

When you save `server_dc` with `basic` auth, the harness clears any previously saved token because that token is not used for that mode.

PowerShell `>` redirection can create UTF-16 files. That is readable, but some downstream tooling may prefer UTF-8 output instead.

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

For internal Jira test cases, `fetch test-case` also enriches the normalized output with TestRay context from the documented Synapse endpoints, including `test_steps`, `linked_requirements`, `linked_test_suites`, `linked_test_plans`, `defects`, and `ad_hoc_test_runs`. When you use `--view both`, those raw supplemental payloads appear under `supplemental_responses`.

The normalized `test_steps` and ad hoc run `steps` use stable keys such as `step_number`, `step_text`, `step_raw`, `step_html`, `expected_result_text`, `expected_result_raw`, `expected_result_html`, `requirement_keys`, and `attachments`, so the agent can consume a predictable schema while you still retain the raw plugin response for trust.

If you want only the part you care about, use `--section` on `fetch`:

```text
python run_cli.py fetch test-case MFD-7754 --section authored-steps
python run_cli.py fetch test-case MFD-7754 --section ad-hoc-runs
python run_cli.py fetch test-case MFD-7754 --section merged-steps
```

The `merged-steps` section keeps the authored test-case step text as the primary source, then overlays the latest ad hoc run status, actual result, attachments, and richer rendered HTML when it is available from the execution record.

To start the MCP server for agent use:

```text
python run_cli.py serve-mcp
```

The initial MCP tool surface is:

```text
get_test_case(issue_key, section="full", include_raw=false)
get_requirement(issue_key, include_raw=false)
```

For `get_test_case`, the `section` values match the CLI fetch sections, including `authored-steps`, `ad-hoc-runs`, and `merged-steps`.

Render a quick human-readable summary:

```text
python run_cli.py fetch test-case MFD-1234 --format text
```