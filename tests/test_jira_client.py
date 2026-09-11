"""Focused tests for Jira Cloud issue retrieval behavior."""

from __future__ import annotations

import io
import json
import unittest

from jira_context_harness.config import JiraSettings
from urllib import error

from jira_context_harness.jira_client import FetchRequest, JiraClient, JiraConfigurationError


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._buffer = io.StringIO(json.dumps(payload))

    def __enter__(self) -> io.StringIO:
        return self._buffer

    def __exit__(self, exc_type, exc, tb) -> None:
        self._buffer.close()


class _FakeBinaryResponse:
    def __init__(self, body: str, *, content_type: str = "application/json") -> None:
        self._buffer = io.BytesIO(body.encode("utf-8"))
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> "_FakeBinaryResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._buffer.close()

    def read(self) -> bytes:
        return self._buffer.read()


class _FakeHttpError(error.HTTPError):
    def __init__(self, url: str, code: int, msg: str, headers: dict[str, str], payload: str) -> None:
        super().__init__(url, code, msg, headers, io.StringIO(payload))


class JiraClientTests(unittest.TestCase):
    def test_fetch_issue_requires_settings(self) -> None:
        client = JiraClient(
            JiraSettings(base_url="", user_email="", password="", api_token="", project_scope="MFD")
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
                        "comment": {
                            "comments": [
                                {
                                    "id": "10001",
                                    "author": {
                                        "displayName": "Delta User",
                                        "name": "delta.user",
                                    },
                                    "created": "2026-09-10T01:00:00.000+0000",
                                    "updated": "2026-09-10T01:05:00.000+0000",
                                    "body": "Comment text",
                                }
                            ]
                        },
                        "customfield_10000": "custom value",
                        "issuelinks": [
                            {
                                "type": {"outward": "tests", "inward": "is tested by"},
                                "outwardIssue": {
                                    "key": "DMFDREQ-42",
                                    "fields": {
                                        "summary": "Requirement summary",
                                        "issuetype": {"name": "Requirement"},
                                        "status": {"name": "Approved"},
                                        "priority": {"name": "Major"},
                                    },
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
                password="",
                api_token="token",
                project_scope="MFD",
            ),
            urlopen=fake_urlopen,
        )

        result = client.fetch_issue(
            FetchRequest(
                issue_kind="test-case",
                issue_key="MFD-1234",
                fields=["summary", "description", "comment", "issuelinks"],
            )
        )

        self.assertEqual(result.issue.issue_key, "MFD-1234")
        self.assertEqual(result.issue.description_format, "adf")
        self.assertIn("Verify wind display.", result.issue.description)
        self.assertEqual(result.issue.links[0].issue_key, "DMFDREQ-42")
        self.assertEqual(result.issue.links[0].issue_kind, "requirement")
        self.assertEqual(result.issue.links[0].status, "Approved")
        self.assertEqual(result.issue.comments[0].author, "Delta User")
        self.assertEqual(result.issue.comments[0].body, "Comment text")
        self.assertNotIn("avatarUrls", json.dumps(result.raw_response))
        self.assertIn("fields=summary%2Cdescription%2Ccomment%2Cissuelinks", str(captured["url"]))
        self.assertEqual(captured["timeout"], 30)
        self.assertTrue(str(captured["authorization"]).startswith("Basic "))

    def test_fetch_issue_uses_server_dc_path_for_internal_host(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["authorization"] = req.get_header("Authorization")
            return _FakeResponse({"key": "MFD-7754", "fields": {}})

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="julio.fuentes@virgingalactic.com",
                password="password",
                api_token="token",
                project_scope="MFD",
            ),
            urlopen=fake_urlopen,
        )

        client.fetch_issue(FetchRequest(issue_kind="test-case", issue_key="MFD-7754"))

        self.assertIn("/rest/api/2/issue/MFD-7754", str(captured["url"]))
        self.assertTrue(str(captured["authorization"]).startswith("Basic "))

    def test_fetch_issue_emits_fields_by_keys_and_fail_fast_query_params(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            return _FakeResponse({"key": "MFD-1234", "fields": {}})

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="julio.fuentes@virgingalactic.com",
                password="password",
                api_token="",
                project_scope="MFD",
            ),
            urlopen=fake_urlopen,
        )

        client.fetch_issue(
            FetchRequest(
                issue_kind="test-case",
                issue_key="MFD-1234",
                fields=["customfield_12345"],
                fields_by_keys=True,
                fail_fast=False,
            )
        )

        self.assertIn("fields=customfield_12345", str(captured["url"]))
        self.assertIn("fieldsByKeys=true", str(captured["url"]))
        self.assertIn("failFast=false", str(captured["url"]))

    def test_fetch_issue_enriches_internal_test_case_with_test_management_context(self) -> None:
        requested_urls: list[str] = []

        def fake_urlopen(req, timeout):
            requested_urls.append(req.full_url)
            if "/rest/api/2/issue/MFD-7754" in req.full_url:
                return _FakeResponse(
                    {
                        "key": "MFD-7754",
                        "fields": {
                            "summary": "DELTA - DIAG XPDR Reported Parameter Callsign Test Case",
                            "description": "Objective text",
                            "status": {"name": "Approved"},
                            "issuetype": {"name": "Test Case"},
                            "project": {"key": "MFD"},
                            "assignee": {"displayName": "Delta User"},
                            "updated": "2026-09-10T00:00:00.000+0000",
                            "issuelinks": [],
                        },
                    }
                )
            if req.full_url.endswith("/rest/synapse/latest/public/testCase/MFD-7754/steps"):
                return _FakeResponse(
                    [
                        {
                            "ID": 7607,
                            "sequenceNumber": "1",
                            "step": "Start test from nominal flight conditions",
                            "expectedResult": "N/A",
                        }
                    ]
                )
            if req.full_url.endswith("/linkedRequirements"):
                return _FakeResponse(
                    [
                        {
                            "id": 81824,
                            "key": "DMFDREQ-1448",
                            "summary": "Requirement summary",
                        }
                    ]
                )
            if req.full_url.endswith("/linkedTestSuites"):
                return _FakeResponse(
                    {
                        "projectKey": "MFD",
                        "summary": "Case summary",
                        "testSuites": ["Delta/DIAG/XPDR"],
                    }
                )
            if req.full_url.endswith("/linkedTestPlans"):
                return _FakeResponse(
                    {
                        "projectKey": "MFD",
                        "summary": "Case summary",
                        "testPlans": [
                            {
                                "testPlanKey": "MFD-10477",
                                "testPlanSummary": "Plan summary",
                            }
                        ],
                    }
                )
            if req.full_url.endswith("/automationReference"):
                return _FakeResponse({"projectKey": "MFD", "summary": "Case summary"})
            if req.full_url.endswith("/getDefects"):
                return _FakeResponse([
                    {"id": 62742, "key": "MFD-8100", "summary": "Bug"}
                ])
            if req.full_url.endswith("/testRun/adhoc/getTestRuns/MFD-7754"):
                return _FakeResponse([
                    {
                        "ID": 10721,
                        "status": "Failed",
                        "testCaseKey": "MFD-7754",
                        "executedBy": "YuJ",
                        "executionOn": "16/Jul/26 9:47 AM",
                        "testCycleId": 3,
                        "testCycleSummary": "Ad hoc",
                        "testRunDetails": {
                            "testRunHistory": [
                                {
                                    "activity": "Failed",
                                    "activityType": "Status",
                                    "executionOn": "16-Jul-2026 09:47:55",
                                    "executionTime": 1784220475927,
                                    "executorName": "YuJ",
                                    "executorFullName": "Jin Yu",
                                    "testRunId": 10721,
                                }
                            ],
                            "testRunSteps": [
                                {
                                    "ID": 144298,
                                    "sequenceNumber": "3",
                                    "status": "Not Tested",
                                    "step": "Set the Flight ID value as specified:",
                                    "expectedResult": "[DMFDREQ-1448]\nDisplayed Callsign",
                                    "actualResult": "<p>!screenshot-1.png|id:3301!</p>",
                                    "testRunStepAttachments": [
                                        {
                                            "ID": 3301,
                                            "fileName": "screenshot-1.png",
                                            "fileExtension": "png",
                                            "mimeType": "image/png",
                                            "testRunStep": {
                                                "step": "<p>Set the Flight ID value as specified:</p>",
                                                "stepRaw": "Set the Flight ID value as specified:",
                                                "expectedResult": "<p>Displayed Callsign</p>",
                                                "expectedResultRaw": "[DMFDREQ-1448]\nDisplayed Callsign",
                                                "actualResult": "<p>!screenshot-1.png|id:3301!</p>",
                                                "actualResultRaw": "!screenshot-1.png|id:3301!",
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ])
            raise AssertionError(f"Unexpected URL {req.full_url}")

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            ),
            urlopen=fake_urlopen,
        )

        result = client.fetch_issue(FetchRequest(issue_kind="test-case", issue_key="MFD-7754"))

        self.assertEqual(result.issue.test_management["test_steps"][0]["step_number"], "1")
        self.assertEqual(
            result.issue.test_management["test_steps"][0]["expected_result_text"],
            "N/A",
        )
        self.assertEqual(
            result.issue.test_management["linked_requirements"][0]["issue_key"],
            "DMFDREQ-1448",
        )
        self.assertEqual(
            result.issue.test_management["linked_test_suites"],
            [{"name": "Delta/DIAG/XPDR"}],
        )
        self.assertEqual(
            result.issue.test_management["linked_test_plans"][0]["issue_key"],
            "MFD-10477",
        )
        self.assertEqual(result.issue.test_management["defects"][0]["issue_key"], "MFD-8100")
        self.assertEqual(result.issue.test_management["ad_hoc_test_runs"][0]["steps"][0]["step_number"], "3")
        self.assertEqual(
            result.issue.test_management["ad_hoc_test_runs"][0]["steps"][0]["requirement_keys"],
            ["DMFDREQ-1448"],
        )
        self.assertEqual(
            result.issue.test_management["ad_hoc_test_runs"][0]["steps"][0]["expected_result_html"],
            "<p>Displayed Callsign</p>",
        )
        self.assertEqual(
            result.issue.test_management["ad_hoc_test_runs"][0]["steps"][0]["attachments"][0]["file_name"],
            "screenshot-1.png",
        )
        self.assertIn("test_steps", result.supplemental_responses)
        self.assertTrue(
            any(url.endswith("/rest/synapse/latest/public/testCase/MFD-7754/steps") for url in requested_urls)
        )

    def test_probe_auth_captures_login_headers(self) -> None:
        def fake_urlopen(req, timeout):
            raise _FakeHttpError(
                req.full_url,
                401,
                "Unauthorized",
                {
                    "X-Seraph-LoginReason": "AUTHENTICATION_FAILED",
                    "WWW-Authenticate": 'Basic realm="JIRA"',
                },
                '{"errorMessages":["Login Required"]}',
            )

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="token",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            ),
            urlopen=fake_urlopen,
        )

        attempts = client.probe_auth()

        self.assertEqual(len(attempts), 2)
        self.assertFalse(attempts[0].ok)
        self.assertEqual(attempts[0].response_headers["X-Seraph-LoginReason"], "AUTHENTICATION_FAILED")
        self.assertIn("Login Required", attempts[0].detail)

    def test_probe_synapse_sanitizes_avatar_urls_from_payloads(self) -> None:
        def fake_urlopen(req, timeout):
            return _FakeBinaryResponse(
                json.dumps(
                    {
                        "author": {
                            "displayName": "Delta User",
                            "avatarUrls": {"16x16": "https://example/avatar.png"},
                        }
                    }
                )
            )

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            ),
            urlopen=fake_urlopen,
        )

        attempts = client.probe_synapse_test_case("MFD-7754")

        self.assertTrue(all("avatarUrls" not in json.dumps(attempt.payload) for attempt in attempts if attempt.payload))

    def test_missing_required_for_server_dc_basic_requires_password(self) -> None:
        settings = JiraSettings(
            base_url="https://avjira",
            user_email="FuentesJ2",
            password="",
            api_token="token",
            project_scope="MFD",
            deployment="server_dc",
            auth_mode="basic",
        )

        self.assertIn("JIRA_PASSWORD", settings.missing_required())

    def test_discover_issue_fields_reports_interesting_fields(self) -> None:
        def fake_urlopen(req, timeout):
            return _FakeResponse(
                {
                    "key": "MFD-7754",
                    "fields": {
                        "summary": "DELTA - DIAG XPDR Reported Parameter Callsign Test Case",
                        "description": "Objective text",
                        "issuetype": {"name": "Test Case"},
                        "project": {"key": "MFD"},
                        "attachment": [{"id": "10", "filename": "steps.png"}],
                        "customfield_10010": "Automated System Test",
                        "customfield_10011": [{"id": "1", "name": "DELTA ... XPDR"}],
                    },
                    "names": {
                        "summary": "Summary",
                        "description": "Description",
                        "attachment": "Attachment",
                        "customfield_10010": "Verification Method",
                        "customfield_10011": "Test Suite",
                    },
                    "schema": {
                        "attachment": {"type": "array", "items": "attachment"},
                        "customfield_10010": {"type": "string", "custom": "com.test:verification"},
                        "customfield_10011": {"type": "array", "items": "option"},
                    },
                }
            )

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            ),
            urlopen=fake_urlopen,
        )

        result = client.discover_issue_fields("MFD-7754")

        self.assertEqual(result.report.issue_key, "MFD-7754")
        self.assertEqual(result.report.project_key, "MFD")
        self.assertEqual(result.report.issue_type, "Test Case")
        field_names = [entry.field_name for entry in result.report.interesting_fields]
        self.assertIn("Attachment", field_names)
        self.assertIn("Verification Method", field_names)
        self.assertIn("Test Suite", field_names)

    def test_probe_synapse_test_case_collects_attempts(self) -> None:
        def fake_urlopen(req, timeout):
            if req.full_url.endswith("/rest/synapse/latest/public/testCase/MFD-7754/steps"):
                return _FakeBinaryResponse('{"steps":[{"id":1,"step":"Start nominal flight"}]}')
            raise _FakeHttpError(
                req.full_url,
                404,
                "Not Found",
                {"Content-Type": "application/json"},
                '{"errorMessages":["Not Found"]}',
            )

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            ),
            urlopen=fake_urlopen,
        )

        attempts = client.probe_synapse_test_case("MFD-7754")

        self.assertTrue(any(attempt.ok for attempt in attempts))
        self.assertTrue(any("steps" in (attempt.payload or {}) for attempt in attempts if attempt.ok))

    def test_inspect_issue_page_finds_synapse_and_step_clues(self) -> None:
        html = """
        <html>
            <body>
                <div>Test Step</div>
                <div>Expected Result</div>
                <div>Issue Links</div>
                <div>customfield_18903</div>
                <script>
                    var api = '/rest/synapse/latest/public/testCase/MFD-7754/steps';
                </script>
            </body>
        </html>
        """

        def fake_urlopen(req, timeout):
            return _FakeBinaryResponse(html, content_type="text/html")

        client = JiraClient(
            JiraSettings(
                base_url="https://avjira",
                user_email="FuentesJ2",
                password="password",
                api_token="",
                project_scope="MFD",
                deployment="server_dc",
                auth_mode="basic",
            ),
            urlopen=fake_urlopen,
        )

        result = client.inspect_issue_page("MFD-7754")

        self.assertEqual(result.issue_key, "MFD-7754")
        self.assertGreater(result.clue_count, 0)
        self.assertIn("customfield_18903", result.raw_html)
        snippets = [clue.snippet for clue in result.clues]
        self.assertTrue(any("synapse" in snippet.lower() for snippet in snippets))
        self.assertTrue(any("Test Step" in snippet for snippet in snippets))
        self.assertTrue(any("Issue Links" in snippet for snippet in snippets))


if __name__ == "__main__":
    unittest.main()