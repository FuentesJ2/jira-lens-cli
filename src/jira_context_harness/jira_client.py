"""Jira REST client for issue retrieval."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import html as html_lib
import json
import re
from typing import Any, Callable, Dict, Optional, Sequence
from urllib import error, parse, request

from jira_context_harness.config import JiraSettings
from jira_context_harness.models import (
    JiraComment,
    JiraFetchResult,
    JiraFieldDiscoveryEntry,
    JiraFieldDiscoveryReport,
    JiraFieldDiscoveryResult,
    JiraIssueContext,
    JiraLink,
    JiraHtmlClue,
    JiraIssuePageInspectionResult,
)


DEFAULT_TIMEOUT_SECONDS = 30


class JiraHarnessError(Exception):
    """Base error for the Jira context harness."""


class JiraConfigurationError(JiraHarnessError):
    """Raised when required Jira settings are missing."""


class JiraClientError(JiraHarnessError):
    """Raised when the Jira API request fails or returns invalid data."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FetchRequest:
    issue_kind: str
    issue_key: str
    fields: Optional[Sequence[str]] = None
    expand: Optional[Sequence[str]] = None
    properties: Optional[Sequence[str]] = None
    fields_by_keys: bool = False
    fail_fast: bool = True


@dataclass
class JiraAuthProbeAttempt:
    api_path: str
    auth_mode: str
    ok: bool
    status_code: Optional[int] = None
    detail: str = ""
    response_headers: Optional[Dict[str, str]] = None
    payload: Optional[Dict[str, Any]] = None


class JiraClient:
    def __init__(
        self,
        settings: JiraSettings,
        *,
        urlopen: Callable[..., Any] = request.urlopen,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._urlopen = urlopen
        self._timeout_seconds = timeout_seconds

    def fetch_issue(self, request_model: FetchRequest) -> JiraFetchResult:
        missing = self._settings.missing_required()
        if missing:
            raise JiraConfigurationError(
                "Missing required Jira settings: " + ", ".join(missing)
            )

        response_payload = _sanitize_payload(self._perform_issue_get(request_model))
        normalized_issue = self._normalize_issue(response_payload, request_model)
        supplemental_responses: dict[str, Any] = {}
        if request_model.issue_kind == "test-case" and _should_fetch_test_management_context(self._settings):
            test_management, supplemental_responses = self._fetch_test_management_context(
                normalized_issue.issue_key
            )
            normalized_issue.test_management = test_management
        return JiraFetchResult(
            issue=normalized_issue,
            raw_response=response_payload,
            supplemental_responses=supplemental_responses,
        )

    def probe_auth(self) -> list[JiraAuthProbeAttempt]:
        missing = self._settings.missing_required()
        if missing:
            raise JiraConfigurationError(
                "Missing required Jira settings: " + ", ".join(missing)
            )

        attempts: list[JiraAuthProbeAttempt] = []
        base_url = self._settings.base_url.rstrip("/")
        for api_path in _candidate_api_paths(self._settings):
            url = f"{base_url}{api_path}/myself"
            for auth_mode in _candidate_auth_modes(self._settings):
                api_request = request.Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": self._build_authorization_header(auth_mode),
                        "User-Agent": "jira-context-harness/0.1.0",
                    },
                    method="GET",
                )
                try:
                    with self._urlopen(api_request, timeout=self._timeout_seconds) as response:
                        payload = json.load(response)
                    attempts.append(
                        JiraAuthProbeAttempt(
                            api_path=api_path,
                            auth_mode=auth_mode,
                            ok=True,
                            status_code=200,
                            detail="Authentication succeeded",
                            payload=_sanitize_payload(payload) if isinstance(payload, dict) else None,
                        )
                    )
                except error.HTTPError as exc:
                    detail, response_headers = self._extract_http_error_detail(exc)
                    attempts.append(
                        JiraAuthProbeAttempt(
                            api_path=api_path,
                            auth_mode=auth_mode,
                            ok=False,
                            status_code=exc.code,
                            detail=detail,
                            response_headers=response_headers,
                        )
                    )
                except error.URLError as exc:
                    attempts.append(
                        JiraAuthProbeAttempt(
                            api_path=api_path,
                            auth_mode=auth_mode,
                            ok=False,
                            detail=f"Request failed: {exc.reason}",
                        )
                    )
        return attempts

    def discover_issue_fields(self, issue_key: str) -> JiraFieldDiscoveryResult:
        missing = self._settings.missing_required()
        if missing:
            raise JiraConfigurationError(
                "Missing required Jira settings: " + ", ".join(missing)
            )

        response_payload = _sanitize_payload(self._perform_issue_get(
            FetchRequest(
                issue_kind="field-discovery",
                issue_key=issue_key,
                fields=["*all"],
                expand=["names", "schema"],
            )
        ))

        fields = response_payload.get("fields")
        names = response_payload.get("names")
        schema = response_payload.get("schema")
        if not isinstance(fields, dict):
            fields = {}
        if not isinstance(names, dict):
            names = {}
        if not isinstance(schema, dict):
            schema = {}

        entries: list[JiraFieldDiscoveryEntry] = []
        for field_id in sorted(set(fields) | set(names) | set(schema)):
            field_value = fields.get(field_id)
            field_schema = schema.get(field_id) if isinstance(schema.get(field_id), dict) else {}
            entries.append(
                JiraFieldDiscoveryEntry(
                    field_id=field_id,
                    field_name=_string_value(names.get(field_id)) or field_id,
                    has_value=_has_meaningful_value(field_value),
                    value_kind=_value_kind(field_value),
                    schema_type=_string_value(field_schema.get("type")),
                    schema_items=_string_value(field_schema.get("items")),
                    schema_system=_string_value(field_schema.get("system")),
                    schema_custom=_string_value(field_schema.get("custom")),
                    sample_preview=_preview_value(field_value),
                )
            )

        present_fields = [entry for entry in entries if entry.has_value]
        interesting_fields = [entry for entry in present_fields if _is_interesting_field(entry)]
        report = JiraFieldDiscoveryReport(
            issue_key=_string_value(response_payload.get("key")) or issue_key,
            issue_type=_nested_name(fields.get("issuetype")),
            project_key=_nested_key(fields.get("project")),
            present_field_count=len(present_fields),
            interesting_field_count=len(interesting_fields),
            interesting_fields=interesting_fields,
            present_fields=present_fields,
        )
        return JiraFieldDiscoveryResult(report=report, raw_response=response_payload)

    def probe_synapse_test_case(self, issue_key: str) -> list[JiraAuthProbeAttempt]:
        missing = self._settings.missing_required()
        if missing:
            raise JiraConfigurationError(
                "Missing required Jira settings: " + ", ".join(missing)
            )

        base_url = self._settings.base_url.rstrip("/")
        encoded_key = parse.quote(issue_key, safe="")
        candidate_urls = [
            f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/steps",
            f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/linkedRequirements",
            f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/linkedTestSuites",
            f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/linkedTestPlans",
            f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/automationReference",
            f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/getDefects",
            f"{base_url}/rest/synapse/latest/public/testRun/adhoc/getTestRuns/{encoded_key}",
        ]

        attempts: list[JiraAuthProbeAttempt] = []
        for candidate_url in candidate_urls:
            api_request = request.Request(
                candidate_url,
                headers={
                    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                    "Authorization": self._build_authorization_header("basic"),
                    "User-Agent": "jira-context-harness/0.1.0",
                },
                method="GET",
            )
            try:
                with self._urlopen(api_request, timeout=self._timeout_seconds) as response:
                    content_type = _response_header(response, "Content-Type")
                    body = _read_response_body(response)
                    payload = _parse_probe_payload(body, content_type)
                attempts.append(
                    JiraAuthProbeAttempt(
                        api_path=candidate_url,
                        auth_mode="basic",
                        ok=True,
                        status_code=200,
                        detail=f"Synapse probe succeeded with content type {content_type or 'unknown'}",
                        payload=_sanitize_payload(payload),
                    )
                )
            except error.HTTPError as exc:
                detail, response_headers = self._extract_http_error_detail(exc)
                attempts.append(
                    JiraAuthProbeAttempt(
                        api_path=candidate_url,
                        auth_mode="basic",
                        ok=False,
                        status_code=exc.code,
                        detail=detail,
                        response_headers=response_headers,
                    )
                )
            except error.URLError as exc:
                attempts.append(
                    JiraAuthProbeAttempt(
                        api_path=candidate_url,
                        auth_mode="basic",
                        ok=False,
                        detail=f"Request failed: {exc.reason}",
                    )
                )
        return attempts

    def inspect_issue_page(self, issue_key: str) -> JiraIssuePageInspectionResult:
        missing = self._settings.missing_required()
        if missing:
            raise JiraConfigurationError(
                "Missing required Jira settings: " + ", ".join(missing)
            )

        base_url = self._settings.base_url.rstrip("/")
        source_url = f"{base_url}/browse/{parse.quote(issue_key, safe='')}"
        api_request = request.Request(
            source_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Authorization": self._build_authorization_header("basic"),
                "User-Agent": "jira-context-harness/0.1.0",
            },
            method="GET",
        )

        try:
            with self._urlopen(api_request, timeout=self._timeout_seconds) as response:
                html = _read_response_body(response)
        except error.HTTPError as exc:
            detail, _response_headers = self._extract_http_error_detail(exc)
            raise JiraClientError(
                f"Issue page request failed with HTTP {exc.code}: {detail}",
                status_code=exc.code,
            ) from exc
        except error.URLError as exc:
            raise JiraClientError(f"Issue page request failed: {exc.reason}") from exc

        clues = _extract_html_clues(html)
        return JiraIssuePageInspectionResult(
            issue_key=issue_key,
            source_url=source_url,
            html_length=len(html),
            clue_count=len(clues),
            clues=clues,
            raw_html_preview=html[:4000],
            raw_html=html,
        )

    def _fetch_test_management_context(
        self,
        issue_key: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        encoded_key = parse.quote(issue_key, safe="")
        base_url = self._settings.base_url.rstrip("/")
        resources = [
            (
                "test_steps",
                f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/steps",
            ),
            (
                "linked_requirements",
                f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/linkedRequirements",
            ),
            (
                "linked_test_suites",
                f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/linkedTestSuites",
            ),
            (
                "linked_test_plans",
                f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/linkedTestPlans",
            ),
            (
                "automation_reference",
                f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/automationReference",
            ),
            (
                "defects",
                f"{base_url}/rest/synapse/latest/public/testCase/{encoded_key}/getDefects",
            ),
            (
                "ad_hoc_test_runs",
                f"{base_url}/rest/synapse/latest/public/testRun/adhoc/getTestRuns/{encoded_key}",
            ),
        ]

        test_management: dict[str, Any] = {}
        supplemental_responses: dict[str, Any] = {}
        for key, url in resources:
            try:
                payload = self._perform_json_get(url)
            except JiraClientError as exc:
                supplemental_responses[key] = {
                    "error": str(exc),
                    "status_code": exc.status_code,
                }
                continue

            sanitized_payload = _sanitize_payload(payload)
            supplemental_responses[key] = sanitized_payload
            test_management[key] = _normalize_test_management_payload(key, sanitized_payload)

        return test_management, supplemental_responses

    def _perform_issue_get(self, request_model: FetchRequest) -> dict[str, Any]:
        errors: list[str] = []
        last_status_code: Optional[int] = None

        for url, auth_mode, api_path in self._iter_request_candidates(request_model):
            api_request = request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": self._build_authorization_header(auth_mode),
                    "User-Agent": "jira-context-harness/0.1.0",
                },
                method="GET",
            )

            try:
                with self._urlopen(api_request, timeout=self._timeout_seconds) as response:
                    payload = json.load(response)
            except error.HTTPError as exc:
                detail, _response_headers = self._extract_http_error_detail(exc)
                last_status_code = exc.code
                errors.append(f"{api_path} with {auth_mode} auth -> HTTP {exc.code}: {detail}")
                continue
            except error.URLError as exc:
                raise JiraClientError(f"Jira API request failed: {exc.reason}") from exc
            except json.JSONDecodeError as exc:
                raise JiraClientError("Jira API returned invalid JSON") from exc

            if not isinstance(payload, dict):
                raise JiraClientError("Jira API returned a non-object JSON payload")
            return payload

        if errors:
            raise JiraClientError(
                "Jira API request failed after trying multiple Jira API variants: "
                + " | ".join(errors),
                status_code=last_status_code,
            )
        raise JiraClientError("Jira API request failed before any request candidates were built")

    def _perform_json_get(self, url: str) -> Any:
        api_request = request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": self._build_authorization_header("basic"),
                "User-Agent": "jira-context-harness/0.1.0",
            },
            method="GET",
        )

        try:
            with self._urlopen(api_request, timeout=self._timeout_seconds) as response:
                return json.load(response)
        except error.HTTPError as exc:
            detail, _response_headers = self._extract_http_error_detail(exc)
            raise JiraClientError(
                f"Supplemental Jira request failed with HTTP {exc.code}: {detail}",
                status_code=exc.code,
            ) from exc
        except error.URLError as exc:
            raise JiraClientError(f"Supplemental Jira request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise JiraClientError("Supplemental Jira request returned invalid JSON") from exc

    def _iter_request_candidates(
        self,
        request_model: FetchRequest,
    ) -> list[tuple[str, str, str]]:
        encoded_key = parse.quote(request_model.issue_key, safe="")
        base_url = self._settings.base_url.rstrip("/")
        query_params = self._query_params_for_request(request_model)

        candidates: list[tuple[str, str, str]] = []
        for api_path in _candidate_api_paths(self._settings):
            url = f"{base_url}{api_path}/issue/{encoded_key}"
            if query_params:
                url = f"{url}?{parse.urlencode(query_params)}"
            for auth_mode in _candidate_auth_modes(self._settings):
                candidates.append((url, auth_mode, api_path))
        return candidates

    def _query_params_for_request(self, request_model: FetchRequest) -> dict[str, str]:
        query_params: dict[str, str] = {}
        if request_model.fields:
            query_params["fields"] = ",".join(request_model.fields)
        if request_model.expand:
            query_params["expand"] = ",".join(request_model.expand)
        if request_model.properties:
            query_params["properties"] = ",".join(request_model.properties)
        if request_model.fields_by_keys:
            query_params["fieldsByKeys"] = "true"
        if not request_model.fail_fast:
            query_params["failFast"] = "false"
        return query_params

    def _build_authorization_header(self, auth_mode: str) -> str:
        if auth_mode == "bearer":
            return f"Bearer {self._settings.api_token}"

        auth_token = base64.b64encode(
            f"{self._settings.user_email}:{self._basic_auth_secret()}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {auth_token}"

    def _basic_auth_secret(self) -> str:
        if self._settings.password:
            return self._settings.password
        return self._settings.api_token

    def _normalize_issue(
        self,
        response_payload: dict[str, Any],
        request_model: FetchRequest,
    ) -> JiraIssueContext:
        fields = response_payload.get("fields")
        if not isinstance(fields, dict):
            fields = {}

        description_value = fields.get("description")
        description_text, description_format = _extract_description(description_value)
        source_key = _string_value(response_payload.get("key")) or request_model.issue_key

        return JiraIssueContext(
            issue_key=source_key,
            issue_kind=request_model.issue_kind,
            summary=_string_value(fields.get("summary")),
            description=description_text,
            description_format=description_format,
            status=_nested_name(fields.get("status")),
            issue_type=_nested_name(fields.get("issuetype")),
            project_key=_nested_key(fields.get("project")),
            assignee=_assignee_name(fields.get("assignee")),
            updated=_string_value(fields.get("updated")),
            source_url=f"{self._settings.base_url.rstrip('/')}/browse/{source_key}",
            priority=_nested_name(fields.get("priority")),
            resolution=_resolution_name(fields.get("resolution")),
            labels=_extract_string_list(fields.get("labels")),
            components=_extract_component_names(fields.get("components")),
            custom_fields=_extract_custom_fields(fields),
            links=_extract_links(fields.get("issuelinks")),
            comments=_extract_comments(fields.get("comment")),
        )

    def _extract_http_error_detail(self, exc: error.HTTPError) -> tuple[str, dict[str, str]]:
        response_headers = _interesting_headers(exc)
        try:
            payload = json.load(exc)
        except Exception:
            detail = exc.reason or "no additional detail"
            if response_headers:
                detail = detail + f"; headers={response_headers}"
            return detail, response_headers

        if isinstance(payload, dict):
            messages: list[str] = []
            error_messages = payload.get("errorMessages")
            if isinstance(error_messages, list):
                messages.extend(str(message) for message in error_messages)
            errors = payload.get("errors")
            if isinstance(errors, dict):
                messages.extend(f"{key}: {value}" for key, value in errors.items())
            if messages:
                detail = "; ".join(messages)
                if response_headers:
                    detail = detail + f"; headers={response_headers}"
                return detail, response_headers

        detail = exc.reason or "no additional detail"
        if response_headers:
            detail = detail + f"; headers={response_headers}"
        return detail, response_headers


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "avatarUrls":
                continue
            sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


def _extract_description(value: Any) -> tuple[str, str]:
    if isinstance(value, str):
        return value, "plain_text"
    if isinstance(value, dict):
        extracted = _flatten_adf_text(value)
        return extracted, "adf"
    if value is None:
        return "", "missing"
    return str(value), type(value).__name__


def _flatten_adf_text(node: Any) -> str:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "text":
            return _string_value(node.get("text"))
        parts = [_flatten_adf_text(child) for child in node.get("content", [])]
        text = "".join(part for part in parts if part)
        if node_type in {"paragraph", "heading", "listItem"} and text:
            return text + "\n"
        return text
    if isinstance(node, list):
        return "".join(_flatten_adf_text(child) for child in node)
    return ""


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _nested_name(value: Any) -> str:
    if isinstance(value, dict):
        return _string_value(value.get("name"))
    return ""


def _nested_key(value: Any) -> str:
    if isinstance(value, dict):
        return _string_value(value.get("key"))
    return ""


def _assignee_name(value: Any) -> str:
    if isinstance(value, dict):
        return _string_value(value.get("displayName") or value.get("accountId"))
    return ""


def _resolution_name(value: Any) -> str:
    if isinstance(value, dict):
        return _string_value(value.get("name"))
    return _string_value(value)


def _extract_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_string_value(item) for item in value if _string_value(item)]


def _extract_component_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = _string_value(item.get("name"))
            if name:
                names.append(name)
            continue
        name = _string_value(item)
        if name:
            names.append(name)
    return names


def _extract_custom_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in fields.items()
        if key.startswith("customfield_") and value is not None
    }


def _extract_links(value: Any) -> list[JiraLink]:
    if not isinstance(value, list):
        return []

    links: list[JiraLink] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        link_type = item.get("type") if isinstance(item.get("type"), dict) else {}
        outward_issue = item.get("outwardIssue")
        inward_issue = item.get("inwardIssue")

        if isinstance(outward_issue, dict):
            outward_fields = outward_issue.get("fields")
            summary = ""
            issue_type = ""
            status = ""
            priority = ""
            if isinstance(outward_fields, dict):
                summary = _string_value(outward_fields.get("summary"))
                issue_type = _nested_name(outward_fields.get("issuetype"))
                status = _nested_name(outward_fields.get("status"))
                priority = _nested_name(outward_fields.get("priority"))
            links.append(
                JiraLink(
                    direction="outward",
                    relationship=_string_value(
                        link_type.get("outward") or link_type.get("name")
                    ),
                    issue_key=_string_value(outward_issue.get("key")),
                    summary=summary,
                    issue_kind=_semantic_issue_kind(issue_type),
                    issue_type=issue_type,
                    status=status,
                    priority=priority,
                )
            )

        if isinstance(inward_issue, dict):
            inward_fields = inward_issue.get("fields")
            summary = ""
            issue_type = ""
            status = ""
            priority = ""
            if isinstance(inward_fields, dict):
                summary = _string_value(inward_fields.get("summary"))
                issue_type = _nested_name(inward_fields.get("issuetype"))
                status = _nested_name(inward_fields.get("status"))
                priority = _nested_name(inward_fields.get("priority"))
            links.append(
                JiraLink(
                    direction="inward",
                    relationship=_string_value(
                        link_type.get("inward") or link_type.get("name")
                    ),
                    issue_key=_string_value(inward_issue.get("key")),
                    summary=summary,
                    issue_kind=_semantic_issue_kind(issue_type),
                    issue_type=issue_type,
                    status=status,
                    priority=priority,
                )
            )

    return links


def _extract_comments(value: Any) -> list[JiraComment]:
    if not isinstance(value, dict):
        return []

    comments_value = value.get("comments")
    if not isinstance(comments_value, list):
        return []

    comments: list[JiraComment] = []
    for item in comments_value:
        if not isinstance(item, dict):
            continue
        author_value = item.get("author") if isinstance(item.get("author"), dict) else {}
        body_text, body_format = _extract_description(item.get("body"))
        comments.append(
            JiraComment(
                comment_id=_string_value(item.get("id")),
                author=_string_value(
                    author_value.get("displayName")
                    or author_value.get("name")
                    or author_value.get("accountId")
                ),
                author_key=_string_value(
                    author_value.get("name")
                    or author_value.get("key")
                    or author_value.get("accountId")
                ),
                created=_string_value(item.get("created")),
                updated=_string_value(item.get("updated")),
                body=body_text,
                body_format=body_format,
            )
        )
    return comments


def _semantic_issue_kind(issue_type: str) -> str:
    normalized = issue_type.strip().lower()
    if not normalized:
        return ""
    return normalized.replace(" ", "-")


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        if not value:
            return "list[empty]"
        return f"list[{type(value[0]).__name__}]"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _preview_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        compact = " ".join(value.split())
        return compact[:240]
    if isinstance(value, list):
        preview_items = [_preview_value(item) for item in value[:3]]
        return {
            "count": len(value),
            "items": preview_items,
        }
    if isinstance(value, dict):
        preview: dict[str, Any] = {}
        for key in list(value.keys())[:6]:
            preview[key] = _preview_value(value[key])
        preview["..."] = f"{len(value)} keys" if len(value) > 6 else f"{len(value)} keys"
        return preview
    return value


def _is_interesting_field(entry: JiraFieldDiscoveryEntry) -> bool:
    haystack = f"{entry.field_id} {entry.field_name}".lower()
    keywords = [
        "step",
        "require",
        "attachment",
        "attach",
        "suite",
        "plan",
        "verify",
        "verification",
        "vehicle",
        "label",
        "component",
        "version",
        "link",
        "defect",
        "reporter",
        "resolution",
    ]
    return any(keyword in haystack for keyword in keywords)


def _candidate_api_paths(settings: JiraSettings) -> list[str]:
    deployment = settings.deployment.strip().lower() or "auto"
    if deployment == "cloud":
        return ["/rest/api/3", "/rest/api/2"]
    if deployment in {"server", "server_dc", "data_center", "datacenter"}:
        return ["/rest/api/2", "/rest/api/latest"]
    if settings.base_url.rstrip("/").lower().endswith(".atlassian.net"):
        return ["/rest/api/3", "/rest/api/2"]
    return ["/rest/api/2", "/rest/api/latest", "/rest/api/3"]


def _candidate_auth_modes(settings: JiraSettings) -> list[str]:
    auth_mode = settings.auth_mode.strip().lower() or "auto"
    if auth_mode in {"basic", "bearer"}:
        return [auth_mode]
    if settings.base_url.rstrip("/").lower().endswith(".atlassian.net"):
        return ["basic"]
    return ["basic", "bearer"]


def _should_fetch_test_management_context(settings: JiraSettings) -> bool:
    deployment = settings.deployment.strip().lower()
    if deployment == "cloud":
        return False
    return not settings.base_url.rstrip("/").lower().endswith(".atlassian.net")


def _normalize_test_management_payload(key: str, payload: Any) -> Any:
    if key == "test_steps" and isinstance(payload, list):
        return [
            _normalize_test_step(step)
            for step in payload
            if isinstance(step, dict)
        ]
    if key == "linked_requirements" and isinstance(payload, list):
        return [
            _normalize_linked_issue(issue)
            for issue in payload
            if isinstance(issue, dict)
        ]
    if key == "linked_test_suites" and isinstance(payload, dict):
        suites = payload.get("testSuites")
        if isinstance(suites, list):
            return [
                {"name": _string_value(suite)}
                for suite in suites
                if _string_value(suite)
            ]
    if key == "linked_test_plans" and isinstance(payload, dict):
        plans = payload.get("testPlans")
        if isinstance(plans, list):
            return [
                _normalize_test_plan(plan)
                for plan in plans
                if isinstance(plan, dict)
            ]
    if key == "automation_reference" and isinstance(payload, dict):
        return {
            "project_key": _string_value(payload.get("projectKey")),
            "summary": _string_value(payload.get("summary")),
        }
    if key == "defects" and isinstance(payload, list):
        return [
            _normalize_linked_issue(issue)
            for issue in payload
            if isinstance(issue, dict)
        ]
    if key == "ad_hoc_test_runs" and isinstance(payload, list):
        return [
            _normalize_test_run(run)
            for run in payload
            if isinstance(run, dict)
        ]
    return payload


def _normalize_test_step(step: dict[str, Any], *, fallback_sequence_number: Optional[int] = None) -> dict[str, Any]:
    embedded_step = _embedded_test_run_step(step)
    step_raw = _first_non_html_value(step.get("stepRaw"), embedded_step.get("stepRaw"), step.get("step"), embedded_step.get("step"))
    expected_result_raw = _first_non_html_value(
        step.get("expectedResultRaw"),
        embedded_step.get("expectedResultRaw"),
        step.get("expectedResult"),
        embedded_step.get("expectedResult"),
    )
    step_data_raw = _first_non_html_value(
        step.get("stepDataRaw"),
        embedded_step.get("stepDataRaw"),
        step.get("stepData"),
        embedded_step.get("stepData"),
    )
    step_html = _first_html_value(step.get("step"), embedded_step.get("step"))
    expected_result_html = _first_html_value(step.get("expectedResult"), embedded_step.get("expectedResult"))
    step_data_html = _first_html_value(step.get("stepData"), embedded_step.get("stepData"))
    actual_result_raw = _first_non_html_value(
        step.get("actualResultRaw"),
        embedded_step.get("actualResultRaw"),
        step.get("actualResult"),
        embedded_step.get("actualResult"),
    )
    actual_result_html = _first_html_value(step.get("actualResult"), embedded_step.get("actualResult"))
    sequence_number = _string_value(step.get("sequenceNumber"))
    if not sequence_number and fallback_sequence_number is not None:
        sequence_number = str(fallback_sequence_number)

    return {
        "step_id": step.get("ID") if step.get("ID") is not None else step.get("id"),
        "step_number": sequence_number,
        "entity_sequence": step.get("entitySequence"),
        "test_case_id": step.get("tcId") if step.get("tcId") is not None else step.get("testCaseId"),
        "status": _string_value(step.get("status")),
        "step_text": _preferred_text(step_raw, step_html),
        "step_raw": step_raw,
        "step_html": step_html,
        "step_data_text": _preferred_text(step_data_raw, step_data_html),
        "step_data_raw": step_data_raw,
        "step_data_html": step_data_html,
        "expected_result_text": _preferred_text(expected_result_raw, expected_result_html),
        "expected_result_raw": expected_result_raw,
        "expected_result_html": expected_result_html,
        "actual_result_text": _preferred_text(actual_result_raw, actual_result_html),
        "actual_result_raw": actual_result_raw,
        "actual_result_html": actual_result_html,
        "requirement_keys": _extract_issue_keys(expected_result_raw),
        "attachments": _normalize_step_attachments(step.get("testRunStepAttachments")),
    }


def _normalize_linked_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": issue.get("id") if issue.get("id") is not None else issue.get("ID"),
        "issue_key": _string_value(issue.get("key") or issue.get("issueKey")),
        "summary": _string_value(issue.get("summary")),
    }


def _normalize_test_plan(plan: dict[str, Any]) -> dict[str, Any]:
    test_cycles = plan.get("testCycles") if isinstance(plan.get("testCycles"), list) else []
    return {
        "issue_key": _string_value(plan.get("testPlanKey")),
        "summary": _string_value(plan.get("testPlanSummary")),
        "test_cycles": [
            {
                "id": cycle.get("testCycleId") if isinstance(cycle, dict) else None,
                "name": _string_value(cycle.get("testCycleName")) if isinstance(cycle, dict) else "",
                "status": _string_value(cycle.get("status")) if isinstance(cycle, dict) else "",
                "notify_tester": cycle.get("notifyTester") if isinstance(cycle, dict) else None,
            }
            for cycle in test_cycles
            if isinstance(cycle, dict)
        ],
    }


def _normalize_test_run(run: dict[str, Any]) -> dict[str, Any]:
    details = run.get("testRunDetails") if isinstance(run.get("testRunDetails"), dict) else {}
    history = details.get("testRunHistory") if isinstance(details.get("testRunHistory"), list) else []
    steps = details.get("testRunSteps") if isinstance(details.get("testRunSteps"), list) else []
    return {
        "test_run_id": run.get("ID") if run.get("ID") is not None else run.get("id"),
        "status": _string_value(run.get("status")),
        "summary": _string_value(run.get("summary")),
        "executed_by": _string_value(run.get("executedBy") or run.get("executedByFromRun")),
        "executed_by_display_name": _string_value(run.get("executedByDisplayName")),
        "execution_on": _string_value(run.get("executionOn")),
        "test_case_id": run.get("testCaseId"),
        "test_case_key": _string_value(run.get("testCaseKey")),
        "test_cycle": {
            "id": run.get("testCycleId"),
            "name": _string_value(run.get("testCycleSummary")),
        },
        "test_plan": {
            "issue_key": _string_value(run.get("testPlanKey")),
            "summary": _string_value(run.get("testPlanSummary")),
        },
        "history": [
            {
                "activity": _string_value(entry.get("activity")),
                "activity_type": _string_value(entry.get("activityType")),
                "execution_on": _string_value(entry.get("executionOn")),
                "execution_time": entry.get("executionTime"),
                "executor_name": _string_value(entry.get("executorName")),
                "executor_full_name": _string_value(entry.get("executorFullName")),
                "test_run_id": entry.get("testRunId"),
            }
            for entry in history
            if isinstance(entry, dict)
        ],
        "steps": [
            _normalize_test_step(step, fallback_sequence_number=index)
            for index, step in enumerate(steps, start=1)
            if isinstance(step, dict)
        ],
    }


def _normalize_step_attachments(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    attachments: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        attachments.append(
            {
                "attachment_id": item.get("ID") if item.get("ID") is not None else item.get("id"),
                "file_name": _string_value(item.get("fileName") or item.get("filename")),
                "file_extension": _string_value(item.get("fileExtension")),
                "mime_type": _string_value(item.get("mimeType")),
            }
        )
    return attachments


def _embedded_test_run_step(step: dict[str, Any]) -> dict[str, Any]:
    attachments = step.get("testRunStepAttachments")
    if not isinstance(attachments, list):
        return {}
    for item in attachments:
        if not isinstance(item, dict):
            continue
        nested_step = item.get("testRunStep")
        if isinstance(nested_step, dict):
            return nested_step
    return {}


def _first_non_html_value(*values: Any) -> str:
    for value in values:
        text = _string_value(value)
        if text and not _looks_like_html(text):
            return text
    return ""


def _first_html_value(*values: Any) -> str:
    for value in values:
        text = _string_value(value)
        if _looks_like_html(text):
            return text
    return ""


def _html_value(value: Any) -> str:
    text = _string_value(value)
    if _looks_like_html(text):
        return text
    return ""


def _preferred_text(raw_text: str, html_text: str) -> str:
    if raw_text and not _looks_like_html(raw_text):
        return raw_text
    if html_text:
        return _html_to_text(html_text)
    return raw_text


def _looks_like_html(value: str) -> bool:
    return bool(value) and ("<" in value and ">" in value)


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    normalized = html_lib.unescape(without_tags)
    return " ".join(normalized.split())


def _extract_issue_keys(value: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", value)
    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        if match in seen:
            continue
        seen.add(match)
        result.append(match)
    return result


def _interesting_headers(exc: error.HTTPError) -> dict[str, str]:
    headers_to_capture = [
        "X-Seraph-LoginReason",
        "WWW-Authenticate",
        "X-AUSERNAME",
        "Content-Type",
    ]
    captured: dict[str, str] = {}
    for header_name in headers_to_capture:
        header_value = exc.headers.get(header_name)
        if header_value:
            captured[header_name] = header_value
    return captured


def _response_header(response: Any, name: str) -> str:
    headers = getattr(response, "headers", None)
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if callable(getter):
        return _string_value(getter(name))
    return ""


def _read_response_body(response: Any) -> str:
    body = response.read()
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return _string_value(body)


def _parse_probe_payload(body: str, content_type: str) -> dict[str, Any]:
    if "json" in content_type.lower():
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {"raw_text": body[:2000]}
        if isinstance(parsed, dict):
            return parsed
        return {"raw_json": parsed}
    return {"raw_text": body[:2000]}


def _extract_html_clues(html: str) -> list[JiraHtmlClue]:
    clues: list[JiraHtmlClue] = []
    clue_patterns = [
        ("synapse", r"https?://[^\"'\s>]*synapse[^\"'\s<]*|/rest/synapse[^\"'\s<]*"),
        ("testray", r"https?://[^\"'\s>]*testray[^\"'\s<]*|testray[^\"'\s<]*"),
        ("test-step", r"Test Step|Expected Result|Forecast|Estimate|XPDR_FLIGHT_ID|Displayed Callsign|Test Setup Description|Requirement Validation Checkboxes"),
        ("test-artifact", r"Test Case|Requirement Suite|Run Status|Execution Count|Test Suite|Requirement"),
        ("issue-links", r"Issue Links|issuelinks|linkingmodule|linkedIssue|linking-panel"),
        ("customfield", r"customfield_[0-9]+"),
        ("wrm-data", r"WRM\._unparsedData\[[^\]]+\]|AJS\.[A-Za-z0-9_$.]+\([^\n<]{0,200}\)"),
        ("ajax", r"/plugins/servlet/[^\"'\s<]*|/rest/[^\"'\s<]*"),
    ]
    seen: set[tuple[str, str]] = set()
    for category, pattern in clue_patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            snippet = _html_snippet(html, match.start(), match.end())
            key = (category, snippet)
            if key in seen:
                continue
            seen.add(key)
            clues.append(JiraHtmlClue(category=category, snippet=snippet))
            if len(clues) >= 50:
                return clues
    return clues


def _html_snippet(html: str, start: int, end: int) -> str:
    window_start = max(0, start - 120)
    window_end = min(len(html), end + 120)
    return " ".join(html[window_start:window_end].split())