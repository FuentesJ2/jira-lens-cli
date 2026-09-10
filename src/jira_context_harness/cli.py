"""CLI entry point for the JIRA context harness."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from jira_context_harness.config import load_settings
from jira_context_harness.jira_client import (
    FetchRequest,
    JiraClient,
    JiraClientError,
    JiraConfigurationError,
)


DEFAULT_TEST_CASE_FIELDS = [
    "summary",
    "description",
    "status",
    "issuetype",
    "project",
    "assignee",
    "updated",
    "issuelinks",
]


def _default_fields_for(issue_kind: str) -> list[str]:
    if issue_kind == "test-case":
        return list(DEFAULT_TEST_CASE_FIELDS)
    return list(DEFAULT_TEST_CASE_FIELDS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira-context",
        description="Local CLI for JIRA context retrieval and MCP serving.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch a single JIRA issue for local inspection or downstream agent use.",
    )
    fetch_parser.add_argument(
        "issue_kind",
        choices=["test-case", "requirement"],
        help="Type of issue to fetch.",
    )
    fetch_parser.add_argument("issue_key", help="JIRA issue key, such as MFD-1234.")
    fetch_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format for the fetched issue.",
    )
    fetch_parser.add_argument(
        "--view",
        choices=["normalized", "raw", "both"],
        default="normalized",
        help="Choose normalized output, raw API JSON, or both in one JSON object.",
    )
    fetch_parser.add_argument(
        "--field",
        action="append",
        dest="fields",
        default=None,
        help="Additional Jira field to request. Can be passed multiple times.",
    )
    fetch_parser.add_argument(
        "--expand",
        action="append",
        default=None,
        help="Jira expand value to request. Can be passed multiple times.",
    )
    fetch_parser.add_argument(
        "--property",
        action="append",
        dest="properties",
        default=None,
        help="Jira issue property to request. Can be passed multiple times.",
    )
    fetch_parser.add_argument(
        "--fields-by-keys",
        action="store_true",
        help="Request custom fields by key when supported by the Jira site.",
    )
    fetch_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Set failFast=false on the Jira request.",
    )

    subparsers.add_parser(
        "serve-mcp",
        help="Run the local MCP server wrapper for agent tool access.",
    )
    return parser


def render_fetch_output(
    *,
    result: object,
    output_format: str,
    view: str,
) -> str:
    if output_format == "text":
        if view != "normalized":
            raise ValueError("Text format only supports normalized view")
        issue = result.issue
        lines = [
            f"Issue key: {issue.issue_key}",
            f"Issue kind: {issue.issue_kind}",
            f"Issue type: {issue.issue_type}",
            f"Status: {issue.status}",
            f"Project: {issue.project_key}",
            f"Assignee: {issue.assignee}",
            f"Updated: {issue.updated}",
            f"Summary: {issue.summary}",
            f"Description format: {issue.description_format}",
            "Description:",
            issue.description,
        ]
        return "\n".join(lines).rstrip() + "\n"

    if view == "normalized":
        payload = result.normalized_dict()
    elif view == "raw":
        payload = result.raw_response
    else:
        payload = result.combined_dict()
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "fetch":
        if args.format == "text" and args.view != "normalized":
            parser.error("--format text only supports --view normalized")

        request_model = FetchRequest(
            issue_kind=args.issue_kind,
            issue_key=args.issue_key,
            fields=_default_fields_for(args.issue_kind) + (args.fields or []),
            expand=args.expand,
            properties=args.properties,
            fields_by_keys=args.fields_by_keys,
            fail_fast=not args.allow_partial,
        )
        try:
            client = JiraClient(load_settings())
            result = client.fetch_issue(request_model)
        except (JiraConfigurationError, JiraClientError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(
            render_fetch_output(
                result=result,
                output_format=args.format,
                view=args.view,
            ),
            end="",
        )
        return 0

    if args.command == "serve-mcp":
        print("serve-mcp is scaffolded but not implemented yet", file=sys.stderr)
        return 2

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())