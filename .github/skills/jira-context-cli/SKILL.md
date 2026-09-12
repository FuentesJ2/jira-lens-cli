---
name: jira-context-cli
description: 'Use when you need Jira or TestRay context from avjira through the portable jira-context CLI bundle. Fetch test cases, requirements, problem reports, issue links, comment history, authored steps, ad hoc runs, raw API payloads, field discovery, Synapse probes, or page-inspection clues. It can also search Jira with JQL or by person when the user starts from a person rather than an issue key.'
argument-hint: 'Provide an issue kind and issue key first, for example: test-case MFD-7754, requirement DMFDREQ-1448, or problem-report MFD-8100. If needed later, you can also ask for a people-search request such as person Dustin Marek history.'
---

# Jira Context CLI

This tracked skill is the deployment source for the workspace copy under the target workspace `.github/skills/jira-context-cli/SKILL.md` path.
Keep the deployed copy synchronized with this source file.

## When to Use
- The user wants the agent to see the same Jira/TestRay data they can inspect themselves.
- The user asks for Jira issue links, linked problem reports, comment history, authored test steps, ad hoc run history, linked requirements, test plans, suites, defects, or raw payloads.
- The user needs a local JSON artifact written to disk before the result is summarized.
- The user asks which issues a person is working on now or worked on before and the workflow should start from search rather than a named issue key.

## Runtime
- Prefer the deployed executable at `<workspace-root>/.github/tools/jira-context/jira-context.exe`.
- The portable runtime bundle lives under the target workspace `.github/tools/jira-context/` folder so the source repository can live elsewhere.
- The deployed bundle is executable-first: call `jira-context.exe` directly rather than constructing Python commands yourself.
- If the current session cannot execute commands, stop immediately and report that the CLI cannot be run from this session.
- When execution is unavailable, do not search for MCP configs, VS Code tasks, command bridges, or workspace wrappers as a fallback.
- If the tool may need credentials or first-run setup, tell the user to run `.github/tools/jira-context/jira-context.exe configure` themselves in their terminal. Do not ask them to paste passwords, tokens, or other secrets into chat.
- Write machine-readable output with `Out-File -Encoding utf8` instead of `>` when saving JSON.
- For `search` and `fetch`, the canonical agent-facing payload is the saved normalized JSON file on disk, not terminal stdout.
- Do not create runtime JSON files inside `.github/skills/`. Keep persisted normalized and raw JSON outputs under the target workspace `.github/tools/jira-context/jira-output/` folder or an explicit user-provided save path.
- When requesting permission to run a Jira CLI command, ask for approval on the exact `jira-context.exe ...` command only. Do not generate PowerShell wrapper functions, pre/post directory scans, file-diff scaffolding, or other validation scripts unless the user explicitly asked for that deeper validation.
- Never wrap a Jira fetch in a one-off PowerShell program that captures stdout, tracks `$LASTEXITCODE`, probes file existence, or prints sentinel blocks such as `RESULT_START`, `FIRST_OUTPUT_START`, or `SECOND_OUTPUT_START`.
- If `--save-normalized-to` was used or should be used, do not inspect terminal transcript files such as Copilot chat `content.txt` resources. Open the saved normalized JSON file directly.

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

## Update And Configure
If the user needs the latest installer or wants to refresh the deployed bundle, give them this direct PowerShell command to run themselves:

```powershell
iwr -OutFile install-jira-context.ps1 https://github.com/FuentesJ2/jira-lens-cli/raw/main/install-jira-context.ps1; .\install-jira-context.ps1; .\.github\tools\jira-context\jira-context.exe
```

If the CLI reports missing Jira settings or auth, tell the user to run this command themselves in their terminal:

```powershell
.\.github\tools\jira-context\jira-context.exe configure
```

- Do not run `configure` on the user's behalf when it will prompt for credentials.
- Do not request passwords or tokens through chat or approval prompts.
- After the user finishes `configure`, continue with the direct `search` or `fetch` command.

## Working With Tessie
- When this skill and the Tessie or MFD Test Script Agent workflow are both relevant, this skill owns live Jira and TestRay retrieval and Tessie owns downstream test-case or script generation.
- If the user names a Jira issue key or asks for current requirement text, status, links, comments, authored steps, ad hoc runs, or related issues, run `jira-context.exe` first instead of answering from repository CSVs.
- Treat repository CSV exports and supporting docs as secondary references for style, compatibility, offline work, or cross-checking after the live fetch. They do not replace the CLI for the named Jira issue.
- If live Jira data and repository CSVs disagree, report both and prefer the live CLI fetch for current issue metadata.
- After a live fetch, Tessie may use the normalized JSON results to generate or revise test cases and scripts.
- Only skip the CLI-first fetch when the user explicitly asks for a CSV-only or offline workflow, or when Jira access is unavailable.

## Core Flow
1. Default to named-issue fetches first: determine the issue kind and use `test-case` for MFD test cases, `requirement` for requirement issues such as `DMFDREQ-1448`, and `problem-report` for linked bug or problem-report issues.
2. Always run fetches with `--save-normalized-to` so the CLI writes the normalized JSON intentionally to `jira-output/` or a user-provided path.
3. After the fetch completes, open the saved normalized JSON file directly before any repo, code, or test search.
4. Do not treat terminal stdout, PowerShell transcript output, or Copilot chat-session resource files as the primary payload when the saved normalized JSON file exists.
5. When summarizing from normalized JSON, name the exact stable keys you used instead of generic text-search.
6. If the first fetch is a `test-case`, inspect the currently linked requirements from that saved normalized JSON before finishing the initial analysis unless the user asked to stay on the test case only.
7. If the user wants raw source payload JSON too, add `--include-raw-payload` or `--save-raw-payload-to`, but keep raw payloads on disk unless they are needed.
8. When the user asks for a specific slice, prefer `--section` over a full dump.
9. If the CLI fails or the Jira/TestRay shape is unclear, use the troubleshooting commands in [debugging reference](./references/debugging.md) before concluding the data is unavailable.
10. Unless the user explicitly asks for code impact, test impact, implementation comparison, or framework behavior, stop after the Jira/TestRay summary and `Next Query Layers`.
11. If missing settings or auth prevent progress, instruct the user to run `.github/tools/jira-context/jira-context.exe configure` themselves before you continue.
12. If the user starts from a person rather than a named issue key, switch to the search workflow described below, save the search JSON first, and only then pivot into a targeted fetch.

## Focused Fetches
- `links`
- `comments`
- `authored-steps`
- `ad-hoc-runs`
- `test-management`

Use the exact command patterns in [commands reference](./references/commands.md).

## Search As A Secondary Workflow
Use this only when the user starts from a person or from JQL rather than a named issue key.

Ask to run or approve one direct CLI search command in this shape when the user asks about a person's recent or historical issues:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe search person "Dustin Marek" --mode current-or-history --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/dustin-marek-current-or-history.json
```

Raw JQL power-user shape:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe search --jql "assignee = \"Dustin Marek\" ORDER BY updated DESC" --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/dustin-marek-search.json
```

- For people-search prompts, run a direct `search` command first instead of guessing issue keys from repository files, transcripts, or memory.
- Always include `--save-normalized-to` for agent-driven Jira searches.
- After a search completes, open the saved normalized JSON file directly and use the returned issue keys from that file.
- Only pivot into `fetch` after the saved search JSON identifies the issue key worth inspecting next.
- Do not infer issue keys from transcript artifacts, stale repo exports, or unsaved terminal output.

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