"""Configuration models for the JIRA context harness."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, Mapping, Optional


DEFAULT_BASE_URL = "https://avjira"
DEFAULT_PROJECT_SCOPE = "MFD"
DEFAULT_DEPLOYMENT = "server_dc"
DEFAULT_AUTH_MODE = "basic"
SETTINGS_KEYS = [
    "JIRA_BASE_URL",
    "JIRA_USER_EMAIL",
    "JIRA_PASSWORD",
    "JIRA_API_TOKEN",
    "JIRA_PROJECT_SCOPE",
    "JIRA_DEPLOYMENT",
    "JIRA_AUTH_MODE",
]


@dataclass
class JiraSettings:
    base_url: str
    user_email: str
    password: str
    api_token: str
    project_scope: str
    deployment: str = DEFAULT_DEPLOYMENT
    auth_mode: str = DEFAULT_AUTH_MODE

    def missing_required(self) -> list[str]:
        missing: list[str] = []
        if not self.base_url:
            missing.append("JIRA_BASE_URL")
        if not self.user_email:
            missing.append("JIRA_USER_EMAIL")

        auth_mode = (self.auth_mode or DEFAULT_AUTH_MODE).strip().lower()
        deployment = (self.deployment or DEFAULT_DEPLOYMENT).strip().lower()
        is_cloud_host = self.base_url.rstrip("/").lower().endswith(".atlassian.net")
        is_cloud = deployment == "cloud" or (deployment == "auto" and is_cloud_host)
        is_server_dc = deployment in {"server", "server_dc", "data_center", "datacenter"}

        if auth_mode == "basic":
            if is_cloud:
                if not self.api_token:
                    missing.append("JIRA_API_TOKEN")
            elif not self.password:
                missing.append("JIRA_PASSWORD")
        elif auth_mode == "bearer":
            if not self.api_token:
                missing.append("JIRA_API_TOKEN")
        elif is_cloud:
            if not self.api_token:
                missing.append("JIRA_API_TOKEN")
        elif is_server_dc or deployment == "auto":
            if not self.password and not self.api_token:
                missing.append("JIRA_PASSWORD or JIRA_API_TOKEN")
        return missing


def default_env_file_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def load_settings(
    environment: Optional[Mapping[str, str]] = None,
    env_file_path: Optional[Path] = None,
) -> JiraSettings:
    combined_environment: Dict[str, str] = {}
    config_path = env_file_path or default_env_file_path()
    combined_environment.update(_read_env_file(config_path))
    combined_environment.update(dict(environment or os.environ))

    return JiraSettings(
        base_url=combined_environment.get("JIRA_BASE_URL", DEFAULT_BASE_URL),
        user_email=combined_environment.get("JIRA_USER_EMAIL", ""),
        password=combined_environment.get("JIRA_PASSWORD", ""),
        api_token=combined_environment.get("JIRA_API_TOKEN", ""),
        project_scope=combined_environment.get("JIRA_PROJECT_SCOPE", DEFAULT_PROJECT_SCOPE),
        deployment=combined_environment.get("JIRA_DEPLOYMENT", DEFAULT_DEPLOYMENT),
        auth_mode=combined_environment.get("JIRA_AUTH_MODE", DEFAULT_AUTH_MODE),
    )


def save_settings(settings: JiraSettings, env_file_path: Optional[Path] = None) -> Path:
    config_path = env_file_path or default_env_file_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    values = _read_env_file(config_path)
    values.update(
        {
            "JIRA_BASE_URL": settings.base_url.strip(),
            "JIRA_USER_EMAIL": settings.user_email.strip(),
            "JIRA_PASSWORD": settings.password.strip(),
            "JIRA_API_TOKEN": settings.api_token.strip(),
            "JIRA_PROJECT_SCOPE": settings.project_scope.strip() or DEFAULT_PROJECT_SCOPE,
            "JIRA_DEPLOYMENT": settings.deployment.strip() or DEFAULT_DEPLOYMENT,
            "JIRA_AUTH_MODE": settings.auth_mode.strip() or DEFAULT_AUTH_MODE,
        }
    )

    lines = [f"{key}={values.get(key, '')}" for key in SETTINGS_KEYS]
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def _read_env_file(env_file_path: Path) -> Dict[str, str]:
    if not env_file_path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in env_file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values