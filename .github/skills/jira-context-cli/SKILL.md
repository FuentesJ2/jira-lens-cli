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
- Write machine-readable output with `Out-File -Encoding utf8` instead of `>` when saving JSON.
- For `fetch`, the agent-facing payload should stay normalized and small.
- Do not create runtime JSON files inside `.github/skills/`. Keep persisted normalized and raw JSON outputs under the target workspace `.github/tools/jira-context/jira-output/` folder or an explicit user-provided save path.
- When requesting permission to run a Jira CLI command, ask for approval on the exact `jira-context.exe ...` command only. Do not generate PowerShell wrapper functions, pre/post directory scans, file-diff scaffolding, or other validation scripts unless the user explicitly asked for that deeper validation.

## Working With Tessie
- When this skill and the Tessie or MFD Test Script Agent workflow are both relevant, this skill owns live Jira and TestRay retrieval and Tessie owns downstream test-case or script generation.
- If the user names a Jira issue key or asks for current requirement text, status, links, comments, authored steps, ad hoc runs, or related issues, run `jira-context.exe` first instead of answering from repository CSVs.
- Treat repository CSV exports and supporting docs as secondary references for style, compatibility, offline work, or cross-checking after the live fetch. They do not replace the CLI for the named Jira issue.
- If live Jira data and repository CSVs disagree, report both and prefer the live CLI fetch for current issue metadata.
- After a live fetch, Tessie may use the normalized JSON results to generate or revise test cases and scripts.
- Only skip the CLI-first fetch when the user explicitly asks for a CSV-only or offline workflow, or when Jira access is unavailable.

## Procedure
1. Determine the issue kind: use `test-case` for MFD test cases, `requirement` for requirement issues such as `DMFDREQ-1448`, and `problem-report` for linked bug or problem-report issues.
2. For a small or focused fetch, run the CLI normally and treat stdout as the normalized payload the agent should read.
3. If the payload may be large, use `--save-normalized-to` immediately so the normalized JSON is written intentionally to `jira-output/` by the CLI.
4. If `--save-normalized-to` was used, read that saved normalized JSON file before any repo, code, or test search. Do not treat the saved file as a trailing artifact check.
5. When you read normalized JSON, name the exact stable keys you used before doing any generic text processing.
6. For a `requirement` fetch, inspect this order first: `issue_key`, `summary`, `description`, `status`, `custom_fields`, `links`, then `comments`.
7. Unless the user explicitly asks for code impact, test impact, implementation comparison, or framework behavior, stop after the Jira/TestRay summary and `Next Query Layers`. Do not pivot into workspace searches on your own.
8. If the first fetch is a `test-case`, always inspect and digest the currently linked requirements from that normalized payload before finishing the initial analysis, unless the user explicitly asked to stay on the test case only.
9. If the user wants raw source payload JSON too, add `--include-raw-payload` or `--save-raw-payload-to`. Keep the raw payload on disk and out of the main summary path unless it is needed.
10. Only open the saved raw payload file or use text-search when the normalized schema is genuinely unknown or the user explicitly wants source-payload details.
11. When the user asks for a specific slice, prefer `--section` over a full dump.
12. If the CLI fails or the Jira/TestRay shape is unclear, use the troubleshooting commands in [debugging reference](./references/debugging.md) before concluding the data is unavailable.
13. For simple fetch validation, request execution of the direct CLI command only. Do not wrap it in a generated `pwsh` program just to observe side effects.
14. After the initial analysis, always tell the user what the next query layer is, if any, for example linked requirements, related issues on a requirement, or an open problem report worth expanding.

## Explain Fetch
- `fetch` retrieves one Jira issue key and normalizes it into a smaller, stable JSON schema for the agent.
- The agent should treat stdout from `fetch` as the primary payload only when the payload is small enough to stay manageable inline.
- A normal `fetch` should not create any background artifact files.
- A normal `fetch` validation should also be requested as a normal command, not as an agent-generated script wrapper.
- If `--include-raw-payload` or `--save-raw-payload-to` is used, the raw Jira and Synapse source payloads are written to disk as JSON files and are not automatically placed into the model context.
- If `--save-normalized-to` is used, the normalized payload is written to a user-visible JSON file that the agent should read directly when the fetch may be large.
- When `--save-normalized-to` is used, that saved normalized file becomes the canonical artifact to read first before any broader repo investigation.
- Raw artifacts are sanitized before they are written: recursive `avatarUrls` fields are removed.
- Do not describe `fetch` as getting multiple issues. It fetches one issue and can optionally save two JSON file outputs: one normalized JSON file and one raw payload JSON file.
- Do not write generic tree-walk scripts against normalized fetch output unless the schema is genuinely unknown. Read the stable normalized keys directly from the saved normalized JSON first.
- `jira-output/` is the default persisted output folder for both normalized JSON and optional raw payload JSON files.

## Default Fetch
```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754
```

## Optional Audit Fetch
```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-normalized.json --save-raw-payload-to <workspace-root>/.github/tools/jira-context/jira-output/fetch-test-case-MFD-7754-full-raw-payload.json
```

## Focused Fetches
- `links`
- `comments`
- `authored-steps`
- `ad-hoc-runs`
- `test-management`

Use the exact command patterns in [commands reference](./references/commands.md).

## Output Guidance
- Prefer normalized output for summaries.
- Default to plain `fetch` with no save flags and no raw flags for small or focused payloads.
- If the payload may be large, prefer `--save-normalized-to` and then read the saved JSON file instead of depending on inline stdout delivery.
- If `--save-normalized-to` was used, read that saved JSON before any repo search and state which normalized keys you relied on.
- Keep raw payload JSON on disk instead of in the agent-facing stdout whenever `fetch` is used.
- Explain `--include-raw-payload` plainly as: normalized JSON stays on stdout, and the original raw payload JSON is written to `jira-output/`.
- The agent only sees the raw payload file if it explicitly opens that file afterward. A fetch alone does not automatically stuff the raw payload into the model context.
- After saving normalized output, read the known keys directly and summarize from that file rather than using generic text-search.
- Do not pivot into codebase, test-framework, or implementation searches after a fetch unless the user explicitly asked for that second layer of analysis.
- Present data in markdown tables whenever the fields fit cleanly into rows and columns. Use bullets only for long prose, detailed commentary, or evidence that does not fit a table cleanly.
- When a test case is fetched first, include the current linked requirements in the initial summary rather than treating them as optional follow-up context.
- Use `--section comments` first when the user wants narrative history such as who worked on the issue, promotions or demotions mentioned in comments, bug discovery notes, repro notes, linked sub-task keys mentioned in comments, or bulk-update notes.
- Do not claim that `comments` includes Jira field-change history, status-transition history, or every workflow action. That requires changelog data, which is not yet normalized by the CLI.
- If the CLI reports missing config or auth, tell the user exactly which saved Jira setting is missing instead of guessing.
- Only use raw payload inspection or text-search against normalized output when the schema is actually unknown. Read the normalized JSON keys directly first.
- End the summary with a short `Next Query Layers` section whenever more graph edges exist that could be explored usefully.

## Summary Style
- Keep the CLI fetch pure. Do not invent synthetic sections such as a combined step view.
- When the user asks for a rundown after a full fetch, present it as a clean chat summary built from the fetched sections.
- Prefer markdown tables whenever they make the data easier to scan, especially for snapshots, linked items, run history, and requirement lists.
- Use short headings, strong labels, and compact commentary so the chat answer feels deliberate rather than like a JSON paraphrase.
- Prefer this order for test-case rundowns:
	1. Snapshot: issue key, type, status, assignee, summary.
	2. Current Requirements: linked requirements for the current test case, plus any immediate signals they should be expanded next.
	3. Test Intent: short objective, step count.
	4. Execution Signals: latest ad hoc run status, notable failed steps, attachments or screenshots if present.
	5. Related Issues: linked problem reports, related epics, or referenced issues.
	6. Comments Worth Reading: only the notable comments, with who and why they matter.
	7. Next Query Layers: the most useful unexplored branches, stated explicitly.
- Preferred chat shape:

```markdown
**Snapshot**
| Key | Type | Status | Assignee | Summary |
| --- | --- | --- | --- | --- |
| MFD-7754 | Test Case | Draft | Julio Fuentes Jr (Contractor) | DELTA - DIAG XPDR Reported Parameter Callsign Test Case |

**Current Requirements**
| Requirement | Summary | Why It Matters | Next Layer |
| --- | --- | --- | --- |
| DMFDREQ-1448 | DIAG XPDR Reported Parameter Callsign | Current requirement linked to the test case | Check its related issues if the failure may be a requirement mismatch |

**Test Intent**
| Objective | Authored Steps |
| --- | --- |
| Show that the DIAG XPDR page correctly displays the Callsign. | 8 |

**Execution Signals**
| Latest Run | Status | Notable Result | Evidence |
| --- | --- | --- | --- |
| 16/Jul/26 9:47 AM by YuJ | Failed | Step 8 failed on the value 128 case | screenshot-1.png |

**Related Issues**
| Issue | Relationship | Status | Summary |
| --- | --- | --- | --- |
| MFD-8100 | relates to | Open | DIAG-XPDR Callsign bug found |
| APRD-1743 | references | Closed | MFD-7754 value 128 prevents display |

**Comments Worth Reading**
- 2024-02-15 | Eric Schubel: possible bug discovered with value 128; recommended demotion to Draft.
- 2024-02-15 | Lizette Osorio: reproduced the bug and noted framework or VM crash afterward.

**Next Query Layers**
| Next Node | Why Query It |
| --- | --- |
| DMFDREQ-1448 | The current requirement may have related issues or lineage that explains the failing expectation. |
| MFD-8100 | The open problem report may confirm whether the latest failure is already understood and tracked. |
```

- Keep each section tight. If a section has nothing useful, say `None found` instead of padding it.
- Prefer the normalized payload for the main rundown and use the raw payload only to confirm notable evidence or preserve exact wording.
- If the user asked for a pure section like `comments` or `ad-hoc-runs`, summarize only that section unless they ask for more.

## References
- Use [commands reference](./references/commands.md) for normal day-to-day fetch commands and advanced fetch flag explanations.
- Use [debugging reference](./references/debugging.md) only for troubleshooting, environment setup recovery, or schema discovery.