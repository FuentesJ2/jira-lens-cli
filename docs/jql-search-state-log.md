# JQL Search State Log

## Purpose

Use this file as the single progress record for the Jira search CLI feature.

- Update it at the end of each completed slice.
- Keep statuses short and factual.
- Record decisions that affect later phases.

## Current Status

| Field | Value |
| --- | --- |
| Feature | Jira JQL search CLI |
| Owner | GitHub Copilot + user |
| State | Phase 4 deferred |
| Current Phase | Deferred |
| Next Action | Resume Phase 4 later if broader involvement search modes become a priority |
| Last Updated | 2026-09-11 |

## Phase Tracker

| Phase | Name | Status | Notes |
| --- | --- | --- | --- |
| 1 | Raw JQL Search MVP | Completed | Raw JQL search saves normalized issue-list JSON with no normalized stdout |
| 2 | Person Search Wrapper | Completed | Adds `search person <name>` with explicit current, history, and current-or-history modes |
| 3 | Search Result Shaping | Completed | Adds order metadata, paging metadata, and stable preservation of requested extra fields |
| 4 | Involvement History Expansion | Deferred | Deferred until a later date pending priority and Jira capability validation |
| 5 | Skill and Workflow Integration | Completed | Skill now routes people prompts through saved search JSON before targeted fetch |

## Decisions

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-11 | Search will be implemented in vertical slices. | Keeps each release usable and testable. |
| 2026-09-11 | Agent-driven search will be file-first with `--save-normalized-to`. | Prevents transcript scraping and keeps artifacts explicit. |
| 2026-09-11 | Phase 1 will support raw JQL before friendly person wrappers. | Solves the core capability first and keeps implementation honest. |
| 2026-09-11 | Phase 1 search uses the Jira search endpoint through the existing candidate API-path logic. | Keeps auth and deployment handling consistent with `fetch`. |
| 2026-09-11 | Person search will be a thin CLI wrapper that generates explicit JQL and reuses the raw JQL search engine. | Keeps behavior inspectable and avoids splitting search execution paths. |
| 2026-09-11 | Copilot should route person prompts through `search` first and only fetch after reading the saved search JSON. | Prevents guessed issue keys and preserves the file-first workflow. |
| 2026-09-11 | Search result shaping will preserve the compact stable fields and place any requested nonstandard Jira fields under `extra_fields`. | Lets advanced searches add context without breaking the normalized schema. |
| 2026-09-11 | Phase 4 is deferred until a later date. | Current priority is stable search, fetch, and skill workflow behavior rather than broader involvement modes. |

## Slice Log

### 2026-09-11 - Planning established

- Added phased implementation plan.
- Added this persistent state log.
- Confirmed the first coding target is Phase 1 raw JQL search.

### 2026-09-11 - Phase 1 completed

- Added `search --jql ... --save-normalized-to ...` to the CLI.
- Added `SearchRequest`, `JiraSearchIssue`, and `JiraSearchResult` models.
- Added Jira search client support using `POST` to the Jira search endpoint.
- Search writes normalized JSON to disk and emits no normalized stdout on the saved path.
- Validated parser wiring, normalized client behavior, and save-only CLI behavior against the repo source tree.

### 2026-09-11 - Phase 2 completed

- Added `search person <display-name>` to the CLI.
- Added explicit `current`, `history`, and `current-or-history` modes.
- Generated explicit JQL from the person search wrapper and preserved the generated query in normalized output metadata.
- Validated parser wiring, JQL generation, and save-only CLI behavior against the repo source tree.

### 2026-09-11 - Phase 5 completed

- Updated the skill guidance to route person prompts through `search person ... --save-normalized-to ...` before any `fetch`.
- Added direct person-search and raw JQL search examples plus a search-to-fetch workflow example.
- Kept the file-first rule explicit for both search and fetch and banned transcript scraping as a substitute for the saved JSON artifacts.

### 2026-09-11 - Phase 3 completed

- Added `--order-by updated|created|priority` for friendly person search.
- Search output now preserves `order_by`, `requested_fields`, `has_more`, and `next_start_at` metadata.
- Requested nonstandard Jira fields are preserved under each issue's `extra_fields` map without breaking the compact normalized schema.

### 2026-09-11 - Phase 4 deferred

- Deferred broader involvement-history search work until a later date.
- Keep `worklogAuthor` and other expanded modes as future validation items rather than current implementation targets.

## Open Questions

| Question | Status | Notes |
| --- | --- | --- |
| Should `search` require `--save-normalized-to` in all modes? | Proposed | Current recommendation is yes for agent-driven search. |
| Should person search match on display name only, or also username/email forms? | Open | Current implementation uses the provided display name verbatim in generated JQL. |
| Is `worklogAuthor` supported on the target Jira deployment? | Open | Validate during Phase 4 discovery. |

## Validation Commands

Use these as the default narrow validation surface while the feature is being built.

```powershell
python -m unittest tests.test_cli -v
```

```powershell
python -m unittest tests.test_jira_client -v
```

If the local environment imports an installed package instead of the repo source tree, set:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
```

## Update Template

When a slice completes, append a short entry like this:

```markdown
### YYYY-MM-DD - Phase X completed

- What shipped.
- What was validated.
- Any follow-up risk or next action.
```