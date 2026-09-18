"""CLI entry point for the JIRA context harness."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import getpass
import json
import re
import sys
from pathlib import Path
from typing import Optional, Sequence, TextIO

from jira_context_harness import __version__
from jira_context_harness.config import (
    DEFAULT_AUTH_MODE,
    DEFAULT_BASE_URL,
    DEFAULT_DEPLOYMENT,
    DEFAULT_PROJECT_SCOPE,
    JiraSettings,
    default_env_file_path,
    load_settings,
    save_settings,
)
from jira_context_harness.jira_client import (
    FetchRequest,
    JiraClient,
    JiraClientError,
    JiraConfigurationError,
)
from jira_context_harness.runtime_paths import normalized_output_dir, raw_payload_artifact_dir, runtime_root


DEFAULT_TEST_CASE_FIELDS = [
    "summary",
    "description",
    "comment",
    "status",
    "issuetype",
    "project",
    "assignee",
    "updated",
    "issuelinks",
]

DEFAULT_REQUIREMENT_EXTRA_FIELDS = [
    "components",
    "labels",
    "priority",
    "resolution",
    "customfield_10170",  # Vehicle
    "customfield_10703",  # Verification Method
    "customfield_10708",  # Rationale
    "customfield_16505",  # Requirement Level
    "customfield_18002",  # Verification Environment
    "customfield_19801",  # Data ID
]

RAW_PAYLOAD_ARTIFACT_DIR = raw_payload_artifact_dir()
NORMALIZED_OUTPUT_DIR = normalized_output_dir()
VALID_FETCH_VIEWS = {"normalized", "raw", "combined"}
LEGACY_FETCH_VIEW_ALIASES = {"both": "combined"}


def _default_fields_for(issue_kind: str) -> list[str]:
    if issue_kind == "test-case":
        return list(DEFAULT_TEST_CASE_FIELDS)
    if issue_kind == "requirement":
        return list(DEFAULT_TEST_CASE_FIELDS) + list(DEFAULT_REQUIREMENT_EXTRA_FIELDS)
    return list(DEFAULT_TEST_CASE_FIELDS)


def _parse_fetch_view(value: str) -> str:
    normalized = LEGACY_FETCH_VIEW_ALIASES.get(value, value)
    if normalized not in VALID_FETCH_VIEWS:
        allowed = ", ".join(sorted(VALID_FETCH_VIEWS | set(LEGACY_FETCH_VIEW_ALIASES)))
        raise argparse.ArgumentTypeError(f"Unsupported --view value '{value}'. Expected one of: {allowed}")
    return normalized


def _artifact_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip("-.")
    return slug or "unknown"


def _write_json_file(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _version_info() -> dict[str, str]:
    runtime_mode = "frozen" if getattr(sys, "frozen", False) else "source"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return {
        "name": "jira-context-harness",
        "version": __version__,
        "runtime_mode": runtime_mode,
        "runtime_root": str(runtime_root()),
        "executable": sys.executable,
        "python_version": python_version,
    }


def _render_version_text(version_info: dict[str, str]) -> str:
    return "\n".join(
        [
            f"{version_info['name']} {version_info['version']}",
            f"runtime_mode: {version_info['runtime_mode']}",
            f"runtime_root: {version_info['runtime_root']}",
            f"executable: {version_info['executable']}",
            f"python_version: {version_info['python_version']}",
        ]
    )


def resolve_output_artifact_path(path_arg: str | Path, default_dir: Path) -> Path:
    candidate = Path(path_arg)
    if not candidate.is_absolute():
        candidate = default_dir / candidate
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira-context",
        description="Local CLI for JIRA context retrieval.",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"jira-context-harness {__version__}",
        help="Print CLI version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch a single JIRA issue for local inspection or downstream agent use.",
    )
    fetch_parser.add_argument(
        "issue_kind",
        choices=["test-case", "requirement", "problem-report"],
        help="Type of issue to fetch.",
    )
    fetch_parser.add_argument("issue_key", help="JIRA issue key, such as MFD-1234.")
    fetch_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format for the fetched issue.",
    )
    fetch_parser.add_argument(
        "--view",
        type=_parse_fetch_view,
        metavar="{normalized,raw,combined}",
        default="normalized",
        help=argparse.SUPPRESS,
    )
    fetch_parser.add_argument(
        "--include-raw-payload",
        action="store_true",
        help="Keep stdout limited to normalized JSON and also save the raw fetched payload to jira-output for optional inspection.",
    )
    fetch_parser.add_argument(
        "--save-normalized-to",
        default=None,
        help="Optional file path to save the normalized fetch output to disk and suppress normalized stdout output.",
    )
    fetch_parser.add_argument(
        "--save-raw-payload-to",
        default=None,
        help="Optional file path to save the raw fetched payload JSON. Implies --include-raw-payload.",
    )
    fetch_parser.add_argument(
        "--section",
        choices=[
            "full",
            "issue",
            "links",
            "comments",
            "test-management",
            "authored-steps",
            "ad-hoc-runs",
        ],
        default="full",
        help="Return a focused subset of the fetched issue, useful for agent consumption and trust checks.",
    )
    fetch_parser.add_argument(
        "--field",
        action="append",
        dest="fields",
        default=None,
        help="Additional Jira field to request. Can be passed multiple times.",
    )
    fetch_parser.add_argument(
        "--expand",
        action="append",
        default=None,
        help="Jira expand value to request. Can be passed multiple times.",
    )
    fetch_parser.add_argument(
        "--property",
        action="append",
        dest="properties",
        default=None,
        help="Jira issue property to request. Can be passed multiple times.",
    )
    fetch_parser.add_argument(
        "--fields-by-keys",
        action="store_true",
        help="Request custom fields by key when supported by the Jira site.",
    )
    fetch_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Set failFast=false on the Jira request.",
    )
    fetch_parser.add_argument(
        "--no-config-prompt",
        action="store_true",
        help="Do not prompt to create local Jira config when required settings are missing.",
    )

    configure_parser = subparsers.add_parser(
        "configure",
        help="Create or update the local Jira config used by the CLI.",
    )
    configure_parser.add_argument(
        "--advanced",
        action="store_true",
        help="Prompt for deployment and auth mode overrides.",
    )

    subparsers.add_parser(
        "probe-auth",
        help="Test the saved Jira auth settings against the Jira user endpoint.",
    )

    synapse_probe_parser = subparsers.add_parser(
        "probe-synapse",
        help="Probe likely TestRay or Synapse plugin endpoints for structured test case data.",
    )
    synapse_probe_parser.add_argument("issue_key", help="JIRA issue key, such as MFD-1234.")

    inspect_page_parser = subparsers.add_parser(
        "inspect-page",
        help="Fetch the Jira browse page HTML and surface Synapse or step-grid clues.",
    )
    inspect_page_parser.add_argument("issue_key", help="JIRA issue key, such as MFD-1234.")
    inspect_page_parser.add_argument(
        "--include-html",
        action="store_true",
        help="Include a preview of the raw HTML in the output.",
    )

    discover_parser = subparsers.add_parser(
        "discover-fields",
        help="Inspect all Jira fields on an issue and identify likely test-case context fields.",
    )
    discover_parser.add_argument("issue_key", help="JIRA issue key, such as MFD-1234.")
    discover_parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include the full raw Jira issue response alongside the discovery report.",
    )

    version_parser = subparsers.add_parser(
        "version",
        help="Print CLI version and runtime metadata.",
    )
    version_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for version information.",
    )

    return parser


def render_fetch_output(
    *,
    result: object,
    output_format: str,
    view: str,
    section: str,
) -> str:
    if output_format == "text":
        if view != "normalized":
            raise ValueError("Text format only supports normalized view")
        if section != "full":
            raise ValueError("Text format only supports section full")
        issue = result.issue
        lines = [
            f"Issue key: {issue.issue_key}",
            f"Issue kind: {issue.issue_kind}",
            f"Issue type: {issue.issue_type}",
            f"Status: {issue.status}",
            f"Project: {issue.project_key}",
            f"Assignee: {issue.assignee}",
            f"Updated: {issue.updated}",
            f"Summary: {issue.summary}",
            f"Description format: {issue.description_format}",
            "Description:",
            issue.description,
        ]
        return "\n".join(lines).rstrip() + "\n"

    payload = _render_fetch_payload(result=result, view=view, section=section)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_fetch_payload(*, result: object, view: str, section: str) -> object:
    if section == "full":
        if view == "normalized":
            return result.normalized_dict()
        if view == "raw":
            return result.raw_response
        return result.combined_dict()

    normalized_section, raw_section = _fetch_section_payloads(result=result, section=section)
    if view == "normalized":
        return normalized_section
    if view == "raw":
        return raw_section
    return {
        "normalized": normalized_section,
        "raw_response": raw_section,
    }


def _fetch_section_payloads(*, result: object, section: str) -> tuple[object, object]:
    normalized = result.normalized_dict()
    raw_response = result.raw_response
    supplemental = getattr(result, "supplemental_responses", {}) or {}
    test_management = normalized.get("test_management", {})

    if section == "issue":
        issue_payload = dict(normalized)
        issue_payload.pop("test_management", None)
        return issue_payload, raw_response
    if section == "links":
        raw_links = []
        if isinstance(raw_response, dict):
            fields = raw_response.get("fields")
            if isinstance(fields, dict):
                raw_links = fields.get("issuelinks") or []
        return normalized.get("links", []), raw_links
    if section == "comments":
        raw_comments = []
        if isinstance(raw_response, dict):
            fields = raw_response.get("fields")
            if isinstance(fields, dict):
                comments_payload = fields.get("comment")
                if isinstance(comments_payload, dict):
                    raw_comments = comments_payload.get("comments") or []
        return normalized.get("comments", []), raw_comments
    if section == "test-management":
        return test_management, supplemental
    if section == "authored-steps":
        return test_management.get("test_steps", []), supplemental.get("test_steps", [])
    if section == "ad-hoc-runs":
        return test_management.get("ad_hoc_test_runs", []), supplemental.get("ad_hoc_test_runs", [])
    raise ValueError(f"Unsupported section {section}")


def _build_raw_payload_artifact(*, result: object, section: str) -> dict[str, object]:
    if section == "full":
        payload: dict[str, object] = {
            "raw_response": result.raw_response,
        }
        supplemental = getattr(result, "supplemental_responses", {}) or {}
        if supplemental:
            payload["supplemental_responses"] = supplemental
        return payload

    _normalized_section, raw_section = _fetch_section_payloads(result=result, section=section)
    return {
        "raw_response": raw_section,
    }


def _write_raw_payload_artifact(
    *,
    result: object,
    issue_kind: str,
    issue_key: str,
    section: str,
    artifact_path: Optional[Path] = None,
) -> Path:
    RAW_PAYLOAD_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if artifact_path is None:
        artifact_name = (
            f"fetch-{_artifact_slug(issue_kind)}-{_artifact_slug(issue_key)}-"
            f"{_artifact_slug(section)}-raw-payload.json"
        )
        artifact_path = RAW_PAYLOAD_ARTIFACT_DIR / artifact_name
    artifact_payload = {
        "issue_key": result.issue.issue_key,
        "issue_kind": result.issue.issue_kind,
        "section": section,
        "raw_payload": _build_raw_payload_artifact(result=result, section=section),
    }
    return _write_json_file(artifact_path, artifact_payload)


def _resolve_settings(
    *,
    allow_prompt: bool,
    input_stream: TextIO,
    error_stream: TextIO,
    env_file_path: Optional[Path] = None,
) -> JiraSettings:
    settings = load_settings(env_file_path=env_file_path)
    if not settings.missing_required():
        return settings

    if not allow_prompt or not _supports_interactive_prompt(input_stream):
        raise JiraConfigurationError(
            "Missing required Jira settings: " + ", ".join(settings.missing_required())
        )

    config_path = env_file_path or default_env_file_path()
    print(
        "Jira settings are missing. Starting first-run setup.",
        file=error_stream,
    )
    print(
        f"Values will be saved to {config_path} and reused on future runs.",
        file=error_stream,
    )
    prompted_settings = _prompt_for_settings(
        existing=settings,
        input_stream=input_stream,
        error_stream=error_stream,
        advanced=False,
    )
    saved_path = save_settings(prompted_settings, env_file_path=config_path)
    print(f"Saved Jira settings to {saved_path}", file=error_stream)
    return prompted_settings


def _supports_interactive_prompt(input_stream: TextIO) -> bool:
    return bool(getattr(input_stream, "isatty", lambda: False)())


def _prompt_for_settings(
    *,
    existing: JiraSettings,
    input_stream: TextIO,
    error_stream: TextIO,
    advanced: bool,
) -> JiraSettings:
    base_url = _prompt_text(
        "Jira base URL",
        default=existing.base_url or DEFAULT_BASE_URL,
        input_stream=input_stream,
        error_stream=error_stream,
    )
    user_email = _prompt_text(
        "Jira username or email",
        default=existing.user_email,
        input_stream=input_stream,
        error_stream=error_stream,
    )
    project_scope = _prompt_text(
        "Default Jira project scope",
        default=existing.project_scope or DEFAULT_PROJECT_SCOPE,
        input_stream=input_stream,
        error_stream=error_stream,
    )
    if advanced:
        deployment = _prompt_text(
            "Jira deployment (server_dc, cloud, auto)",
            default=existing.deployment or DEFAULT_DEPLOYMENT,
            input_stream=input_stream,
            error_stream=error_stream,
        )
        auth_mode = _prompt_text(
            "Jira auth mode (basic, bearer, auto)",
            default=existing.auth_mode or DEFAULT_AUTH_MODE,
            input_stream=input_stream,
            error_stream=error_stream,
        )
    else:
        deployment = existing.deployment or DEFAULT_DEPLOYMENT
        auth_mode = existing.auth_mode or DEFAULT_AUTH_MODE
    password, api_token = _prompt_auth_secret_values(
        base_url=base_url,
        deployment=deployment or DEFAULT_DEPLOYMENT,
        auth_mode=auth_mode or DEFAULT_AUTH_MODE,
        existing=existing,
        error_stream=error_stream,
    )
    return JiraSettings(
        base_url=base_url,
        user_email=user_email,
        password=password,
        api_token=api_token,
        project_scope=project_scope or DEFAULT_PROJECT_SCOPE,
        deployment=deployment or DEFAULT_DEPLOYMENT,
        auth_mode=auth_mode or DEFAULT_AUTH_MODE,
    )


def _prompt_text(
    label: str,
    *,
    default: str,
    input_stream: TextIO,
    error_stream: TextIO,
) -> str:
    suffix = f" [{default}]" if default else ""
    print(f"{label}{suffix}: ", end="", file=error_stream, flush=True)
    value = input_stream.readline()
    if value == "":
        raise JiraConfigurationError("Interactive setup cancelled before configuration was completed")
    return value.rstrip("\r\n") or default


def _prompt_secret(label: str, *, existing_value: str, error_stream: TextIO) -> str:
    suffix = " [saved]" if existing_value else ""
    try:
        value = getpass.getpass(f"{label}{suffix}: ", stream=error_stream)
    except (EOFError, KeyboardInterrupt) as exc:
        raise JiraConfigurationError(
            "Interactive setup cancelled before configuration was completed"
        ) from exc
    return value or existing_value


def _prompt_auth_secret_values(
    *,
    base_url: str,
    deployment: str,
    auth_mode: str,
    existing: JiraSettings,
    error_stream: TextIO,
) -> tuple[str, str]:
    normalized_deployment = deployment.strip().lower()
    normalized_auth_mode = auth_mode.strip().lower()
    is_cloud = normalized_deployment == "cloud" or base_url.rstrip("/").lower().endswith(
        ".atlassian.net"
    )

    if normalized_auth_mode == "bearer":
        return "", _prompt_secret(
            "Jira personal access token",
            existing_value=existing.api_token,
            error_stream=error_stream,
        )

    if normalized_auth_mode == "basic" and not is_cloud:
        return (
            _prompt_secret(
                "Jira password",
                existing_value=existing.password,
                error_stream=error_stream,
            ),
            "",
        )

    if is_cloud:
        return "", _prompt_secret(
            "Atlassian API token",
            existing_value=existing.api_token,
            error_stream=error_stream,
        )

    print(
        "For internal Jira with auto auth, enter a password for basic auth and/or a personal access token for bearer auth.",
        file=error_stream,
    )
    password = _prompt_secret(
        "Jira password",
        existing_value=existing.password,
        error_stream=error_stream,
    )
    api_token = _prompt_secret(
        "Jira personal access token",
        existing_value=existing.api_token,
        error_stream=error_stream,
    )
    return password, api_token


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        version_info = _version_info()
        if args.format == "json":
            print(json.dumps(version_info, indent=2, sort_keys=True))
        else:
            print(_render_version_text(version_info))
        return 0

    if args.command == "fetch":
        legacy_combined_requested = args.view == "combined"
        if legacy_combined_requested:
            args.include_raw_payload = True
            args.view = "normalized"
        if args.save_raw_payload_to:
            args.include_raw_payload = True

        if args.include_raw_payload and args.view == "raw":
            parser.error("--include-raw-payload cannot be combined with --view raw")
        if args.save_normalized_to and args.format != "json":
            parser.error("--save-normalized-to only supports --format json")
        if args.save_normalized_to and args.view != "normalized":
            parser.error("--save-normalized-to only supports --view normalized")

        if args.format == "text" and args.view != "normalized":
            parser.error("--format text only supports --view normalized")
        if args.format == "text" and args.section != "full":
            parser.error("--format text only supports --section full")

        request_model = FetchRequest(
            issue_kind=args.issue_kind,
            issue_key=args.issue_key,
            fields=_default_fields_for(args.issue_kind) + (args.fields or []),
            expand=args.expand,
            properties=args.properties,
            fields_by_keys=args.fields_by_keys,
            fail_fast=not args.allow_partial,
        )
        try:
            settings = _resolve_settings(
                allow_prompt=not args.no_config_prompt,
                input_stream=sys.stdin,
                error_stream=sys.stderr,
            )
            client = JiraClient(settings)
            result = client.fetch_issue(request_model)
        except (JiraConfigurationError, JiraClientError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        rendered_output = render_fetch_output(
            result=result,
            output_format=args.format,
            view=args.view,
            section=args.section,
        )

        if legacy_combined_requested:
            print(
                "`--view combined` is deprecated for `fetch`. Use `--include-raw-payload` instead. Stdout now stays normalized while the raw payload is written to jira-output/.",
                file=sys.stderr,
            )

        if args.include_raw_payload:
            resolved_raw_payload_path = (
                resolve_output_artifact_path(args.save_raw_payload_to, RAW_PAYLOAD_ARTIFACT_DIR)
                if args.save_raw_payload_to
                else None
            )
            artifact_path = _write_raw_payload_artifact(
                result=result,
                issue_kind=args.issue_kind,
                issue_key=args.issue_key,
                section=args.section,
                artifact_path=resolved_raw_payload_path,
            )
            print(f"Saved raw payload JSON to {artifact_path}", file=sys.stderr)

        if args.save_normalized_to:
            resolved_normalized_path = resolve_output_artifact_path(
                args.save_normalized_to,
                NORMALIZED_OUTPUT_DIR,
            )
            normalized_path = _write_json_file(resolved_normalized_path, json.loads(rendered_output))
            print(f"Saved normalized output to {normalized_path}", file=sys.stderr)
            return 0

        print(rendered_output, end="")
        return 0

    if args.command == "configure":
        try:
            existing = load_settings()
            updated = _prompt_for_settings(
                existing=existing,
                input_stream=sys.stdin,
                error_stream=sys.stderr,
                advanced=args.advanced,
            )
            saved_path = save_settings(updated)
        except JiraConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(f"Saved Jira settings to {saved_path}", file=sys.stderr)
        return 0

    if args.command == "probe-auth":
        try:
            settings = _resolve_settings(
                allow_prompt=True,
                input_stream=sys.stdin,
                error_stream=sys.stderr,
            )
            client = JiraClient(settings)
            attempts = client.probe_auth()
        except (JiraConfigurationError, JiraClientError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(json.dumps([asdict(attempt) for attempt in attempts], indent=2, sort_keys=True))
        return 0

    if args.command == "discover-fields":
        try:
            settings = _resolve_settings(
                allow_prompt=True,
                input_stream=sys.stdin,
                error_stream=sys.stderr,
            )
            client = JiraClient(settings)
            result = client.discover_issue_fields(args.issue_key)
        except (JiraConfigurationError, JiraClientError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(json.dumps(result.to_dict(include_raw=args.include_raw), indent=2, sort_keys=True))
        return 0

    if args.command == "inspect-page":
        try:
            settings = _resolve_settings(
                allow_prompt=True,
                input_stream=sys.stdin,
                error_stream=sys.stderr,
            )
            client = JiraClient(settings)
            result = client.inspect_issue_page(args.issue_key)
        except (JiraConfigurationError, JiraClientError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(json.dumps(result.to_dict(include_html=args.include_html), indent=2, sort_keys=True))
        return 0

    if args.command == "probe-synapse":
        try:
            settings = _resolve_settings(
                allow_prompt=True,
                input_stream=sys.stdin,
                error_stream=sys.stderr,
            )
            client = JiraClient(settings)
            attempts = client.probe_synapse_test_case(args.issue_key)
        except (JiraConfigurationError, JiraClientError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(json.dumps([asdict(attempt) for attempt in attempts], indent=2, sort_keys=True))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())