# Jira Context CLI Commands

All commands in this skill use the isolated harness runtime:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe
```

This file is for normal day-to-day CLI usage.
Debugging and development-only commands live in [debugging.md](./debugging.md).

## Full Fetches

Default agent fetch with no artifact side effects:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754
```

If the normalized payload may be large, save it directly from the CLI and read that file first:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-normalized.json
```

Fetch normalized test-case JSON and also save the raw trust payload to the hidden artifact folder:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-normalized.json --save-raw-payload-to <workspace-root>/.github/tools/jira-context/.artifacts/tmp/fetch-test-case-MFD-7754-full-raw-payload.json
```

Fetch and name the normalized file and raw artifact explicitly in one command:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-normalized.json --save-raw-payload-to <workspace-root>/.github/tools/jira-context/.artifacts/tmp/fetch-test-case-MFD-7754-full-raw-payload.json
```

The raw trust artifact for that command is written automatically to:

```text
<workspace-root>/.github/tools/jira-context/.artifacts/tmp/fetch-test-case-MFD-7754-full-raw-payload.json
```

The normalized file is what the agent should read first. Access the stable keys directly from that JSON before doing any generic text processing.
The raw artifact is only for trust checks and source-payload inspection when the schema is genuinely unknown or the user explicitly asks for it.
Do not place runtime JSON payloads inside `.github/skills/`; keep them under the harness runtime area instead.

Fetch normalized requirement JSON and also save the raw trust payload:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch requirement DMFDREQ-1448 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/DMFDREQ-1448-normalized.json --save-raw-payload-to <workspace-root>/.github/tools/jira-context/.artifacts/tmp/fetch-requirement-DMFDREQ-1448-full-raw-payload.json
```

Fetch normalized problem-report JSON and also save the raw trust payload:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch problem-report MFD-8100 --save-normalized-to <workspace-root>/.github/tools/jira-context/jira-output/MFD-8100-normalized.json --save-raw-payload-to <workspace-root>/.github/tools/jira-context/.artifacts/tmp/fetch-problem-report-MFD-8100-full-raw-payload.json
```

## Advanced Fetch Options

Most users should ignore these unless they are intentionally widening the Jira API request.

### Why these flags exist

- `--field <name>` exists because the normal fetch only asks Jira for the small set of fields this workflow usually needs. If you need some extra Jira field that is not in the normal contract, this lets you ask for it directly. Without it, you miss that field entirely.
- `--expand <name>` exists because some Jira data is only available when Jira is told to expand it. Think of it as asking Jira to unfold extra details instead of giving you the short version. Without it, you may only get the compact form and miss richer nested data.
- `--property <key>` exists because Jira issue properties are a separate storage area from normal issue fields. If some integration stored useful data there, a normal fetch will not include it unless you ask. Without it, you miss those properties completely.
- `--fields-by-keys` exists because some Jira sites or workflows refer to fields by key names instead of numeric-looking ids like `customfield_12345`. This flag tells Jira how to interpret the field names you passed. Without it, a field request can fail or return nothing if Jira expected keys instead of ids.
- `--allow-partial` exists because a fetch can fail if even one requested extra field, property, or expansion is bad or unsupported. This flag says: give me what you can instead of failing the whole request. Without it, one bad add-on request can block the entire fetch.
- `--no-config-prompt` exists for non-interactive use. The normal CLI tries to help a human by prompting for missing Jira settings on first run. This flag turns that off so a script, automation step, or controlled validation run fails immediately instead of waiting for user input.

### What they provide in practice

- `--field <name>` widens the source Jira payload with one or more extra fields. It does not automatically add new normalized keys, but it can make those raw values available for inspection or future normalization work.
- `--expand <name>` widens the response by asking Jira for fuller nested structures.
- `--property <key>` pulls targeted issue-property data into the Jira response.
- `--fields-by-keys` changes how Jira resolves the field identifiers you requested.
- `--allow-partial` makes exploratory fetches more forgiving.
- `--no-config-prompt` makes the CLI behave predictably in scripted or approval-based workflows.

## Focused Sections

Issue links:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --section links --include-raw-payload | Out-File -Encoding utf8 <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-links.json
```

Comment history:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --section comments --include-raw-payload | Out-File -Encoding utf8 <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-comments.json
```

Authored test steps:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --section authored-steps --include-raw-payload | Out-File -Encoding utf8 <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-authored-steps.json
```

Ad hoc test runs:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --section ad-hoc-runs --include-raw-payload | Out-File -Encoding utf8 <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-ad-hoc-runs.json
```

Full test-management payload:

```powershell
<workspace-root>/.github/tools/jira-context/jira-context.exe fetch test-case MFD-7754 --section test-management --include-raw-payload | Out-File -Encoding utf8 <workspace-root>/.github/tools/jira-context/jira-output/MFD-7754-test-management.json
```