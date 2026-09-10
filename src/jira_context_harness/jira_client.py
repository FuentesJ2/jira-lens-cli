"""JIRA Cloud REST API v3 client for issue retrieval."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from typing import Any, Callable, Sequence
from urllib import error, parse, request

from jira_context_harness.config import JiraSettings
from jira_context_harness.models import JiraFetchResult, JiraIssueContext, JiraLink


DEFAULT_TIMEOUT_SECONDS = 30


class JiraHarnessError(Exception):
    """Base error for the Jira context harness."""


class JiraConfigurationError(JiraHarnessError):
    """Raised when required Jira settings are missing."""


class JiraClientError(JiraHarnessError):
    """Raised when the Jira API request fails or returns invalid data."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FetchRequest:
    issue_kind: str
    issue_key: str
    fields: Sequence[str] | None = None
    expand: Sequence[str] | None = None
    properties: Sequence[str] | None = None
    fields_by_keys: bool = False
    fail_fast: bool = True


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

        response_payload = self._perform_issue_get(request_model)
        normalized_issue = self._normalize_issue(response_payload, request_model)
        return JiraFetchResult(issue=normalized_issue, raw_response=response_payload)

    def _perform_issue_get(self, request_model: FetchRequest) -> dict[str, Any]:
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

        encoded_key = parse.quote(request_model.issue_key, safe="")
        base_url = self._settings.base_url.rstrip("/")
        url = f"{base_url}/rest/api/3/issue/{encoded_key}"
        if query_params:
            url = f"{url}?{parse.urlencode(query_params)}"

        auth_token = base64.b64encode(
            f"{self._settings.user_email}:{self._settings.api_token}".encode("utf-8")
        ).decode("ascii")

        api_request = request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {auth_token}",
                "User-Agent": "jira-context-harness/0.1.0",
            },
            method="GET",
        )

        try:
            with self._urlopen(api_request, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except error.HTTPError as exc:
            detail = self._extract_http_error_detail(exc)
            raise JiraClientError(
                f"Jira API request failed with HTTP {exc.code}: {detail}",
                status_code=exc.code,
            ) from exc
        except error.URLError as exc:
            raise JiraClientError(f"Jira API request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise JiraClientError("Jira API returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise JiraClientError("Jira API returned a non-object JSON payload")
        return payload

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
            custom_fields=_extract_custom_fields(fields),
            links=_extract_links(fields.get("issuelinks")),
        )

    def _extract_http_error_detail(self, exc: error.HTTPError) -> str:
        try:
            payload = json.load(exc)
        except Exception:
            return exc.reason or "no additional detail"

        if isinstance(payload, dict):
            messages: list[str] = []
            error_messages = payload.get("errorMessages")
            if isinstance(error_messages, list):
                messages.extend(str(message) for message in error_messages)
            errors = payload.get("errors")
            if isinstance(errors, dict):
                messages.extend(f"{key}: {value}" for key, value in errors.items())
            if messages:
                return "; ".join(messages)

        return exc.reason or "no additional detail"


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
            if isinstance(outward_fields, dict):
                summary = _string_value(outward_fields.get("summary"))
            links.append(
                JiraLink(
                    direction="outward",
                    relationship=_string_value(
                        link_type.get("outward") or link_type.get("name")
                    ),
                    issue_key=_string_value(outward_issue.get("key")),
                    summary=summary,
                )
            )

        if isinstance(inward_issue, dict):
            inward_fields = inward_issue.get("fields")
            summary = ""
            if isinstance(inward_fields, dict):
                summary = _string_value(inward_fields.get("summary"))
            links.append(
                JiraLink(
                    direction="inward",
                    relationship=_string_value(
                        link_type.get("inward") or link_type.get("name")
                    ),
                    issue_key=_string_value(inward_issue.get("key")),
                    summary=summary,
                )
            )

    return links