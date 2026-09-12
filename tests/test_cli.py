"""Smoke tests for the scaffolded CLI."""

from __future__ import annotations

import io
from pathlib import Path
import unittest
from unittest.mock import patch

from jira_context_harness.cli import build_parser, main, render_fetch_output, render_search_output
from jira_context_harness.config import JiraSettings
from jira_context_harness.jira_client import JiraAuthProbeAttempt
from jira_context_harness.models import JiraFetchResult, JiraIssueContext, JiraSearchIssue, JiraSearchResult


class _InteractiveInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class BuildParserTests(unittest.TestCase):
    def test_fetch_accepts_test_case(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234"])

        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.issue_kind, "test-case")
        self.assertEqual(args.issue_key, "MFD-1234")
        self.assertEqual(args.format, "json")
        self.assertEqual(args.view, "normalized")
        self.assertFalse(args.include_raw_payload)

    def test_fetch_accepts_requirement(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "requirement", "DMFDREQ-1234"])

        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.issue_kind, "requirement")
        self.assertEqual(args.issue_key, "DMFDREQ-1234")

    def test_fetch_accepts_problem_report(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "problem-report", "MFD-8100"])

        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.issue_kind, "problem-report")
        self.assertEqual(args.issue_key, "MFD-8100")

    def test_fetch_accepts_raw_view(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234", "--view", "raw"])

        self.assertEqual(args.view, "raw")

    def test_fetch_accepts_combined_view(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234", "--view", "combined"])

        self.assertEqual(args.view, "combined")

    def test_fetch_accepts_legacy_both_view_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234", "--view", "both"])

        self.assertEqual(args.view, "combined")

    def test_fetch_accepts_section(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "fetch",
            "test-case",
            "MFD-1234",
            "--section",
            "ad-hoc-runs",
        ])

        self.assertEqual(args.section, "ad-hoc-runs")

    def test_fetch_accepts_comments_section(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234", "--section", "comments"])

        self.assertEqual(args.section, "comments")

    def test_fetch_accepts_include_raw_payload(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "test-case", "MFD-1234", "--include-raw-payload"])

        self.assertTrue(args.include_raw_payload)

    def test_fetch_accepts_explicit_save_paths(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "fetch",
            "test-case",
            "MFD-1234",
            "--save-normalized-to",
            "C:/tmp/MFD-1234-normalized.json",
            "--save-raw-payload-to",
            "C:/tmp/MFD-1234-raw.json",
        ])

        self.assertEqual(args.save_normalized_to, "C:/tmp/MFD-1234-normalized.json")
        self.assertEqual(args.save_raw_payload_to, "C:/tmp/MFD-1234-raw.json")

    def test_search_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "search",
            "--jql",
            'assignee = "Dustin Marek" ORDER BY updated DESC',
            "--save-normalized-to",
            "C:/tmp/dustin-marek-search.json",
            "--limit",
            "5",
            "--start-at",
            "10",
        ])

        self.assertEqual(args.command, "search")
        self.assertEqual(args.jql, 'assignee = "Dustin Marek" ORDER BY updated DESC')
        self.assertEqual(args.save_normalized_to, "C:/tmp/dustin-marek-search.json")
        self.assertEqual(args.limit, 5)
        self.assertEqual(args.start_at, 10)

    def test_search_person_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "search",
            "person",
            "Dustin Marek",
            "--mode",
            "history",
            "--save-normalized-to",
            "C:/tmp/dustin-marek-history.json",
        ])

        self.assertEqual(args.command, "search")
        self.assertEqual(args.search_target, "person")
        self.assertEqual(args.search_value, "Dustin Marek")
        self.assertEqual(args.mode, "history")
        self.assertIsNone(args.jql)

    def test_search_person_accepts_order_by(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "search",
            "person",
            "Dustin Marek",
            "--order-by",
            "created",
            "--save-normalized-to",
            "C:/tmp/dustin-marek-created.json",
        ])

        self.assertEqual(args.order_by, "created")

    def test_search_requires_save_path(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit) as exit_context:
            parser.parse_args([
                "search",
                "--jql",
                'assignee = "Dustin Marek" ORDER BY updated DESC',
            ])

        self.assertEqual(exit_context.exception.code, 2)

    def test_search_person_defaults_to_current_mode(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "search",
            "person",
            "Dustin Marek",
            "--save-normalized-to",
            "C:/tmp/dustin-marek-current.json",
        ])

        self.assertIsNone(args.mode)

    def test_configure_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["configure"])

        self.assertEqual(args.command, "configure")

    def test_configure_advanced_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["configure", "--advanced"])

        self.assertEqual(args.command, "configure")
        self.assertTrue(args.advanced)

    def test_probe_auth_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["probe-auth"])

        self.assertEqual(args.command, "probe-auth")

    def test_discover_fields_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["discover-fields", "MFD-7754", "--include-raw"])

        self.assertEqual(args.command, "discover-fields")
        self.assertEqual(args.issue_key, "MFD-7754")
        self.assertTrue(args.include_raw)

    def test_probe_synapse_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["probe-synapse", "MFD-7754"])

        self.assertEqual(args.command, "probe-synapse")
        self.assertEqual(args.issue_key, "MFD-7754")

    def test_inspect_page_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["inspect-page", "MFD-7754", "--include-html"])

        self.assertEqual(args.command, "inspect-page")
        self.assertEqual(args.issue_key, "MFD-7754")
        self.assertTrue(args.include_html)


class CliOutputTests(unittest.TestCase):
    def test_render_search_output_supports_json(self) -> None:
        result = JiraSearchResult(
            query='assignee = "Dustin Marek" ORDER BY updated DESC',
            mode="raw-jql",
            total=1,
            returned=1,
            start_at=0,
            max_results=10,
            order_by="custom-jql",
            requested_fields=["summary", "updated"],
            issues=[
                JiraSearchIssue(
                    issue_key="MFD-9212",
                    summary="Summary",
                    status="In Progress",
                    issue_type="Problem Report",
                    project_key="MFD",
                    assignee="Dustin Marek",
                    reporter="Delta User",
                    updated="2026-09-11T12:34:56.000+0000",
                    source_url="https://avjira/browse/MFD-9212",
                )
            ],
        )

        output = render_search_output(result=result)

        self.assertIn('"query": "assignee = \\"Dustin Marek\\" ORDER BY updated DESC"', output)
        self.assertIn('"issue_key": "MFD-9212"', output)
        self.assertIn('"order_by": "custom-jql"', output)
        self.assertIn('"requested_fields": [', output)

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

        output = render_fetch_output(result=result, output_format="json", view="raw", section="full")

        self.assertIn('"key": "MFD-1234"', output)

    def test_render_fetch_output_supports_section_combined(self) -> None:
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
                test_management={
                    "ad_hoc_test_runs": [{"test_run_id": 1, "status": "Failed"}],
                },
            ),
            raw_response={"key": "MFD-1234"},
            supplemental_responses={"ad_hoc_test_runs": [{"ID": 1, "status": "Failed"}]},
        )

        output = render_fetch_output(
            result=result,
            output_format="json",
            view="combined",
            section="ad-hoc-runs",
        )

        self.assertIn('"normalized": [', output)
        self.assertIn('"raw_response": [', output)
        self.assertIn('"test_run_id": 1', output)

    def test_render_fetch_output_supports_comments_section(self) -> None:
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
                comments=[
                    {
                        "comment_id": "10001",
                        "author": "Delta User",
                        "author_key": "delta.user",
                        "created": "2026-09-10T01:00:00.000+0000",
                        "updated": "2026-09-10T01:05:00.000+0000",
                        "body": "Comment text",
                        "body_format": "plain_text",
                    }
                ],
            ),
            raw_response={
                "fields": {
                    "comment": {
                        "comments": [{"id": "10001", "body": "Comment text"}],
                    }
                }
            },
        )

        output = render_fetch_output(
            result=result,
            output_format="json",
            view="combined",
            section="comments",
        )

        self.assertIn('"normalized": [', output)
        self.assertIn('"raw_response": [', output)
        self.assertIn('"comment_id": "10001"', output)

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
                password="password",
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

    def test_main_include_raw_payload_writes_artifact_and_keeps_stdout_normalized(self) -> None:
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

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="password",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                with patch(
                    "jira_context_harness.cli._write_raw_payload_artifact",
                    return_value=Path("C:/Dev/jira-context-harness/jira-output/fetch-test-case-MFD-1234-full-raw-payload.json"),
                ) as artifact_mock:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main(["fetch", "test-case", "MFD-1234", "--include-raw-payload"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"issue_key": "MFD-1234"', stdout.getvalue())
        self.assertNotIn('"raw_response"', stdout.getvalue())
        self.assertIn("Saved raw payload JSON to", stderr.getvalue())
        artifact_mock.assert_called_once()

    def test_main_legacy_combined_view_alias_now_writes_artifact_and_emits_normalized_json(self) -> None:
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

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                with patch(
                    "jira_context_harness.cli._write_raw_payload_artifact",
                    return_value=Path("C:/Dev/jira-context-harness/jira-output/fetch-test-case-MFD-1234-full-raw-payload.json"),
                ):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main(["fetch", "test-case", "MFD-1234", "--view", "combined"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"issue_key": "MFD-1234"', stdout.getvalue())
        self.assertNotIn('"raw_response"', stdout.getvalue())
        self.assertIn("deprecated", stderr.getvalue())

    def test_main_save_paths_write_named_normalized_and_raw_outputs(self) -> None:
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

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                with patch(
                    "jira_context_harness.cli._write_raw_payload_artifact",
                    return_value=Path("C:/tmp/MFD-1234-raw.json"),
                ) as raw_mock:
                    with patch(
                        "jira_context_harness.cli._write_json_file",
                        return_value=Path("C:/tmp/MFD-1234-normalized.json"),
                    ) as json_mock:
                        stdout = io.StringIO()
                        stderr = io.StringIO()
                        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                            exit_code = main([
                                "fetch",
                                "test-case",
                                "MFD-1234",
                                "--save-normalized-to",
                                "C:/tmp/MFD-1234-normalized.json",
                                "--save-raw-payload-to",
                                "C:/tmp/MFD-1234-raw.json",
                            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        normalized_stderr = stderr.getvalue().replace("\\", "/")
        self.assertIn("Saved normalized output to C:/tmp/MFD-1234-normalized.json", normalized_stderr)
        self.assertIn("Saved raw payload JSON to C:/tmp/MFD-1234-raw.json", normalized_stderr)
        raw_mock.assert_called_once()
        json_mock.assert_called_once()

    def test_main_fetch_relative_save_normalized_to_resolves_under_runtime_output_dir(self) -> None:
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

        expected_path = Path("C:/runtime/jira-output/MFD-1234-normalized.json")

        with patch("pathlib.Path.mkdir"):
            with patch("jira_context_harness.cli.NORMALIZED_OUTPUT_DIR", Path("C:/runtime/jira-output")):
                with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
                    load_settings_mock.return_value = JiraSettings(
                        base_url="https://example.atlassian.net",
                        user_email="user@example.com",
                        password="password",
                        api_token="token",
                        project_scope="MFD",
                    )
                    with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                        jira_client_mock.return_value.fetch_issue.return_value = result
                        with patch(
                            "jira_context_harness.cli._write_json_file",
                            return_value=expected_path,
                        ) as json_mock:
                            stdout = io.StringIO()
                            stderr = io.StringIO()
                            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                                exit_code = main([
                                    "fetch",
                                    "test-case",
                                    "MFD-1234",
                                    "--save-normalized-to",
                                    "MFD-1234-normalized.json",
                                ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(json_mock.call_args.args[0], expected_path)
        self.assertIn(
            "Saved normalized output to C:/runtime/jira-output/MFD-1234-normalized.json",
            stderr.getvalue().replace("\\", "/"),
        )

    def test_main_fetch_absolute_save_paths_are_preserved_exactly(self) -> None:
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

        normalized_path = Path("C:/tmp/MFD-1234-normalized.json")
        raw_path = Path("C:/tmp/MFD-1234-raw.json")

        with patch("pathlib.Path.mkdir"):
            with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
                load_settings_mock.return_value = JiraSettings(
                    base_url="https://example.atlassian.net",
                    user_email="user@example.com",
                    password="password",
                    api_token="token",
                    project_scope="MFD",
                )
                with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                    jira_client_mock.return_value.fetch_issue.return_value = result
                    with patch(
                        "jira_context_harness.cli._write_raw_payload_artifact",
                        return_value=raw_path,
                    ) as raw_mock:
                        with patch(
                            "jira_context_harness.cli._write_json_file",
                            return_value=normalized_path,
                        ) as json_mock:
                            stdout = io.StringIO()
                            stderr = io.StringIO()
                            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                                exit_code = main([
                                    "fetch",
                                    "test-case",
                                    "MFD-1234",
                                    "--save-normalized-to",
                                    "C:/tmp/MFD-1234-normalized.json",
                                    "--save-raw-payload-to",
                                    "C:/tmp/MFD-1234-raw.json",
                                ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json_mock.call_args.args[0], normalized_path)
        self.assertEqual(raw_mock.call_args.kwargs["artifact_path"], raw_path)
        normalized_stderr = stderr.getvalue().replace("\\", "/")
        self.assertIn("Saved normalized output to C:/tmp/MFD-1234-normalized.json", normalized_stderr)
        self.assertIn("Saved raw payload JSON to C:/tmp/MFD-1234-raw.json", normalized_stderr)

    def test_main_save_normalized_to_suppresses_stdout(self) -> None:
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
                password="",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                with patch(
                    "jira_context_harness.cli._write_json_file",
                    return_value=Path("C:/tmp/MFD-1234-normalized.json"),
                ) as json_mock:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main([
                            "fetch",
                            "test-case",
                            "MFD-1234",
                            "--save-normalized-to",
                            "C:/tmp/MFD-1234-normalized.json",
                        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "Saved normalized output to C:/tmp/MFD-1234-normalized.json",
            stderr.getvalue().replace("\\", "/"),
        )
        json_mock.assert_called_once()

    def test_main_search_writes_named_normalized_output_and_suppresses_stdout(self) -> None:
        result = JiraSearchResult(
            query='assignee = "Dustin Marek" ORDER BY updated DESC',
            mode="raw-jql",
            total=1,
            returned=1,
            start_at=0,
            max_results=10,
            order_by="custom-jql",
            issues=[
                JiraSearchIssue(
                    issue_key="MFD-9212",
                    summary="Summary",
                    status="In Progress",
                    issue_type="Problem Report",
                    project_key="MFD",
                    assignee="Dustin Marek",
                    reporter="Delta User",
                    updated="2026-09-11T12:34:56.000+0000",
                    source_url="https://avjira/browse/MFD-9212",
                )
            ],
        )

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="password",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.search_issues.return_value = result
                with patch(
                    "jira_context_harness.cli._write_json_file",
                    return_value=Path("C:/tmp/dustin-marek-search.json"),
                ) as json_mock:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main([
                            "search",
                            "--jql",
                            'assignee = "Dustin Marek" ORDER BY updated DESC',
                            "--save-normalized-to",
                            "C:/tmp/dustin-marek-search.json",
                        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "Saved normalized output to C:/tmp/dustin-marek-search.json",
            stderr.getvalue().replace("\\", "/"),
        )
        request_model = jira_client_mock.return_value.search_issues.call_args.args[0]
        self.assertEqual(request_model.order_by, "custom-jql")
        jira_client_mock.return_value.search_issues.assert_called_once()
        json_mock.assert_called_once()

    def test_main_search_relative_save_normalized_to_resolves_under_runtime_output_dir(self) -> None:
        result = JiraSearchResult(
            query='assignee = "Dustin Marek" ORDER BY updated DESC',
            mode="raw-jql",
            total=1,
            returned=1,
            start_at=0,
            max_results=10,
            order_by="custom-jql",
            issues=[
                JiraSearchIssue(
                    issue_key="MFD-9212",
                    summary="Summary",
                    status="In Progress",
                    issue_type="Problem Report",
                    project_key="MFD",
                    assignee="Dustin Marek",
                    reporter="Delta User",
                    updated="2026-09-11T12:34:56.000+0000",
                    source_url="https://avjira/browse/MFD-9212",
                )
            ],
        )

        expected_path = Path("C:/runtime/jira-output/dustin-marek-search.json")

        with patch("pathlib.Path.mkdir"):
            with patch("jira_context_harness.cli.NORMALIZED_OUTPUT_DIR", Path("C:/runtime/jira-output")):
                with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
                    load_settings_mock.return_value = JiraSettings(
                        base_url="https://example.atlassian.net",
                        user_email="user@example.com",
                        password="password",
                        api_token="token",
                        project_scope="MFD",
                    )
                    with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                        jira_client_mock.return_value.search_issues.return_value = result
                        with patch(
                            "jira_context_harness.cli._write_json_file",
                            return_value=expected_path,
                        ) as json_mock:
                            stdout = io.StringIO()
                            stderr = io.StringIO()
                            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                                exit_code = main([
                                    "search",
                                    "--jql",
                                    'assignee = "Dustin Marek" ORDER BY updated DESC',
                                    "--save-normalized-to",
                                    "dustin-marek-search.json",
                                ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(json_mock.call_args.args[0], expected_path)
        self.assertIn(
            "Saved normalized output to C:/runtime/jira-output/dustin-marek-search.json",
            stderr.getvalue().replace("\\", "/"),
        )

    def test_main_search_person_builds_current_query_and_saves_output(self) -> None:
        result = JiraSearchResult(
            query='assignee = "Dustin Marek" ORDER BY updated DESC',
            mode="current",
            total=1,
            returned=1,
            start_at=0,
            max_results=10,
            issues=[
                JiraSearchIssue(
                    issue_key="MFD-9212",
                    summary="Summary",
                    status="In Progress",
                    issue_type="Problem Report",
                    project_key="MFD",
                    assignee="Dustin Marek",
                    reporter="Delta User",
                    updated="2026-09-11T12:34:56.000+0000",
                    source_url="https://avjira/browse/MFD-9212",
                )
            ],
        )

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="password",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.search_issues.return_value = result
                with patch(
                    "jira_context_harness.cli._write_json_file",
                    return_value=Path("C:/tmp/dustin-marek-current.json"),
                ) as json_mock:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main([
                            "search",
                            "person",
                            "Dustin Marek",
                            "--save-normalized-to",
                            "C:/tmp/dustin-marek-current.json",
                        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "Saved normalized output to C:/tmp/dustin-marek-current.json",
            stderr.getvalue().replace("\\", "/"),
        )
        request_model = jira_client_mock.return_value.search_issues.call_args.args[0]
        self.assertEqual(request_model.mode, "current")
        self.assertEqual(request_model.order_by, "updated")
        self.assertEqual(request_model.jql, 'assignee = "Dustin Marek" ORDER BY updated DESC')
        json_mock.assert_called_once()

    def test_main_search_person_builds_created_order_query(self) -> None:
        result = JiraSearchResult(
            query='assignee = "Dustin Marek" ORDER BY created DESC',
            mode="current",
            total=0,
            returned=0,
            start_at=0,
            max_results=10,
            order_by="created",
            issues=[],
        )

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="password",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.search_issues.return_value = result
                with patch(
                    "jira_context_harness.cli._write_json_file",
                    return_value=Path("C:/tmp/dustin-marek-created.json"),
                ):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main([
                            "search",
                            "person",
                            "Dustin Marek",
                            "--order-by",
                            "created",
                            "--save-normalized-to",
                            "C:/tmp/dustin-marek-created.json",
                        ])

        self.assertEqual(exit_code, 0)
        request_model = jira_client_mock.return_value.search_issues.call_args.args[0]
        self.assertEqual(request_model.order_by, "created")
        self.assertEqual(request_model.jql, 'assignee = "Dustin Marek" ORDER BY created DESC')
        self.assertEqual(stdout.getvalue(), "")

    def test_main_search_person_builds_current_or_history_query(self) -> None:
        result = JiraSearchResult(
            query='assignee = "Dustin Marek" OR assignee WAS "Dustin Marek" ORDER BY updated DESC',
            mode="current-or-history",
            total=0,
            returned=0,
            start_at=0,
            max_results=10,
            issues=[],
        )

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                password="password",
                api_token="token",
                project_scope="MFD",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.search_issues.return_value = result
                with patch(
                    "jira_context_harness.cli._write_json_file",
                    return_value=Path("C:/tmp/dustin-marek-history.json"),
                ):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        exit_code = main([
                            "search",
                            "person",
                            "Dustin Marek",
                            "--mode",
                            "current-or-history",
                            "--save-normalized-to",
                            "C:/tmp/dustin-marek-history.json",
                        ])

        self.assertEqual(exit_code, 0)
        request_model = jira_client_mock.return_value.search_issues.call_args.args[0]
        self.assertEqual(request_model.mode, "current-or-history")
        self.assertEqual(
            request_model.jql,
            'assignee = "Dustin Marek" OR assignee WAS "Dustin Marek" ORDER BY updated DESC',
        )
        self.assertEqual(stdout.getvalue(), "")

    def test_main_search_rejects_mode_without_person(self) -> None:
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as exit_context:
                main([
                    "search",
                    "--jql",
                    'assignee = "Dustin Marek" ORDER BY updated DESC',
                    "--mode",
                    "history",
                    "--save-normalized-to",
                    "C:/tmp/dustin-marek-search.json",
                ])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertIn("--mode is only valid with search person", stderr.getvalue())

    def test_main_search_rejects_order_by_without_person(self) -> None:
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as exit_context:
                main([
                    "search",
                    "--jql",
                    'assignee = "Dustin Marek" ORDER BY updated DESC',
                    "--order-by",
                    "created",
                    "--save-normalized-to",
                    "C:/tmp/dustin-marek-search.json",
                ])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertIn("--order-by is only valid with search person", stderr.getvalue())

    def test_main_save_normalized_to_rejects_raw_view(self) -> None:
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as exit_context:
                main([
                    "fetch",
                    "test-case",
                    "MFD-1234",
                    "--view",
                    "raw",
                    "--save-normalized-to",
                    "C:/tmp/MFD-1234-normalized.json",
                ])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertIn("--save-normalized-to only supports --view normalized", stderr.getvalue())

    def test_main_save_raw_payload_to_rejects_raw_view(self) -> None:
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as exit_context:
                main([
                    "fetch",
                    "test-case",
                    "MFD-1234",
                    "--view",
                    "raw",
                    "--save-raw-payload-to",
                    "C:/tmp/MFD-1234-raw.json",
                ])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertIn("--include-raw-payload cannot be combined with --view raw", stderr.getvalue())

    def test_main_prompts_for_missing_config_and_retries_fetch(self) -> None:
        result = JiraFetchResult(
            issue=JiraIssueContext(
                issue_key="MFD-7754",
                issue_kind="test-case",
                summary="Summary",
                description="Description",
                description_format="plain_text",
                status="Approved",
                issue_type="Test",
                project_key="MFD",
                assignee="User",
                updated="2026-09-10T00:00:00.000+0000",
                source_url="https://example.atlassian.net/browse/MFD-7754",
            ),
            raw_response={"key": "MFD-7754"},
        )

        interactive_input = _InteractiveInput("https://example.atlassian.net\nuser@example.com\nMFD\n")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="",
                user_email="",
                password="",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.cli.save_settings") as save_settings_mock:
                with patch("jira_context_harness.cli.getpass.getpass", return_value="token"):
                    with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                        jira_client_mock.return_value.fetch_issue.return_value = result
                        with patch("sys.stdin", interactive_input), patch(
                            "sys.stdout", stdout
                        ), patch("sys.stderr", stderr):
                            exit_code = main(["fetch", "test-case", "MFD-7754"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"issue_key": "MFD-7754"', stdout.getvalue())
        self.assertIn("Starting first-run setup", stderr.getvalue())
        saved_settings = save_settings_mock.call_args.args[0]
        self.assertEqual(saved_settings.base_url, "https://example.atlassian.net")
        self.assertEqual(saved_settings.user_email, "user@example.com")
        self.assertEqual(saved_settings.password, "")
        self.assertEqual(saved_settings.api_token, "token")
        self.assertEqual(saved_settings.deployment, "server_dc")
        self.assertEqual(saved_settings.auth_mode, "basic")

    def test_configure_updates_saved_settings(self) -> None:
        interactive_input = _InteractiveInput("https://avjira\njulio.fuentes@virgingalactic.com\nMFD\n")
        stderr = io.StringIO()

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://virgingalactic.atlassian.net",
                user_email="julio.fuentes@virgingalactic.com",
                password="",
                api_token="saved-token",
                project_scope="MFD",
                deployment="auto",
                auth_mode="auto",
            )
            with patch("jira_context_harness.cli.save_settings") as save_settings_mock:
                with patch("jira_context_harness.cli.getpass.getpass", return_value="jira-password"):
                    with patch("sys.stdin", interactive_input), patch("sys.stderr", stderr):
                        exit_code = main(["configure"])

        self.assertEqual(exit_code, 0)
        saved_settings = save_settings_mock.call_args.args[0]
        self.assertEqual(saved_settings.base_url, "https://avjira")
        self.assertEqual(saved_settings.deployment, "server_dc")
        self.assertEqual(saved_settings.auth_mode, "basic")
        self.assertEqual(saved_settings.password, "jira-password")
        self.assertEqual(saved_settings.api_token, "")

    def test_configure_advanced_updates_overrides(self) -> None:
        interactive_input = _InteractiveInput(
            "https://example.atlassian.net\nuser@example.com\nMFD\ncloud\nbasic\n"
        )
        stderr = io.StringIO()

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="saved-password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.cli.save_settings") as save_settings_mock:
                with patch("jira_context_harness.cli.getpass.getpass", return_value="cloud-token"):
                    with patch("sys.stdin", interactive_input), patch("sys.stderr", stderr):
                        exit_code = main(["configure", "--advanced"])

        self.assertEqual(exit_code, 0)
        saved_settings = save_settings_mock.call_args.args[0]
        self.assertEqual(saved_settings.deployment, "cloud")
        self.assertEqual(saved_settings.auth_mode, "basic")
        self.assertEqual(saved_settings.password, "")
        self.assertEqual(saved_settings.api_token, "cloud-token")

    def test_main_skips_prompt_when_disabled(self) -> None:
        stderr = io.StringIO()
        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="",
                user_email="",
                password="",
                api_token="",
                project_scope="MFD",
            )
            with patch("sys.stderr", stderr):
                exit_code = main(["fetch", "test-case", "MFD-7754", "--no-config-prompt"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Missing required Jira settings", stderr.getvalue())

    def test_main_emits_ad_hoc_section_for_fetch(self) -> None:
        result = JiraFetchResult(
            issue=JiraIssueContext(
                issue_key="MFD-7754",
                issue_kind="test-case",
                summary="Summary",
                description="Description",
                description_format="plain_text",
                status="Approved",
                issue_type="Test Case",
                project_key="MFD",
                assignee="User",
                updated="2026-09-10T00:00:00.000+0000",
                source_url="https://avjira/browse/MFD-7754",
                test_management={
                    "ad_hoc_test_runs": [{"test_run_id": 10721, "status": "Failed"}],
                },
            ),
            raw_response={"key": "MFD-7754"},
            supplemental_responses={"ad_hoc_test_runs": [{"ID": 10721, "status": "Failed"}]},
        )

        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    exit_code = main([
                        "fetch",
                        "test-case",
                        "MFD-7754",
                        "--section",
                        "ad-hoc-runs",
                    ])

        self.assertEqual(exit_code, 0)
        self.assertIn('"test_run_id": 10721', stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_main_emits_field_discovery_report(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.discover_issue_fields.return_value.to_dict.return_value = {
                    "report": {"issue_key": "MFD-7754", "interesting_field_count": 3}
                }
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    exit_code = main(["discover-fields", "MFD-7754"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"issue_key": "MFD-7754"', stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_main_emits_synapse_probe_report(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.probe_synapse_test_case.return_value = [
                    JiraAuthProbeAttempt(
                        api_path="https://avjira/rest/synapse/latest/public/testCase/MFD-7754/steps",
                        auth_mode="basic",
                        ok=True,
                        status_code=200,
                        detail="ok",
                        payload={"steps": [{"id": 1}]},
                    )
                ]
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    exit_code = main(["probe-synapse", "MFD-7754"])

        self.assertEqual(exit_code, 0)
        self.assertIn("synapse/latest/public", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_main_emits_issue_page_inspection_report(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("jira_context_harness.cli.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.cli.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.inspect_issue_page.return_value.to_dict.return_value = {
                    "issue_key": "MFD-7754",
                    "clue_count": 2,
                }
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    exit_code = main(["inspect-page", "MFD-7754"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"issue_key": "MFD-7754"', stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

class LauncherSupportTests(unittest.TestCase):
    def test_cli_main_imports_from_package_surface(self) -> None:
        from jira_context_harness import cli

        self.assertTrue(callable(cli.main))


if __name__ == "__main__":
    unittest.main()