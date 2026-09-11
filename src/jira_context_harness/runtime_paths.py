"""Runtime path helpers for source and frozen executable deployments."""

from __future__ import annotations

from pathlib import Path
import sys


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def raw_payload_artifact_dir() -> Path:
    return runtime_root() / ".artifacts" / "tmp"


def normalized_output_dir() -> Path:
    return runtime_root() / "jira-output"