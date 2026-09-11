# JQL Search CLI Implementation Plan

## Goal

Add a Jira search capability to the CLI so a user can search for a person such as `Dustin Marek`, review recent or historical issues, and then pivot into the existing single-issue `fetch` workflow.

Primary user story:

```text
Find the most recent issues Dustin Marek is working on or has worked on, inspect the returned issue list, then fetch one of those issues for deeper analysis.
```

## Principles

- Deliver in vertical slices that are individually usable.
- Reuse the existing Jira client auth and API-path selection logic.
- Keep agent-driven search file-first: save normalized JSON, then read the saved file.
- Keep the first version small and reliable before adding convenience layers.
- Separate current assignment, assignment history, and worklog-based involvement instead of guessing.

## Target CLI Shape

Raw JQL power-user flow:

```powershell
jira-context.exe search --jql "assignee = \"Dustin Marek\" ORDER BY updated DESC" --save-normalized-to C:/Dev/.github/tools/jira-context/jira-output/dustin-marek-search.json
```

Friendly person-search flow after later slices:

```powershell
jira-context.exe search person "Dustin Marek" --mode current --save-normalized-to C:/Dev/.github/tools/jira-context/jira-output/dustin-marek-current.json
```

```powershell
jira-context.exe search person "Dustin Marek" --mode history --save-normalized-to C:/Dev/.github/tools/jira-context/jira-output/dustin-marek-history.json
```

## Proposed Output Shape

```json
{
  "query": "assignee = \"Dustin Marek\" ORDER BY updated DESC",
  "mode": "raw-jql",
  "total": 12,
  "returned": 10,
  "start_at": 0,
  "max_results": 10,
  "issues": [
    {
      "issue_key": "MFD-9212",
      "summary": "Example summary",
      "status": "In Progress",
      "issue_type": "Problem Report",
      "project_key": "MFD",
      "assignee": "Dustin Marek",
      "reporter": "Example Reporter",
      "updated": "2026-09-11T12:34:56.000+0000",
      "source_url": "https://avjira/browse/MFD-9212"
    }
  ]
}
```

## Phase 1: Raw JQL Search MVP

### Vertical slice

Ship a usable `search --jql ... --save-normalized-to ...` command that returns a normalized issue list from Jira search.

### Scope

- Add a `search` subcommand.
- Accept raw JQL via `--jql`.
- Require `--save-normalized-to` for `search`.
- Support `--limit` and `--start-at`.
- Normalize search results into a compact list.
- Emit no normalized stdout when saving the search output.

### Implementation areas

- `src/jira_context_harness/cli.py`
- `src/jira_context_harness/jira_client.py`
- `src/jira_context_harness/models.py`
- `tests/test_cli.py`
- `tests/test_jira_client.py`
- `README.md`
- `.github/skills/jira-context-cli/SKILL.md`
- `.github/skills/jira-context-cli/references/commands.md`

### API direction

- Add a client method that calls Jira search through the same candidate API path logic used by `fetch`.
- Prefer `POST` for JQL search payloads to avoid quoting and URL-length issues.
- Start with Jira fields needed for list views: `summary`, `status`, `issuetype`, `project`, `assignee`, `reporter`, `updated`.

### Tests

- Search parser accepts `--jql`, `--limit`, `--start-at`, and `--save-normalized-to`.
- Search command rejects missing `--save-normalized-to`.
- Search command writes normalized JSON and suppresses stdout.
- Client handles a successful Jira search response.
- Client surfaces Jira HTTP 400 or auth failures clearly.

### Exit criteria

- A user can run raw JQL search from the CLI and get a saved normalized result file.
- The result is compact enough for the agent to scan quickly.
- The saved file is the only analysis artifact used by the agent flow.

## Phase 2: Person Search Wrapper

### Vertical slice

Ship a friendly `search person <name>` command that builds JQL for common people-based searches without requiring the user to know JQL.

### Scope

- Add `search person <display-name>`.
- Add `--mode current|history|current-or-history`.
- Generate explicit JQL instead of hiding search semantics.
- Keep the saved normalized JSON format compatible with Phase 1.

### JQL mapping

- `current`: `assignee = "<name>" ORDER BY updated DESC`
- `history`: `assignee WAS "<name>" ORDER BY updated DESC`
- `current-or-history`: `assignee = "<name>" OR assignee WAS "<name>" ORDER BY updated DESC`

### Tests

- CLI builds the expected JQL for each mode.
- Output metadata states which mode and generated JQL were used.
- Empty search results are handled cleanly.

### Exit criteria

- A user can search for `Dustin Marek` by name without writing JQL.
- The generated query is visible in the output for trust and debugging.

## Phase 3: Search Result Shaping

### Vertical slice

Make the search results more actionable for follow-up work without expanding into full issue payloads.

### Scope

- Add optional field selection for advanced use.
- Add `--order-by updated|created|priority` where practical.
- Add a compact text summary mode for humans if still needed.
- Add clearer normalized metadata for paging and total counts.

### Tests

- Paging metadata is correct.
- Optional fields do not break the normalized schema.
- Search remains file-first when save output is requested.

### Exit criteria

- Users can narrow or shape results without leaving the CLI.
- Agents still consume a stable, compact normalized file.

## Phase 4: Involvement History Expansion

### Vertical slice

Broaden the meaning of “worked on” beyond assignment history while keeping search semantics explicit.

### Scope

- Evaluate `worklogAuthor = "<name>"` support for the target Jira instance.
- Consider `reporter =`, `comment ~`, or other explicit modes only if they are useful and supported.
- Add separate search modes only after confirming API support on the target Jira environment.

### Risks

- JQL support differs between Jira deployments and plugins.
- Some history concepts require changelog expansion and are more expensive than assignment history.

### Exit criteria

- “Worked on” modes are explicit and evidence-based rather than inferred.

## Phase 5: Skill and Workflow Integration

### Vertical slice

Teach the Copilot skill to use the new search flow before fetch when the user asks about a person’s recent or historical issues.

### Scope

- Update skill guidance for people-search prompts.
- Add command examples for raw JQL and person search.
- Preserve the rule that agent-driven search and fetch flows are file-first.

### Exit criteria

- The skill can route from a person search to a targeted fetch without transcript scraping or wrapper scripts.

## Recommended Order

1. Phase 1
2. Phase 2
3. Phase 5
4. Phase 3
5. Phase 4

Rationale:

- Phase 1 gives a real search engine immediately.
- Phase 2 makes it usable for the exact user story.
- Phase 5 makes the agent use it correctly as soon as the feature exists.
- Phase 3 and Phase 4 are quality and breadth expansions.

## First Implementation Slice

Start with Phase 1 only.

Definition of done for the first coding pass:

- `jira-context.exe search --jql ... --save-normalized-to ...` works.
- Saved normalized search JSON has compact issue list output.
- No normalized stdout is emitted for the saved search path.
- CLI and client tests cover the happy path and a basic failure path.