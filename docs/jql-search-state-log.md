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
| State | Phase 1 complete |
| Current Phase | Phase 2: Person Search Wrapper |
| Next Action | Add `search person <name>` and explicit mode mapping |
| Last Updated | 2026-09-11 |

## Phase Tracker

| Phase | Name | Status | Notes |
| --- | --- | --- | --- |
| 1 | Raw JQL Search MVP | Completed | Raw JQL search saves normalized issue-list JSON with no normalized stdout |
| 2 | Person Search Wrapper | Planned | Adds `search person <name>` |
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

## Open Questions

| Question | Status | Notes |
| --- | --- | --- |
| Should `search` require `--save-normalized-to` in all modes? | Proposed | Current recommendation is yes for agent-driven search. |
| Should Phase 2 match on display name only, or also username/email forms? | Open | Depends on how the target Jira instance resolves JQL user references. |
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