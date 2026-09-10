# API Scope

## Purpose

Provide deterministic, agent-usable JIRA context retrieval for the MFD workflow.

## Initial vertical slices

1. Fetch a single JIRA test case issue by key.
2. Fetch a single JIRA requirement issue by key.

## Deferred slices

1. Linked-issue graph traversal.
2. Attachment retrieval.
3. Scope-wide project search.
4. Cached issue bundles for repeated agent sessions.

## CLI surface draft

### Fetch a single issue

`jira-context fetch test-case MFD-1234`

`jira-context fetch requirement DMFDREQ-1234`

### Start MCP server

`jira-context serve-mcp`

## MCP tool surface draft

1. `get_test_case(issue_key)`
2. `get_requirement(issue_key)`

## Output shape draft

Each fetch should eventually normalize the response into a stable structure with:

1. Issue key
2. Issue type
3. Summary
4. Description
5. Status
6. Relevant custom fields
7. Outbound and inbound links metadata
8. Raw source URL

## Open design questions

1. Which JIRA deployment is authoritative for this workflow: Jira Cloud, Jira Server, or Data Center?
2. Which authentication path should be supported first?
3. Which fields on test case issues are required for your workflow beyond summary and description?
4. Which fields on requirement issues are required for your workflow beyond summary and description?