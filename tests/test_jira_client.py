"""Focused tests for Jira Cloud issue retrieval behavior."""

from __future__ import annotations

import io
import json
import unittest

from jira_context_harness.config import JiraSettings
from jira_context_harness.jira_client import FetchRequest, JiraClient, JiraConfigurationError


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._buffer = io.StringIO(json.dumps(payload))

    def __enter__(self) -> io.StringIO:
        return self._buffer

    def __exit__(self, exc_type, exc, tb) -> None:
        self._buffer.close()


class JiraClientTests(unittest.TestCase):
    def test_fetch_issue_requires_settings(self) -> None:
        client = JiraClient(
            JiraSettings(base_url="", user_email="", api_token="", project_scope="MFD")
        )

        with self.assertRaises(JiraConfigurationError):
            client.fetch_issue(FetchRequest(issue_kind="test-case", issue_key="MFD-1234"))

    def test_fetch_issue_normalizes_adf_and_links(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["authorization"] = req.get_header("Authorization")
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "key": "MFD-1234",
                    "fields": {
                        "summary": "HSI wind test case",
                        "description": {
                            "type": "doc",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "Verify wind display."}
                                    ],
                                }
                            ],
                        },
                        "status": {"name": "Approved"},
                        "issuetype": {"name": "Test"},
                        "project": {"key": "MFD"},
                        "assignee": {"displayName": "Delta User"},
                        "updated": "2026-09-10T00:00:00.000+0000",
                        "customfield_10000": "custom value",
                        "issuelinks": [
                            {
                                "type": {"outward": "tests", "inward": "is tested by"},
                                "outwardIssue": {
                                    "key": "DMFDREQ-42",
                                    "fields": {"summary": "Requirement summary"},
                                },
                            }
                        ],
                    },
                }
            )

        client = JiraClient(
            JiraSettings(
                base_url="https://example.atlassian.net",
                user_email="user@example.com",
                api_token="token",
                project_scope="MFD",
            ),
            urlopen=fake_urlopen,
        )

        result = client.fetch_issue(
            FetchRequest(
                issue_kind="test-case",
                issue_key="MFD-1234",
                fields=["summary", "description", "issuelinks"],
            )
        )

        self.assertEqual(result.issue.issue_key, "MFD-1234")
        self.assertEqual(result.issue.description_format, "adf")
        self.assertIn("Verify wind display.", result.issue.description)
        self.assertEqual(result.issue.links[0].issue_key, "DMFDREQ-42")
        self.assertIn("fields=summary%2Cdescription%2Cissuelinks", str(captured["url"]))
        self.assertEqual(captured["timeout"], 30)
        self.assertTrue(str(captured["authorization"]).startswith("Basic "))


if __name__ == "__main__":
    unittest.main()