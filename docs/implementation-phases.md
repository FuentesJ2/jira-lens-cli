# Jira Context Harness Implementation Phases

## Purpose

Build a local sidecar harness that gives the agent deterministic access to Jira Cloud issue context for the MFD workflow without polluting the `mfd` or `mfd-test-framework` repositories.

The delivery model for each phase is vertical:

1. Jira Cloud REST API v3 access
2. Python client normalization
3. CLI command
4. MCP tool exposure
5. Agent-facing usage pattern
6. End-to-end verification

## Confirmed platform assumptions

1. Target API: Jira Cloud REST API v3 or internal Jira Server/Data Center issue APIs, depending on the actual host
2. Team-default phase-1 environment: `https://avjira` with Jira Server/Data Center-style REST behavior
3. Team-default auth path for phase 1: basic auth with Jira username plus password
4. Initial scope: single issue retrieval only
5. Deferred scope: graph traversal, linked-issue crawling, attachments, project-wide discovery workflows

## Design constraints

1. The harness must remain outside the `mfd` and `mfd-test-framework` repositories.
2. Credentials must not be committed or stored in tracked files.
3. The CLI and MCP server must share the same client and normalization layer.
4. The MCP layer must expose narrow, typed tools rather than broad free-form query execution in phase 1.
5. Output must preserve raw Jira data where needed while also providing a stable normalized view for the agent.

## STATELOG

This section captures build-time and workflow gotchas so the harness design stays grounded in actual usage friction.

### Current gotchas

1. The `jira-context` shell command does not exist until the package is installed into the active Python environment.
2. Running `python cli.py ...` from inside `src/jira_context_harness` fails because direct script execution bypasses the package import path.
3. A no-install local launcher is useful in early phases because it removes packaging and shell `PATH` setup as blockers.
4. CLI trust matters for this project, so raw API response output must remain a first-class path, not a debug-only option.
5. When implementation details are uncertain, revisit the Jira Cloud REST API v3 docs before widening the contract.
6. The active local Python version may be older than the version assumed during initial scaffolding, so compatibility claims and packaging metadata must be verified against the actual interpreter before adding newer stdlib features.
7. First-run onboarding must not contaminate redirected JSON output, so prompts and setup messaging should go to stderr while data stays on stdout.
8. The real Jira environment may not be Jira Cloud. If issue URLs resolve under an internal host such as `https://avjira`, the harness may need Jira Server or Data Center REST conventions instead of Cloud v3.
9. Internal Jira onboarding must distinguish clearly between password-based basic auth and token-based auth. A generic `API token` prompt is not precise enough for users switching between Cloud and internal Jira.
10. Team-default onboarding should assume `avjira` + `server_dc` + `basic` so most users do not need to make deployment or auth decisions manually.
12. When the standard Jira issue JSON and the guessed Synapse REST paths are both insufficient, the Jira browse-page HTML is the next local source of truth because it already renders the test-step grid and may reveal plugin-backed endpoints or embedded step data.
11. PowerShell `>` redirection can create UTF-16 files, which is readable but awkward for downstream machine processing unless the CLI later provides explicit UTF-8 file output.

### Resolved in Phase 1

1. Added a root-level launcher so the CLI can be exercised locally before editable installation.
2. Removed `dataclass(slots=True)` usage after the local interpreter rejected it during launcher execution.
3. Added first-run interactive config capture that writes a local `.env` file and retries the original fetch command.
4. Split password and token handling in onboarding so internal Jira basic auth can use a real password while Cloud and bearer flows keep using tokens.
5. Added a field-discovery slice so the harness can inspect all Jira field metadata on a real issue instead of guessing where Synapse-style test steps, requirement panels, attachments, or test plans are stored.
7. Added an issue-page inspection slice so the harness can inspect rendered Jira HTML for step-grid markup and embedded Synapse endpoint clues.
6. Added a Synapse probe slice so the harness can test plugin-backed TestRay endpoints when the structured step grid is not present in the standard Jira issue response.

### Active Phase 1 risk

1. The raw issue fetch proves baseline access, but the current default whitelist does not yet expose all of the UI sections the user relies on, such as step tables, requirement panels, attachments, test plans, and Synapse-specific metadata.
2. Before widening into requirement crawling or attachment parsing, discover and confirm the exact Jira fields that back those UI sections on real MFD test case issues.

### Add future gotchas here

1. Authentication surprises
2. Field-shape variability across Jira issue types
3. ADF parsing edge cases
4. MCP transport or startup constraints
5. Agent workflow mismatches discovered during validation

## Proposed plan shape

Each phase below is intentionally small and end-to-end. After each phase, you can verify the behavior before we widen scope.

---

## Phase 0: Contract and environment setup

### Goal

Lock the external contract and local development shape before any real API wiring.

### Vertical delivery

1. Define the project layout and package boundaries.
2. Define environment variables for Jira base URL, user email, API token, and default project scope.
3. Define normalized issue response models for agent consumption.
4. Define initial CLI command names.
5. Define initial MCP tool names.

### Planned deliverables

1. Project scaffold
2. Configuration loader
3. Data models for normalized issue context
4. Planning docs

### Status

Partially complete.

### Current evidence

1. The sidecar project exists in [jira-context-harness](jira-context-harness).
2. The CLI and MCP entrypoints are stubbed.
3. The normalized model and config files exist.
4. A root launcher exists so the CLI can be run locally before installation.

### Exit criteria

1. You confirm the project name, layout, and phase structure.
2. You confirm the initial field goals for test case and requirement issues.

### Open questions

1. Should the sidecar project remain named `jira-context-harness`, or would you prefer a more role-specific name?
2. Do you want the first agent-facing tool names to include `mfd` in their identifiers?

---

## Phase 1: Fetch a single test case issue by key

### Goal

Retrieve one Jira test case issue by key and expose it consistently through the client, CLI, MCP, and agent workflow.

### Vertical delivery

1. Jira API
   Use `GET /rest/api/3/issue/{issueIdOrKey}`.
2. Client layer
   Implement authenticated fetch with explicit field selection and deterministic error handling.
3. CLI
   Add a command to fetch one test case issue by key and print normalized JSON.
4. MCP
   Add one tool that accepts an issue key and returns normalized issue context.
5. Agent usage
   Document when the agent should call this tool to gather context before test-case review or test-step drafting.
6. Verification
   Validate one real MFD test case issue end to end: CLI output, MCP output, and agent-readable summary.

### Proposed external surface

1. CLI
   `jira-context fetch test-case <ISSUE_KEY>`
2. MCP tool
   `get_test_case(issue_key)`

### Phase-1 API defaults

1. Endpoint: start with the host-appropriate issue endpoint, typically `GET /rest/api/3/issue/{issueIdOrKey}` for Cloud and `GET /rest/api/2/issue/{issueIdOrKey}` for internal Jira Server/Data Center hosts
2. Auth: basic auth with email and API token
3. Default field strategy: explicit field whitelist
4. Default expand strategy: none unless required by the issue type
5. Default output: normalized JSON with an option to emit the raw API payload directly for trust and inspection

### Fields to confirm before implementation

1. Summary
2. Description
3. Status
4. Issue type
5. Project
6. Assignee or owner if relevant
7. Updated timestamp
8. Any custom fields you rely on for test-case authoring or review

### Likely risks

1. Description may arrive as ADF rather than plain text.
2. Relevant test-case fields may be custom to your Jira project.
3. Permissions or issue security may hide fields or issues unexpectedly.

### Exit criteria

1. A real test case key can be fetched successfully with local credentials.
2. The CLI prints stable normalized JSON.
3. The CLI can also emit the raw API response so you can pipe it directly into a JSON or text file for inspection.
4. The MCP tool returns the same normalized contract.
5. The result is useful to the agent without any manual copy-paste cleanup.

### Deferred from this phase

1. Link crawling
2. Attachments
3. Search by JQL
4. Requirement issue fetch

---

## Phase 2: Fetch a single requirement issue by key

### Goal

Extend the same slice to requirement issues without broadening into graph traversal.

### Vertical delivery

1. Reuse the same Jira API endpoint.
2. Extend normalization for requirement-specific fields.
3. Add CLI support for `requirement` issue kind.
4. Add MCP tool support for requirement retrieval.
5. Verify the agent can consume requirement context for test-step validation and script generation.

### Proposed external surface

1. CLI
   `jira-context fetch requirement <ISSUE_KEY>`
2. MCP tool
   `get_requirement(issue_key)`

### Fields to confirm before implementation

1. Requirement summary
2. Requirement body text
3. Requirement status
4. Any requirement identifier field beyond the issue key
5. Any verification metadata that matters to your review process

### Exit criteria

1. A real requirement key can be fetched successfully.
2. Requirement output is normalized distinctly from test case output where needed.
3. The agent can use the result directly as requirements context.

### Deferred from this phase

1. Reverse lookup from test case to requirement links
2. Bulk requirement lookup
3. Search and graph expansion

---

## Phase 3: Project-scoped search for MFD issues

### Goal

Add controlled search across the MFD Jira scope so the agent can find candidate issues rather than requiring an exact key every time.

### Vertical delivery

1. Jira API
   Use enhanced JQL search with `GET` or `POST /rest/api/3/search/jql`.
2. Client layer
   Add search requests with explicit JQL, paging, and field whitelists.
3. CLI
   Add a search command for project-scoped lookups.
4. MCP
   Add one or more narrow search tools with safe parameterization.
5. Agent usage
   Document when the agent should search versus requiring the user to provide an exact key.
6. Verification
   Validate that search results are scoped, paginated, and predictable.

### Proposed external surface

1. CLI
   `jira-context search --jql "project = MFD AND issuetype = Test"`
2. MCP tool
   `search_mfd_issues(jql, max_results)`

### Design notes

1. Prefer `POST /rest/api/3/search/jql` for structured requests.
2. Handle pagination with `nextPageToken` and `isLast`.
3. Keep field selection explicit to avoid oversized payloads.

### Exit criteria

1. Search works against the intended project scope.
2. The MCP contract exposes only the parameters the agent actually needs.
3. Result size and paging behavior are deterministic enough for agent use.

### Deferred from this phase

1. Linked-issue expansion
2. Attachment retrieval
3. Cross-project graph analysis

---

## Phase 4: Link-aware context expansion

### Goal

Allow the harness to optionally expose selected linked issue metadata without full graph crawling.

### Vertical delivery

1. Use issue link data already present on issue responses where possible.
2. Add normalization for linked issue summaries and relationship types.
3. Add opt-in expansion flags at the CLI and MCP layers.
4. Verify that the agent can understand nearby linked context without getting flooded.

### Exit criteria

1. Linked issue summaries can be included intentionally.
2. Default behavior remains narrow and cheap.
3. The response contract stays stable.

---

## Phase 5: Role-specific agent workflow integration

### Goal

Wire the harness into your actual MFD workflow so the agent retrieves context at the right moments.

### Workflow targets

1. Pull a test case before validating or writing Jira test steps.
2. Pull a requirement before checking whether the test case covers it.
3. Pull both before drafting or reviewing a test script.

### Possible workspace-layer integration

1. A workspace prompt for “fetch Jira context for this test case”.
2. A skill that tells the agent which MCP tool to call and how to use the result.
3. Updates to the existing MFD agent guidance so context gathering happens consistently.

### Exit criteria

1. The agent uses the harness intentionally rather than requiring manual context copying.
2. The workflow remains narrow and predictable.
3. The external tooling remains separate from the product repos.

---

## Not in scope yet

1. Full graph database behavior
2. Broad recursive crawling of all linked Jira artifacts
3. Attachment download and parsing
4. Comment ingestion
5. Write-back operations to Jira
6. OAuth 2.0 or multi-user distribution hardening

## Recommended immediate next step

Proceed with Phase 1 only after you provide:

1. A sample test case issue key
2. The Jira base URL shape you use
3. The custom fields that matter for a test case in your workflow
4. Any auth constraints beyond standard email plus API token