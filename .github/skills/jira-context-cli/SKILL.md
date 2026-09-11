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
- For `fetch`, the agent-facing payload should stay normalized and small.
- Do not create runtime JSON files inside `.github/skills/`. Keep persisted normalized and raw JSON outputs under the target workspace `.github/tools/jira-context/jira-output/` folder or an explicit user-provided save path.
- When requesting permission to run a Jira CLI command, ask for approval on the exact `jira-context.exe ...` command only. Do not generate PowerShell wrapper functions, pre/post directory scans, file-diff scaffolding, or other validation scripts unless the user explicitly asked for that deeper validation.
- Never wrap a Jira fetch in a one-off PowerShell program that captures stdout, tracks `$LASTEXITCODE`, probes file existence, or prints sentinel blocks such as `RESULT_START`, `FIRST_OUTPUT_START`, or `SECOND_OUTPUT_START`.

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

## Working With Tessie
- When this skill and the Tessie or MFD Test Script Agent workflow are both relevant, this skill owns live Jira and TestRay retrieval and Tessie owns downstream test-case or script generation.
- If the user names a Jira issue key or asks for current requirement text, status, links, comments, authored steps, ad hoc runs, or related issues, run `jira-context.exe` first instead of answering from repository CSVs.
- Treat repository CSV exports and supporting docs as secondary references for style, compatibility, offline work, or cross-checking after the live fetch. They do not replace the CLI for the named Jira issue.
- If live Jira data and repository CSVs disagree, report both and prefer the live CLI fetch for current issue metadata.
- After a live fetch, Tessie may use the normalized JSON results to generate or revise test cases and scripts.
- Only skip the CLI-first fetch when the user explicitly asks for a CSV-only or offline workflow, or when Jira access is unavailable.

## Core Flow
1. Determine the issue kind: use `test-case` for MFD test cases, `requirement` for requirement issues such as `DMFDREQ-1448`, and `problem-report` for linked bug or problem-report issues.
2. For a small or focused fetch, run the direct CLI command normally and treat stdout as the normalized payload.
3. If the payload may be large, use `--save-normalized-to` immediately so the CLI writes the normalized JSON intentionally to `jira-output/`.
4. If `--save-normalized-to` was used, read that saved normalized JSON file before any repo, code, or test search.
5. When summarizing from normalized JSON, name the exact stable keys you used instead of generic text-search.
6. If the first fetch is a `test-case`, inspect the currently linked requirements before finishing the initial analysis unless the user asked to stay on the test case only.
7. If the user wants raw source payload JSON too, add `--include-raw-payload` or `--save-raw-payload-to`, but keep raw payloads on disk unless they are needed.
8. When the user asks for a specific slice, prefer `--section` over a full dump.
9. If the CLI fails or the Jira/TestRay shape is unclear, use the troubleshooting commands in [debugging reference](./references/debugging.md) before concluding the data is unavailable.
10. Unless the user explicitly asks for code impact, test impact, implementation comparison, or framework behavior, stop after the Jira/TestRay summary and `Next Query Layers`.

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
- For a test-case rundown, prefer this order: Snapshot, Current Requirements, Test Intent, Execution Signals, Related Issues, Comments Worth Reading, Next Query Layers.
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
| Objective | Authored Steps |
| --- | --- |
| Show that the DIAG XPDR page correctly displays the Callsign after setting Flight ID bytes. | 8 |

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