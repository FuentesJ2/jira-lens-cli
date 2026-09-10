"""Focused tests for the MCP server fetch helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from jira_context_harness.config import JiraSettings
from jira_context_harness.mcp_server import fetch_issue_tool_payload
from jira_context_harness.models import JiraFetchResult, JiraIssueContext


class McpServerTests(unittest.TestCase):
    def test_fetch_issue_tool_payload_returns_merged_steps_section(self) -> None:
        result = JiraFetchResult(
            issue=JiraIssueContext(
                issue_key="MFD-7754",
                issue_kind="test-case",
                summary="Summary",
                description="Description",
                description_format="plain_text",
                status="Draft",
                issue_type="Test Case",
                project_key="MFD",
                assignee="User",
                updated="2026-09-10T00:00:00.000+0000",
                source_url="https://avjira/browse/MFD-7754",
                test_management={
                    "merged_steps": [{"step_number": "3", "latest_run_status": "Failed"}],
                },
            ),
            raw_response={"key": "MFD-7754"},
            supplemental_responses={
                "test_steps": [{"sequenceNumber": "3"}],
                "ad_hoc_test_runs": [{"ID": 10721}],
            },
        )

        with patch("jira_context_harness.mcp_server.load_settings") as load_settings_mock:
            load_settings_mock.return_value = JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            )
            with patch("jira_context_harness.mcp_server.JiraClient") as jira_client_mock:
                jira_client_mock.return_value.fetch_issue.return_value = result
                payload = fetch_issue_tool_payload(
                    "test-case",
                    "MFD-7754",
                    section="merged-steps",
                    include_raw=True,
                )

        self.assertEqual(payload["normalized"][0]["step_number"], "3")
        self.assertEqual(payload["normalized"][0]["latest_run_status"], "Failed")
        self.assertIn("test_steps", payload["raw_response"])
        self.assertIn("ad_hoc_test_runs", payload["raw_response"])

    def test_requirement_rejects_test_management_section(self) -> None:
        with self.assertRaises(ValueError):
            fetch_issue_tool_payload("requirement", "DMFDREQ-1448", section="merged-steps")