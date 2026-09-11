"""Root-level launcher for local CLI use before package installation."""

from __future__ import annotations

from pathlib import Path
import sys


MIN_PYTHON = (3, 9)


def _bootstrap_src_path() -> None:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    src_path_text = str(src_path)
    if src_path_text not in sys.path:
        sys.path.insert(0, src_path_text)


def _ensure_supported_python() -> int:
    if sys.version_info >= MIN_PYTHON:
        return 0
    print(
        f"jira-context requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+; current interpreter is "
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    version_error = _ensure_supported_python()
    if version_error:
        return version_error
    _bootstrap_src_path()
    from jira_context_harness.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())