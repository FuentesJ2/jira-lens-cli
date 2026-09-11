# Jira Context CLI Debugging Commands

Use this file only when the normal fetch workflow is failing, the Jira/TestRay shape is unclear, or the local environment needs repair.

## Authentication

Probe Jira authentication:

```powershell
C:/Dev/.github/tools/jira-context/jira-context.cmd probe-auth | Out-File -Encoding utf8 C:/Dev/.github/tools/jira-context/jira-output/jira-auth-probe.json
```

## Schema Discovery

Inspect interesting Jira fields:

```powershell
C:/Dev/.github/tools/jira-context/jira-context.cmd discover-fields MFD-7754 --include-raw | Out-File -Encoding utf8 C:/Dev/.github/tools/jira-context/jira-output/jira-field-discovery.json
```

Inspect Jira browse-page HTML clues:

```powershell
C:/Dev/.github/tools/jira-context/jira-context.cmd inspect-page MFD-7754 --include-html | Out-File -Encoding utf8 C:/Dev/.github/tools/jira-context/jira-output/jira-issue-page-inspection.json
```

## TestRay Or Synapse Probing

Probe documented Synapse or TestRay endpoints:

```powershell
C:/Dev/.github/tools/jira-context/jira-context.cmd probe-synapse MFD-7754 | Out-File -Encoding utf8 C:/Dev/.github/tools/jira-context/jira-output/jira-synapse-probe.json
```

## Local Environment Recovery

If the portable launcher is present but Python is missing, install any Python 3.9+ interpreter and ensure `py` or `python` is available on PATH.

```powershell
py -3 --version
python --version
```