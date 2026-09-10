"""Configuration models for the JIRA context harness."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass
class JiraSettings:
    base_url: str
    user_email: str
    api_token: str
    project_scope: str

    def missing_required(self) -> list[str]:
        missing: list[str] = []
        if not self.base_url:
            missing.append("JIRA_BASE_URL")
        if not self.user_email:
            missing.append("JIRA_USER_EMAIL")
        if not self.api_token:
            missing.append("JIRA_API_TOKEN")
        return missing


def load_settings() -> JiraSettings:
    return JiraSettings(
        base_url=os.getenv("JIRA_BASE_URL", ""),
        user_email=os.getenv("JIRA_USER_EMAIL", ""),
        api_token=os.getenv("JIRA_API_TOKEN", ""),
        project_scope=os.getenv("JIRA_PROJECT_SCOPE", "MFD"),
    )