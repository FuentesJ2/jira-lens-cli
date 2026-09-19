---
name: jira-context-cli
description: 'Use when you need Jira or TestRay context from avjira through the portable jira-context CLI bundle. Fetch test cases, requirements, problem reports, issue links, comment history, authored steps, ad hoc runs, raw API payloads, field discovery, Synapse probes, or page-inspection clues.'
argument-hint: 'Provide issue kind and issue key, for example: test-case MFD-7754, requirement DMFDREQ-1448, or problem-report MFD-8100.'
---

# Jira Context CLI

This tracked skill is the deployment source for the workspace copy under the target workspace `.github/skills/jira-context-cli/SKILL.md` path.
Keep the deployed copy synchronized with this source file.

## When to Use
- The user wants the agent to see the same Jira/TestRay data they can inspect themselves.
- The user asks for Jira issue links, linked problem reports, comment history, authored test steps, ad hoc run history, linked requirements, test plans, suites, defects, or raw payloads.
- The user needs a local JSON artifact written to disk before the result is summarized.

## Runtime
- Prefer the deployed executable at `<workspace-root>/.github/tools/jira-context/jira-context.exe`.
- The portable runtime bundle lives under the target workspace `.github/tools/jira-context/` folder so the source repository can live elsewhere.
- The deployed bundle is executable-first: call `jira-context.exe` directly rather than constructing Python commands yourself.
- If the current session cannot execute commands, stop immediately and report that the CLI cannot be run from this session.
- When execution is unavailable, do not search for MCP configs, VS Code tasks, command bridges, or workspace wrappers as a fallback.
- Write machine-readable output with `Out-File -Encoding utf8` instead of `>` when saving JSON.
- For `fetch`, the canonical agent-facing payload is the saved normalized JSON file on disk, not terminal stdout.
- Do not create runtime JSON files inside `.github/skills/`. Keep persisted normalized and raw JSON outputs under the target workspace `.github/tools/jira-context/jira-output/` folder or an explicit user-provided save path.
- When requesting permission to run a Jira CLI command, ask for approval on the exact `jira-context.exe ...` command only. Do not generate PowerShell wrapper functions, pre/post directory scans, file-diff scaffolding, or other validation scripts unless the user explicitly asked for that deeper validation.
- Never wrap a Jira fetch in a one-off PowerShell program that captures stdout, tracks `$LASTEXITCODE`, probes file existence, or prints sentinel blocks such as `RESULT_START`, `FIRST_OUTPUT_START`, or `SECOND_OUTPUT_START`.
- If `--save-normalized-to` was used or should be used, do not inspect terminal transcript files such as Copilot chat `content.txt` resources. Open the saved normalized JSON file directly.
- For normalized JSON analysis, read the saved JSON file directly using workspace file-reading tools (for example `read_file`). Do not run terminal parsing commands (PowerShell/Python/jq) to interpret normalized JSON unless the user explicitly requests command-based parsing output.
- If the JSON is large, continue reading it in chunks with direct file reads instead of writing extraction wrappers.

## Direct Command Shape
Ask to run or approve one direct CLI command in this shape and nothing around it:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-9212 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/MFD-9212-normalized.json
```

Concrete Windows example:

```powershell
C:/Dev/.github/tools/jira-context/jira-context.exe fetch test-case MFD-9212 --save-normalized-to C:/Dev/.github/tools/jira-context/jira-output/MFD-9212-normalized.json
```

- Do not prepend `$exe=...`, argument arrays, `Out-String`, `Test-Path`, `$LASTEXITCODE`, or sentinel markers.
- Do not bundle `test-case` and `problem-report` fallback attempts into one generated PowerShell script.
- If the issue kind is uncertain, ask the user or run one direct fetch at a time.
- Always include `--save-normalized-to` for agent-driven Jira fetches.

## Working With Tessie
- When this skill and the Tessie or MFD Test Script Agent workflow are both relevant, this skill owns live Jira and TestRay retrieval and Tessie owns downstream test-case or script generation.
- If the user names a Jira issue key or asks for current requirement text, status, links, comments, authored steps, ad hoc runs, or related issues, run `jira-context.exe` first instead of answering from repository CSVs.
- Treat repository CSV exports and supporting docs as secondary references for style, compatibility, offline work, or cross-checking after the live fetch. They do not replace the CLI for the named Jira issue.
- If live Jira data and repository CSVs disagree, report both and prefer the live CLI fetch for current issue metadata.
- After a live fetch, Tessie may use the normalized JSON results to generate or revise test cases and scripts.
- Only skip the CLI-first fetch when the user explicitly asks for a CSV-only or offline workflow, or when Jira access is unavailable.

## Core Flow
1. Determine the issue kind: use `test-case` for MFD test cases, `requirement` for requirement issues such as `DMFDREQ-1448`, and `problem-report` for linked bug or problem-report issues.
2. Always run fetches with `--save-normalized-to` so the CLI writes the normalized JSON intentionally to `jira-output/` or a user-provided path.
3. After the fetch completes, open the saved normalized JSON file directly before any repo, code, or test search.
4. Do not treat terminal stdout, PowerShell transcript output, or Copilot chat-session resource files as the primary payload when the saved normalized JSON file exists.
5. When summarizing from normalized JSON, name the exact stable keys you used instead of generic text-search.
6. If the first fetch is a `test-case`, inspect the currently linked requirements from that saved normalized JSON before finishing the initial analysis unless the user asked to stay on the test case only.
7. If the user wants raw source payload JSON too, add `--include-raw-payload` or `--save-raw-payload-to`, but keep raw payloads on disk unless they are needed.
8. When the user asks for a specific slice, prefer `--section` over a full dump.
9. If the CLI fails or the Jira/TestRay shape is unclear, use the troubleshooting commands in [debugging reference](./references/debugging.md) before concluding the data is unavailable.
10. Unless the user explicitly asks for code impact, test impact, implementation comparison, or framework behavior, stop after the Jira/TestRay summary and `Next Query Layers`.

## Requirement Context Contract
- For `fetch requirement ...`, treat the Details and Main context fields as required context whenever Jira returns them.
- After each requirement fetch, read the saved normalized JSON first and explicitly inspect these keys: `summary`, `description`, `status`, `issue_type`, `project_key`, `assignee`, `updated`, `links`, `comments`, `priority`, `resolution`, `labels`, `components`, `custom_fields.customfield_19801` (Data ID), `custom_fields.customfield_10170` (Vehicle), `custom_fields.customfield_10703` (Verification Method), `custom_fields.customfield_10708` (Rationale), `custom_fields.customfield_16505` (Requirement Level), and `custom_fields.customfield_18002` (Verification Environment).
- Unless the user asked for a narrow section-only response, include the requirement `description` in the requirement summary (full text or a faithful excerpt).
- If one or more required requirement-context fields are missing, run `discover-fields <issue-key> --include-raw`, map the display names from `raw_response.names`, then refetch with explicit `--field` additions for requirement details: `components`, `labels`, `priority`, `resolution`, `issuetype`, `customfield_10170`, `customfield_10703`, `customfield_10708`, `customfield_16505`, `customfield_18002`, and `customfield_19801`.
- Do not assume one requirement proves schema stability across all projects; use discovery when field names or IDs appear to drift.

## Test-Case Context Contract
- For `fetch test-case ...`, treat test intent, requirement linkage, and execution evidence as required context when available.
- After each test-case fetch, read the saved normalized JSON first and explicitly inspect these keys: `summary`, `description`, `status`, `issue_type`, `project_key`, `assignee`, `updated`, `links`, `comments`, and `test_management` (`test_steps`, `linked_requirements`, `linked_test_suites`, `linked_test_plans`, `automation_reference`, `defects`, `ad_hoc_test_runs`).
- When linked requirements are present, inspect each linked requirement for `custom_fields.customfield_19801` (Data ID) and prepare a comparable list for output.
- If required test-case context is missing, refetch with explicit `--field` additions and/or a focused `--section` query before summarizing.

## Focused Fetches
- `links`
- `comments`
- `authored-steps`
- `ad-hoc-runs`
- `test-management`

Use the exact command patterns in [commands reference](./references/commands.md).

## Answer Shape
- Prefer normalized output for summaries.
- Default to markdown tables whenever two or more comparable fields can be lined up cleanly.
- Prefer tables over bullets for snapshots, requirement lists, linked issues, run history, step counts, statuses, owners, and other structured Jira/TestRay data.
- In `Test Intent`, `Authored Steps` must show the existing Jira test-case STEPS from `test_management.test_steps`, not only a count.
- When `test_management.test_steps` has entries, include an `Authored Steps` table with one row per step using `step_number`, `step_text`, and `expected_result_text`.
- For a test-case rundown, prefer this order: Snapshot, Current Requirements, Test Intent, Authored Steps, Execution Signals, Related Issues, Comments Worth Reading, Next Query Layers.
- Keep headings short and deliberate.
- After an important table, add a short interpretation paragraph when there is a meaningful signal or mismatch to call out.
- If the user asked for a pure section such as `comments` or `ad-hoc-runs`, summarize only that section unless they ask for more.
- If the CLI reports missing config or auth, tell the user exactly which saved Jira setting is missing.
- Do not claim that `comments` includes Jira field-change history or every workflow action; changelog data is not normalized yet.
- Keep each section tight. If a section has nothing useful, say `None found`.

Preferred compact shape:

```markdown
**Snapshot**
| Key | Type | Status | Assignee | Summary |
| --- | --- | --- | --- | --- |
| MFD-7754 | Test Case | Draft | Julio Fuentes Jr (Contractor) | DELTA - DIAG XPDR Reported Parameter Callsign Test Case |

**Current Requirements**
| Requirement | Status | What It Says Now | Why It Matters |
| --- | --- | --- | --- |
| DMFDREQ-1448 | Requirement Validated | Callsign may display up to 8 ASCII chars with out-of-range handling defined | The linked test case may be stale against the current requirement wording |

The biggest signal is whether the current requirement and current test-case expectations still match.

**Test Intent**
| Objective | Authored Steps Count |
| --- | --- |
| Show that the DIAG XPDR page correctly displays the Callsign after setting Flight ID bytes. | 8 |

**Authored Steps**
| Step # | Step Text | Expected Result |
| --- | --- | --- |
| 1 | Set XPDR flight ID bytes for a valid callsign input. | Callsign displays the expected 8-character ASCII value on the DIAG XPDR page. |
| 2 | Set an out-of-range byte pattern for the callsign field. | Display handling matches the requirement-defined out-of-range behavior. |

**Execution Signals**
| Latest Run | Status | Notable Result | Evidence |
| --- | --- | --- | --- |
| None found | None found | None found | None found |

**Related Issues**
| Issue | Relationship | Status | Summary |
| --- | --- | --- | --- |
| None found | None found | None found | None found |

**Comments Worth Reading**
- 2024-02-15 | Example Author: short reason this comment matters.

**Next Query Layers**
| Next Node | Why Query It |
| --- | --- |
| DMFDREQ-1448 | Check related issues or lineage if the current expectation looks stale. |
```

## References
- Use [commands reference](./references/commands.md) for normal day-to-day fetch commands and advanced fetch flag explanations.
- Use [debugging reference](./references/debugging.md) only for troubleshooting, environment setup recovery, or schema discovery.