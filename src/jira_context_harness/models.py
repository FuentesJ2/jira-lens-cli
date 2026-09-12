"""Core data models for normalized JIRA issue responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class JiraLink:
    direction: str
    relationship: str
    issue_key: str
    summary: str = ""
    issue_kind: str = ""
    issue_type: str = ""
    status: str = ""
    priority: str = ""


@dataclass
class JiraComment:
    comment_id: str
    author: str
    author_key: str
    created: str
    updated: str
    body: str
    body_format: str


@dataclass
class JiraIssueContext:
    issue_key: str
    issue_kind: str
    summary: str
    description: str
    description_format: str
    status: str
    issue_type: str
    project_key: str
    assignee: str
    updated: str
    source_url: str
    custom_fields: dict[str, Any] = field(default_factory=dict)
    links: list[JiraLink] = field(default_factory=list)
    comments: list[JiraComment] = field(default_factory=list)
    test_management: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JiraFetchResult:
    issue: JiraIssueContext
    raw_response: dict[str, Any]
    supplemental_responses: dict[str, Any] = field(default_factory=dict)

    def normalized_dict(self) -> dict[str, Any]:
        return self.issue.to_dict()

    def combined_dict(self) -> dict[str, Any]:
        payload = {
            "normalized": self.normalized_dict(),
            "raw_response": self.raw_response,
        }
        if self.supplemental_responses:
            payload["supplemental_responses"] = self.supplemental_responses
        return payload


@dataclass
class JiraSearchIssue:
    issue_key: str
    summary: str
    status: str
    issue_type: str
    project_key: str
    assignee: str
    reporter: str
    updated: str
    source_url: str
    created: str = ""
    priority: str = ""
    extra_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JiraSearchResult:
    query: str
    mode: str
    total: int
    returned: int
    start_at: int
    max_results: int
    order_by: str = "updated"
    has_more: bool = False
    next_start_at: int | None = None
    requested_fields: list[str] = field(default_factory=list)
    issues: list[JiraSearchIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "total": self.total,
            "returned": self.returned,
            "start_at": self.start_at,
            "max_results": self.max_results,
            "order_by": self.order_by,
            "has_more": self.has_more,
            "next_start_at": self.next_start_at,
            "requested_fields": list(self.requested_fields),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class JiraFieldDiscoveryEntry:
    field_id: str
    field_name: str
    has_value: bool
    value_kind: str
    schema_type: str
    schema_items: str
    schema_system: str
    schema_custom: str
    sample_preview: Any


@dataclass
class JiraFieldDiscoveryReport:
    issue_key: str
    issue_type: str
    project_key: str
    present_field_count: int
    interesting_field_count: int
    interesting_fields: list[JiraFieldDiscoveryEntry] = field(default_factory=list)
    present_fields: list[JiraFieldDiscoveryEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JiraFieldDiscoveryResult:
    report: JiraFieldDiscoveryReport
    raw_response: dict[str, Any]

    def to_dict(self, *, include_raw: bool) -> dict[str, Any]:
        payload = {"report": self.report.to_dict()}
        if include_raw:
            payload["raw_response"] = self.raw_response
        return payload

@dataclass
class JiraHtmlClue:
    category: str
    snippet: str

@dataclass
class JiraIssuePageInspectionResult:
    issue_key: str
    source_url: str
    html_length: int
    clue_count: int
    clues: list[JiraHtmlClue] = field(default_factory=list)
    raw_html_preview: str = ""
    raw_html: str = ""

    def to_dict(self, *, include_html: bool) -> dict[str, Any]:
        payload = {
            "issue_key": self.issue_key,
            "source_url": self.source_url,
            "html_length": self.html_length,
            "clue_count": self.clue_count,
            "clues": [asdict(clue) for clue in self.clues],
        }
        if include_html:
            payload["raw_html_preview"] = self.raw_html_preview
            payload["raw_html"] = self.raw_html
        return payload