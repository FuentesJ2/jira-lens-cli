"""Local MCP server entry point for the JIRA context harness."""

from __future__ import annotations

from typing import Any, Sequence

from jira_context_harness.cli import _default_fields_for, _render_fetch_payload
from jira_context_harness.config import load_settings
from jira_context_harness.jira_client import FetchRequest, JiraClient, JiraConfigurationError


def fetch_issue_tool_payload(
    issue_kind: str,
    issue_key: str,
    *,
    section: str = "full",
    include_raw: bool = False,
) -> object:
    if issue_kind == "requirement" and section not in {"full", "issue", "links"}:
        raise ValueError("Requirement issues only support sections full, issue, and links")

    settings = load_settings()
    missing = settings.missing_required()
    if missing:
        raise JiraConfigurationError(
            "Missing required Jira settings: " + ", ".join(missing)
        )

    client = JiraClient(settings)
    result = client.fetch_issue(
        FetchRequest(
            issue_kind=issue_kind,
            issue_key=issue_key,
            fields=_default_fields_for(issue_kind),
        )
    )
    return _render_fetch_payload(
        result=result,
        view="both" if include_raw else "normalized",
        section=section,
    )


def build_server() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP Python dependency is not installed. Install the project dependencies and rerun `python run_cli.py serve-mcp`."
        ) from exc

    server = FastMCP("jira-context-harness")

    @server.tool()
    def get_test_case(
        issue_key: str,
        section: str = "full",
        include_raw: bool = False,
    ) -> object:
        """Fetch one Jira test case with optional TestRay-focused sections."""

        return fetch_issue_tool_payload(
            "test-case",
            issue_key,
            section=section,
            include_raw=include_raw,
        )

    @server.tool()
    def get_requirement(issue_key: str, include_raw: bool = False) -> object:
        """Fetch one Jira requirement issue with normalized links and fields."""

        return fetch_issue_tool_payload(
            "requirement",
            issue_key,
            section="full",
            include_raw=include_raw,
        )

    return server


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    server = build_server()
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())