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
| State | Phase 2 complete |
| Current Phase | Phase 3: Search Result Shaping |
| Next Action | Evaluate optional ordering and field-shaping without breaking compact normalized output |
| Last Updated | 2026-09-11 |

## Phase Tracker

| Phase | Name | Status | Notes |
| --- | --- | --- | --- |
| 1 | Raw JQL Search MVP | Completed | Raw JQL search saves normalized issue-list JSON with no normalized stdout |
| 2 | Person Search Wrapper | Completed | Adds `search person <name>` with explicit current, history, and current-or-history modes |
| 3 | Search Result Shaping | Planned | Paging, ordering, and optional fields |
| 4 | Involvement History Expansion | Planned | Broader definitions of “worked on” |
| 5 | Skill and Workflow Integration | Planned | Teach Copilot to route search then fetch |

## Decisions

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-11 | Search will be implemented in vertical slices. | Keeps each release usable and testable. |
| 2026-09-11 | Agent-driven search will be file-first with `--save-normalized-to`. | Prevents transcript scraping and keeps artifacts explicit. |
| 2026-09-11 | Phase 1 will support raw JQL before friendly person wrappers. | Solves the core capability first and keeps implementation honest. |
| 2026-09-11 | Phase 1 search uses the Jira search endpoint through the existing candidate API-path logic. | Keeps auth and deployment handling consistent with `fetch`. |
| 2026-09-11 | Person search will be a thin CLI wrapper that generates explicit JQL and reuses the raw JQL search engine. | Keeps behavior inspectable and avoids splitting search execution paths. |

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