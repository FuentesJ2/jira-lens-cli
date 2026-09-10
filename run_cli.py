"""Root-level launcher for local CLI use before package installation."""

from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_src_path() -> None:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    src_path_text = str(src_path)
    if src_path_text not in sys.path:
        sys.path.insert(0, src_path_text)


def main() -> int:
    _bootstrap_src_path()
    from jira_context_harness.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())