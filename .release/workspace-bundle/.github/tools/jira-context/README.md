# jira-context Portable Runtime

This folder is the portable runtime bundle for the Jira context CLI.

The preferred deployed shape is a compiled `jira-context.exe` plus this folder's support files.

## Runtime contract

- Run `jira-context.exe` from this folder.
- Configuration is stored in `.env` in this folder.
- Raw trust artifacts are written to `.artifacts/tmp/` in this folder.
- User-visible saved JSON files can go in `jira-output/` in this folder.
