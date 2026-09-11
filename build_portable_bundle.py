"""Build a portable Windows executable bundle for jira-context."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
DIST_ROOT = PROJECT_ROOT / "dist" / "jira-context-portable"
BUILD_ROOT = PROJECT_ROOT / "build" / "pyinstaller"
SOURCE_SKILL_ROOT = PROJECT_ROOT / ".github" / "skills" / "jira-context-cli"
DEFAULT_DEPLOY_ROOT = Path("C:/Dev/.github")

DEPLOYED_TOOL_README = """# jira-context Portable Runtime

This folder is the portable runtime bundle for the Jira context CLI.

The preferred deployed shape is a compiled `jira-context.exe` plus this folder's support files.

## Runtime contract

- Run `jira-context.exe` from this folder.
- Configuration is stored in `.env` in this folder.
- Raw trust artifacts are written to `.artifacts/tmp/` in this folder.
- User-visible saved JSON files can go in `jira-output/` in this folder.
"""

DEPLOYED_TOOL_GITIGNORE = """.env
.artifacts/tmp/*
!.artifacts/tmp/.gitkeep
jira-output/*
!jira-output/README.txt
"""

DEPLOYED_JIRA_OUTPUT_README = (
    "Use this folder for user-visible normalized JSON outputs when you want to persist CLI fetch results.\n"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and deploy the portable jira-context executable bundle into a workspace .github folder.",
    )
    deploy_target_group = parser.add_mutually_exclusive_group()
    deploy_target_group.add_argument(
        "--deploy-root",
        type=Path,
        help="Destination .github directory. Defaults to C:/Dev/.github.",
    )
    deploy_target_group.add_argument(
        "--workspace-root",
        type=Path,
        help="Workspace root that should receive the deployed .github/tool and .github/skills content.",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build the portable bundle but do not deploy it.",
    )
    parser.add_argument(
        "--no-bootstrap-build-tools",
        action="store_true",
        help="Fail instead of auto-installing the build dependency group when PyInstaller is missing.",
    )
    parser.add_argument(
        "--keep-dist",
        action="store_true",
        help="Keep any existing dist/build folders instead of deleting them first.",
    )
    return parser.parse_args()


def _resolve_deploy_root(args: argparse.Namespace) -> Path:
    if args.workspace_root is not None:
        return (args.workspace_root / ".github").resolve()

    if args.deploy_root is not None:
        return args.deploy_root.resolve()

    return DEFAULT_DEPLOY_ROOT


def _ensure_build_tools(*, allow_bootstrap: bool) -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return

    if not allow_bootstrap:
        raise SystemExit(
            "PyInstaller is not available. Install the build dependency group with `python -m pip install .[build]` or rerun without --no-bootstrap-build-tools."
        )

    command = [sys.executable, "-m", "pip", "install", ".[build]"]
    try:
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Failed to bootstrap build dependencies with `python -m pip install .[build]`."
        ) from exc


def _run_pyinstaller() -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "jira-context",
        "--distpath",
        str(DIST_ROOT / "bin"),
        "--workpath",
        str(BUILD_ROOT),
        "--specpath",
        str(BUILD_ROOT),
        "--paths",
        str(PROJECT_ROOT / "src"),
        "--hidden-import",
        "jira_context_harness.cli",
        "--hidden-import",
        "jira_context_harness.config",
        "--hidden-import",
        "jira_context_harness.jira_client",
        "--hidden-import",
        "jira_context_harness.models",
        "--hidden-import",
        "jira_context_harness.runtime_paths",
        str(PROJECT_ROOT / "run_cli.py"),
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"PyInstaller build failed with exit code {exc.returncode}.") from exc


def _reset_output(*, keep_dist: bool) -> None:
    if keep_dist:
        return
    shutil.rmtree(DIST_ROOT, ignore_errors=True)
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _assemble_bundle() -> Path:
    bundle_root = DIST_ROOT / "bundle"
    bundle_root.mkdir(parents=True, exist_ok=True)

    built_exe = DIST_ROOT / "bin" / "jira-context.exe"
    if not built_exe.exists():
        raise SystemExit(f"Expected PyInstaller output was not found: {built_exe}")

    _copy_file(built_exe, bundle_root / "jira-context.exe")
    _write_file(bundle_root / ".gitignore", DEPLOYED_TOOL_GITIGNORE)
    _write_file(bundle_root / "README.md", DEPLOYED_TOOL_README)
    _write_file(bundle_root / ".artifacts" / "tmp" / ".gitkeep", "keep\n")
    _write_file(bundle_root / "jira-output" / "README.txt", DEPLOYED_JIRA_OUTPUT_README)
    return bundle_root


def _replace_tree(source: Path, destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _deploy_bundle(bundle_root: Path, deploy_root: Path) -> Path:
    tool_destination = deploy_root / "tools" / "jira-context"
    _replace_tree(bundle_root, tool_destination)
    return tool_destination


def _deploy_skill(deploy_root: Path) -> list[Path]:
    if not SOURCE_SKILL_ROOT.exists():
        raise SystemExit(f"Tracked skill source not found: {SOURCE_SKILL_ROOT}")

    destination = deploy_root / "skills" / "jira-context-cli"
    _replace_tree(SOURCE_SKILL_ROOT, destination)
    return [destination]


def main() -> int:
    args = _parse_args()
    deploy_root = _resolve_deploy_root(args)
    _reset_output(keep_dist=args.keep_dist)
    _ensure_build_tools(allow_bootstrap=not args.no_bootstrap_build_tools)
    _run_pyinstaller()
    bundle_root = _assemble_bundle()
    print(f"Built portable bundle at {bundle_root}")

    if not args.build_only:
        tool_destination = _deploy_bundle(bundle_root, deploy_root)
        skill_destinations = _deploy_skill(deploy_root)
        print(f"Deployed portable bundle to {tool_destination}")
        for destination in skill_destinations:
            print(f"Deployed skill to {destination}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())