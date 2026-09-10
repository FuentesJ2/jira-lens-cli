"""Smoke tests for the scaffolded CLI."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from jira_context_harness.cli import build_parser, main, render_fetch_output
from jira_context_harness.config import JiraSettings
from jira_context_harness.models import JiraFetchResult, JiraIssueContext


class BuildParserTests(unittest.TestCase):
    def test_fetch_accepts_test_case(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234"])

        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.issue_kind, "test-case")
        self.assertEqual(args.issue_key, "MFD-1234")
        self.assertEqual(args.format, "json")
        self.assertEqual(args.view, "normalized")

    def test_fetch_accepts_requirement(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "requirement", "DMFDREQ-1234"])

        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.issue_kind, "requirement")
        self.assertEqual(args.issue_key, "DMFDREQ-1234")

    def test_fetch_accepts_raw_view(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234", "--view", "raw"])

        self.assertEqual(args.view, "raw")

    def test_serve_mcp_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-mcp"])

        self.assertEqual(args.command, "serve-mcp")


class CliOutputTests(unittest.TestCase):
    def test_render_fetch_output_supports_raw_json(self) -> None:
        result = JiraFetchResult(
            issue=JiraIssueContext(
                issue_key="MFD-1234",
                issue_kind="test-case",
                summary="Summary",
                description="Description",
                description_format="plain_text",
                status="Approved",
                issue_type="Test",
                project_key="MFD",
                assignee="User",
                updated="2026-09-10T00:00:00.000+0000",
                source_url="https://example.atlassian.net/browse/MFD-1234",
            ),
            raw_response={"key": "MFD-1234", "fields": {"summary": "Summary"}},
        )

        output = render_fetch_output(result=result, output_format="json", view="raw")

        self.assertIn('"key": "MFD-1234"', output)

    def test_main_emits_json_for_fetch(self) -> None:
        result = JiraFetchResult(
            issue=JiraIssueContext(
                issue_key="MFD-1234",
                issue_kind="test-case",
                summary="Summary",
                description="Description",
                description_format="plain_text",
                status="Approved",
                issue_type="Test",
                project_key="MFD",
                assignee="User",
                updated="2026-09-10T00:00:00.000+0000",
                source_url="https://example.atlassian.net/browse/MFD-1234",
            ),
            raw_response={"key": "MFD-1234"},
        )

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    exit_code = main(["fetch", "test-case", "MFD-1234"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"issue_key": "MFD-1234"', stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")


class LauncherSupportTests(unittest.TestCase):
    def test_cli_main_imports_from_package_surface(self) -> None:
        from jira_context_harness import cli

        self.assertTrue(callable(cli.main))


if __name__ == "__main__":
    unittest.main()