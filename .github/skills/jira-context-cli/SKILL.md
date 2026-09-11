---
name: jira-context-cli
description: 'Use when you need Jira or TestRay context from avjira through the portable jira-context CLI bundle. Fetch test cases, requirements, problem reports, issue links, comment history, authored steps, ad hoc runs, raw API payloads, field discovery, Synapse probes, or page-inspection clues.'
argument-hint: 'Provide issue kind and issue key, for example: test-case MFD-7754, requirement DMFDREQ-1448, or problem-report MFD-8100.'
---

# Jira Context CLI

This tracked skill is the deployment source for the workspace copy at `C:/Dev/.github/skills/jira-context-cli/SKILL.md`.
Keep the deployed copy synchronized with this source file.

## When to Use
- The user wants the agent to see the same Jira/TestRay data they can inspect themselves.
- The user asks for Jira issue links, linked problem reports, comment history, authored test steps, ad hoc run history, linked requirements, test plans, suites, defects, or raw payloads.
- The user needs a trustable local artifact written to disk before the result is summarized.

## Runtime
- Prefer the portable launcher at `C:/Dev/.github/tools/jira-context/jira-context.cmd`.
- The portable runtime bundle lives under `C:/Dev/.github/tools/jira-context/` so the source repository can live elsewhere.
- If `jira-context.exe` is present in that folder, the launcher uses it first. Otherwise it uses any available Python 3.9+ interpreter through `py` or `python`.
- The agent should still call the launcher directly rather than constructing Python commands itself.
- Write machine-readable output with `Out-File -Encoding utf8` instead of `>` when saving JSON.
- For `fetch`, the agent-facing payload should stay normalized and small.
- Do not create runtime JSON artifacts inside `.github/skills/`. Keep ephemeral payload artifacts under `C:/Dev/.github/tools/jira-context/.artifacts/tmp/` so the skill folder stays versionable and clean.
- When requesting permission to run a Jira CLI command, ask for approval on the exact `jira-context.cmd ...` command only. Do not generate PowerShell wrapper functions, pre/post directory scans, file-diff scaffolding, or other validation scripts unless the user explicitly asked for that deeper validation.

## Procedure
1. Determine the issue kind: use `test-case` for MFD test cases, `requirement` for requirement issues such as `DMFDREQ-1448`, and `problem-report` for linked bug or problem-report issues.
2. For a general fetch, run the CLI normally and treat stdout as the normalized payload the agent should read.
3. If the user wants a trust artifact, add `--include-raw-payload`. That writes the heavy raw payload to `.artifacts/tmp/` while leaving stdout normalized.
4. Save the normalized stdout to a UTF-8 JSON file when the output may be large or when you want a user-visible artifact.
5. Read the normalized JSON file or terminal output, then summarize the relevant section back to the user.
6. Only open the raw artifact file if the user explicitly wants to inspect source payload details.
7. When the user asks for a specific slice, prefer `--section` over a full dump.
8. If the CLI fails or the Jira/TestRay shape is unclear, use the troubleshooting commands in [debugging reference](./references/debugging.md) before concluding the data is unavailable.
9. For simple fetch validation, request execution of the direct CLI command only. Do not wrap it in a generated `pwsh` program just to observe side effects.

## Explain Fetch
- `fetch` retrieves one Jira issue key and normalizes it into a smaller, stable JSON schema for the agent.
- The agent should treat stdout from `fetch` as the primary payload.
- A normal `fetch` should not create any background artifact files.
- A normal `fetch` validation should also be requested as a normal command, not as an agent-generated script wrapper.
- If `--include-raw-payload` or `--save-raw-payload-to` is used, the raw Jira and Synapse source payloads are written to disk as a trust artifact and are not automatically placed into the model context.
- If `--save-normalized-to` is used, the same normalized payload is also written to a user-visible JSON file.
- Raw artifacts are sanitized before they are written: recursive `avatarUrls` fields are removed.
- Do not describe `fetch` as getting multiple issues. It fetches one issue and can optionally save two file outputs: one normalized JSON file and one raw trust artifact.
- Do not write generic tree-walk scripts against normalized fetch output unless the schema is genuinely unknown. Read the stable normalized keys directly first.

## Default Fetch
```powershell
C:/Dev/.github/tools/jira-context/jira-context.cmd fetch test-case MFD-7754
```

## Optional Audit Fetch
```powershell
C:/Dev/.github/tools/jira-context/jira-context.cmd fetch test-case MFD-7754 --include-raw-payload | Out-File -Encoding utf8 C:/Dev/.github/tools/jira-context/jira-output/MFD-7754-normalized.json
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
- Default to plain `fetch` with no save flags and no raw flags unless the user explicitly wants persistence or source-payload auditability.
- Preserve raw payloads for trust, but keep them on disk instead of in the agent-facing stdout whenever `fetch` is used.
- Explain `--include-raw-payload` plainly as: normalized JSON stays on stdout, and the original heavy raw payload is written to `.artifacts/tmp/`.
- The agent only sees the raw artifact if it explicitly opens that file afterward. A fetch alone does not automatically stuff the raw payload into the model context.
- Use `--section comments` first when the user wants narrative history such as who worked on the issue, promotions or demotions mentioned in comments, bug discovery notes, repro notes, linked sub-task keys mentioned in comments, or bulk-update notes.
- Do not claim that `comments` includes Jira field-change history, status-transition history, or every workflow action. That requires changelog data, which is not yet normalized by the CLI.
- If the CLI reports missing config or auth, tell the user exactly which saved Jira setting is missing instead of guessing.
- Do not generate generic recursive PowerShell or shell extraction scripts against a normalized fetch unless the schema is actually unknown. Read the normalized JSON keys directly first.

## Summary Style
- Keep the CLI fetch pure. Do not invent synthetic sections such as a combined step view.
- When the user asks for a rundown after a full fetch, present it as a clean chat summary built from the fetched sections.
- Use short headings, strong labels, and compact bullets so the chat answer feels deliberate rather than like a JSON paraphrase.
- Prefer this order for test-case rundowns:
	1. Snapshot: issue key, type, status, assignee, summary.
	2. Test Intent: short objective, linked requirements, step count.
	3. Execution Signals: latest ad hoc run status, notable failed steps, attachments or screenshots if present.
	4. Related Issues: linked problem reports, related epics, or referenced issues.
	5. Comments Worth Reading: only the notable comments, with who and why they matter.
- Preferred chat shape:

```markdown
**Snapshot**
MFD-7754 | Test Case | Draft | Assignee: Julio Fuentes Jr (Contractor)
DELTA - DIAG XPDR Reported Parameter Callsign Test Case

**Test Intent**
- Objective: Show that the DIAG XPDR page correctly displays the Callsign.
- Linked requirements: DMFDREQ-1448
- Current authored steps: 8

**Execution Signals**
- Latest ad hoc run: Failed on 16/Jul/26 9:47 AM by YuJ
- Notable result: step 8 failed on the value 128 case
- Evidence: screenshot-1.png

**Related Issues**
- Problem report: MFD-8100 | Open | DIAG-XPDR Callsign bug found
- Reference: APRD-1743 | Closed | MFD-7754 value 128 prevents display

**Comments Worth Reading**
- 2024-02-15 | Eric Schubel: possible bug discovered with value 128; recommended demotion to Draft.
- 2024-02-15 | Lizette Osorio: reproduced the bug and noted framework or VM crash afterward.
```

- Keep each section tight. If a section has nothing useful, say `None found` instead of padding it.
- Prefer the normalized payload for the main rundown and use the raw payload only to confirm notable evidence or preserve exact wording.
- If the user asked for a pure section like `comments` or `ad-hoc-runs`, summarize only that section unless they ask for more.

## References
- Use [commands reference](./references/commands.md) for normal day-to-day fetch commands and advanced fetch flag explanations.
- Use [debugging reference](./references/debugging.md) only for troubleshooting, environment setup recovery, or schema discovery.