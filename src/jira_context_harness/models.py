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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JiraFetchResult:
    issue: JiraIssueContext
    raw_response: dict[str, Any]

    def normalized_dict(self) -> dict[str, Any]:
        return self.issue.to_dict()

    def combined_dict(self) -> dict[str, Any]:
        return {
            "normalized": self.normalized_dict(),
            "raw_response": self.raw_response,
        }