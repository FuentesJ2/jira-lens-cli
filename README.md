# jira-context-harness

Local sidecar project for agent-facing JIRA context retrieval.

This project is intentionally outside the `mfd` and `mfd-test-framework` repositories so the harness can evolve without polluting either repo.

## Python compatibility

The harness currently targets Python 3.9+.

## Deployment shape

There are two valid runtime shapes now:

1. Development shape: source code plus `jira-context.cmd`
2. Portable deployment shape: compiled `jira-context.exe` plus support folders

The portable deployment shape is the one you want when the tool should stay in the workspace without exposing the full source tree.

## Initial goals

1. Provide a human-usable CLI for fetching JIRA issue context.
2. Start with single-issue fetches for test cases and requirements.
3. Defer graph expansion, link crawling, and attachment workflows until later slices.

## Planned structure

- `src/jira_context_harness/`: application code
- `tests/`: scaffolded tests
- `docs/`: architecture notes and planning artifacts

## Current status

The CLI is now functional end to end for the core workflow. Current capabilities:

1. Fetch a single Jira issue for `test-case`, `requirement`, and `problem-report`.
2. Normalize Jira and Synapse or TestRay responses into smaller agent-friendly JSON.
3. Save normalized JSON and optional raw payload JSON in `jira-output/`.
4. Support focused fetch sections such as `links`, `comments`, `authored-steps`, `ad-hoc-runs`, and `test-management`.
5. Prompt for missing Jira settings on first use, save them locally, and retry the fetch automatically.
6. Deploy as a portable workspace bundle under `.github/tools/jira-context/` plus the Copilot skill under `.github/skills/jira-context-cli/`.

The workspace skill at `.github/skills/jira-context-cli/` is the active Copilot integration path for this pure-CLI workflow. In the surrounding `Dev-Sidecar` workspace, the workspace-root `.github/copilot-instructions.md` can provide repo-aware Copilot context without placing that file inside the simulated deployment tree in this repository.

When this harness is used alongside Tessie or other MFD test-generation workflows, live Jira data should be fetched with this CLI first and repository CSVs should be treated as secondary references unless the user explicitly wants an offline workflow.

The currently known browser issue URL for this workflow is `https://avjira/browse/MFD-7754`. If that is the authoritative Jira host, the harness may need to target Jira Server or Data Center REST endpoints instead of Jira Cloud v3.

## Quick start for teammates

If you are already at a workspace root, install the latest release with:

```powershell
Invoke-WebRequest -OutFile install-jira-context.ps1 https://github.com/FuentesJ2/jira-lens-cli/raw/main/install-jira-context.ps1; .\install-jira-context.ps1
```

The installer works even if the workspace does not have a `.github` folder yet; it will create the managed `.github`, `.github/skills`, and `.github/tools` folders.

Then run a first fetch:

```powershell
.\.github\tools\jira-context\jira-context.exe fetch requirement DMFDREQ-1448
```

If Jira settings are missing, the CLI will prompt once, save them locally, and retry the fetch automatically.

## CLI usage

Set environment variables:

```text
JIRA_BASE_URL=https://avjira
JIRA_USER_EMAIL=your_jira_username
JIRA_PASSWORD=
JIRA_API_TOKEN=your_api_token
JIRA_PROJECT_SCOPE=MFD
JIRA_DEPLOYMENT=server_dc
JIRA_AUTH_MODE=basic
```

### Local execution without installation

If you have not installed the package yet, run the launcher from the project root:

```text
./jira-context.cmd fetch test-case MFD-1234
```

This is the most reliable local validation path because it does not depend on `pip install -e .` or shell `PATH` setup.

The checked-in `jira-context.cmd` wrapper now prefers a sibling `jira-context.exe` when one exists. If no executable is present, it falls back to Python source execution.

For agent-driven `fetch`, the canonical payload should be a saved normalized JSON file created with `--save-normalized-to`.
After the fetch completes, open that saved normalized JSON file directly instead of re-reading terminal output.
If you also want the original raw payload JSON, use `--include-raw-payload` or `--save-raw-payload-to`; keep the raw payload on disk unless it is needed.
Do not treat Copilot chat-session transcript files or temporary terminal capture files as the primary artifact when the normalized JSON file already exists.
Keep runtime payload files under the harness root, not inside `.github/skills/`, so the skill content remains shareable and version-controlled without artifact churn.

On first run, if required Jira settings are missing, the CLI will prompt for them interactively, save them to a local `.env` file in the project root, and then retry the same fetch command.

The secret prompt now depends on the selected deployment and auth mode:

1. Jira Cloud + basic auth: `Atlassian API token`
2. Internal Jira + basic auth: `Jira password`
3. Internal Jira + bearer auth: `Jira personal access token`

Normal team onboarding defaults to `https://avjira`, `server_dc`, `basic`, and `MFD`, so most users should only need to provide username and password.

If you need to update the saved configuration later, run:

```text
./jira-context.cmd configure
```

If someone needs to override the default internal Jira assumptions, use:

```text
./jira-context.cmd configure --advanced
```

To diagnose whether your saved credentials can authenticate to Jira at all, run:

```text
./jira-context.cmd probe-auth > jira-auth-probe.json
```

To discover which Jira fields actually store test steps, requirement panels, attachments, test plans, and related Synapse data for a specific issue, run:

```text
./jira-context.cmd discover-fields MFD-7754 > jira-field-discovery.json
```

If you also want the full all-fields Jira response in the same output file, run:

```text
./jira-context.cmd discover-fields MFD-7754 --include-raw > jira-field-discovery-full.json
```

If the standard Jira issue response still does not expose the structured step grid, probe the TestRay or Synapse plugin endpoints directly:

```text
./jira-context.cmd probe-synapse MFD-7754 > jira-synapse-probe.json
```

This command targets the plugin base path used in the team docs: `https://avjira/rest/synapse/latest/public/`.
It now probes the documented TestRay DC test-case resources first, including `/testCase/{issueKey}/steps`, `/linkedRequirements`, `/linkedTestSuites`, `/linkedTestPlans`, `/automationReference`, `/getDefects`, and `/testRun/adhoc/getTestRuns/{issueKey}`.

If those plugin probes still do not expose the step grid, inspect the actual Jira browse page HTML for embedded step markup or plugin endpoint clues:

```text
./jira-context.cmd inspect-page MFD-7754 --include-html > jira-issue-page-inspection.json
```

### Installed execution

If you want the `jira-context` command to exist directly in PowerShell, install the project in editable mode from the project root:

```text
python -m pip install -e .
```

Then this form will work:

```text
jira-context fetch test-case MFD-1234
```

That is the usual packaging shape for CLIs in Python: define a console entry point in `pyproject.toml`, install the package into an environment, and let the installer create a command like `jira-context`.
For this harness, the checked-in `jira-context.cmd` wrapper is the nicer local path because it preserves the isolated `.venv` without asking people to activate anything first.

### Portable executable build

If you want a deployable Windows executable instead of copying the source tree into the workspace tool folder, build the portable bundle from this repo:

```text
python build_portable_bundle.py --workspace-root C:/path/to/other/workspace
```

That single command now does three things from scratch:

1. Installs the build dependency group automatically if PyInstaller is missing.
2. Builds `jira-context.exe`.
3. Deploys the tool and skill into the target workspace `.github` folder.

If you omit the deploy target flags, the default destination remains `C:/Dev/.github`.

You can target either form explicitly:

```text
python build_portable_bundle.py --workspace-root C:/path/to/other/workspace
python build_portable_bundle.py --deploy-root C:/path/to/other/workspace/.github
```

The deploy targets are:

- `C:/path/to/other/workspace/.github/tools/jira-context/`
- `C:/path/to/other/workspace/.github/skills/jira-context-cli/`

After deployment, run `C:/path/to/other/workspace/.github/tools/jira-context/jira-context.exe` directly.

Because the runtime path logic now detects frozen executables, the deployed `.env` and `jira-output/` locations stay rooted next to the `.exe` rather than inside a temporary extraction directory.

The deployed tool folder is intended to be code-free: the builder emits `jira-context.exe` and `jira-output/` there, and deploys the skill separately.

If you want to build without deploying, use:

```text
python build_portable_bundle.py --build-only
```

## CI build and distribution

The repository now includes a GitHub Actions workflow at `.github/workflows/build-portable-bundle.yml` that builds the Windows portable bundle on GitHub-hosted runners.

The workflow triggers on:

1. Manual runs through `workflow_dispatch`
2. Pushes to `main`

What it produces:

1. Builds `jira-context.exe` with PyInstaller on `windows-latest`
2. Stages a workspace-ready folder layout containing:
	- `.github/tools/jira-context/...`
	- `.github/skills/jira-context-cli/...`
3. Uploads a zip artifact named `jira-context-workspace-bundle-<ref>`

That zip is the teammate-facing deliverable. They should not need to clone this repo or run the build locally.

Recommended internal GitHub flow:

1. Push this repo to your internal GitHub remote.
2. Open the Actions tab and run `Build Portable Bundle`, or push to `main`.
3. Download the uploaded artifact zip from the workflow run.
4. Extract it at the target workspace root so the `.github` folder lands in place.

For release-based teammate installs, the repo also includes `.github/workflows/release-portable-bundle.yml`.
That workflow runs on tags that start with `v` and publishes the same workspace-ready zip as a GitHub release asset.

## Bootstrap installer

The recommended teammate entrypoint is `install-jira-context.ps1` in the repo root.

What it does:

1. Uses the current release by default, or a specific release tag when `-Version` is provided.
2. Resolves the workspace root from `-WorkspaceRoot` or by walking upward from the current directory until it finds `.github` or `.git`.
3. Creates `.github`, `.github/skills`, and `.github/tools` if they do not exist.
4. Replaces only the managed folders:
	- `.github/skills/jira-context-cli`
	- `.github/tools/jira-context`
5. Preserves `.github/tools/jira-context/.env` by default.
6. Preserves `jira-output` by default, unless `-CleanArtifacts` is passed.

Recommended usage from a teammate workspace root:

```powershell
Invoke-WebRequest -OutFile install-jira-context.ps1 https://github.com/FuentesJ2/jira-lens-cli/raw/main/install-jira-context.ps1; .\install-jira-context.ps1
```

Install a specific release instead of the latest one:

```powershell
Invoke-WebRequest -OutFile install-jira-context.ps1 https://github.com/FuentesJ2/jira-lens-cli/raw/v0.1.2/install-jira-context.ps1; .\install-jira-context.ps1 -Version v0.1.2
```

Target a specific workspace explicitly:

```powershell
.\install-jira-context.ps1 -WorkspaceRoot C:/Dev/my-workspace
```

For private or internal GitHub, pass a token explicitly or set `GITHUB_TOKEN` before running the installer:

```powershell
$env:GITHUB_TOKEN = "<token>"
.\install-jira-context.ps1 -GitHubBaseUrl https://github.example.com -Repository my-org/jira-lens-cli
```

For offline or pre-downloaded installs, point the installer at a local bundle zip:

```powershell
.\install-jira-context.ps1 -BundleZipPath C:/Temp/jira-context-workspace-bundle-v0.1.0.zip
```

### What `.[build]` means

The builder may bootstrap dependencies with `python -m pip install .[build]`.

- `.` means "install from the current project directory".
- `[build]` means "also install the optional dependency group named `build` from `pyproject.toml`".

In this project, that `build` group currently exists to pull in PyInstaller for executable packaging.

The earlier `-e` form meant an editable install, which is useful for development environments but is not necessary for your normal one-command deploy flow.

### Important gotcha

Do not run `python cli.py ...` from inside `src/jira_context_harness`. That bypasses the package import path and will fail on `from jira_context_harness...` imports.

If your local Python is older than the version originally assumed during scaffolding, package metadata and language features must match that reality. The current scaffold avoids `dataclass(slots=True)` so the launcher path works in older local interpreters.

Another important gotcha is output redirection: onboarding prompts are written to stderr so commands like `./jira-context.cmd fetch test-case MFD-1234 --include-raw-payload > test-case-normalized.json` can still create a clean JSON file on stdout while the raw payload JSON is written separately to `jira-output/`.

For internal Jira hosts such as `https://avjira`, the harness may need Jira Server or Data Center REST paths. The current client now tries the common issue endpoint variants automatically, starting with `/rest/api/2` for non-Cloud hosts.

If auth fails, `probe-auth` captures useful headers such as `X-Seraph-LoginReason` and `WWW-Authenticate` so you can tell the difference between bad credentials, missing login, and Jira-side auth policy issues.

For internal Jira, do not paste an Atlassian Cloud API token into the `Jira password` prompt. They are different credentials.

When you save `server_dc` with `basic` auth, the harness clears any previously saved token because that token is not used for that mode.

PowerShell `>` redirection can create UTF-16 files. That is readable, but some downstream tooling may prefer UTF-8 output instead.

Fetch normalized JSON:

```text
./jira-context.cmd fetch test-case MFD-1234 > test-case-normalized.json
```

Fetch normalized JSON and also save the raw payload JSON for optional inspection:

```text
./jira-context.cmd fetch test-case MFD-1234 --include-raw-payload > test-case-normalized.json
```

Fetch and name the normalized file and raw payload file explicitly in one command:

```text
./jira-context.cmd fetch test-case MFD-1234 --save-normalized-to ./jira-output/MFD-1234-normalized.json --save-raw-payload-to ./jira-output/fetch-test-case-MFD-1234-full-raw-payload.json
```

That raw payload file is written automatically to:

```text
./jira-output/fetch-test-case-MFD-1234-full-raw-payload.json
```

For internal Jira test cases, `fetch test-case` also enriches the normalized output with TestRay context from the documented Synapse endpoints, including `test_steps`, `linked_requirements`, `linked_test_suites`, `linked_test_plans`, `defects`, and `ad_hoc_test_runs`. When you use `--include-raw-payload`, the raw Jira issue payload and raw supplemental payloads are stored together in the saved raw payload file.

The `jira-output/` directory is the single persisted output folder here: it is git-ignored, predictable, and meant for both normalized fetches and optional raw payload captures. Right now these files use stable names and overwrite the previous fetch for the same issue and section, so the folder does not grow forever even without a cleanup command.

The raw payload file is sanitized before it is written. Keys named `avatarUrls` are stripped recursively from Jira and Synapse payloads so that avatar links never appear in normalized output, saved raw payload files, or raw-included reports.

The normalized `test_steps` and ad hoc run `steps` use stable keys such as `step_number`, `step_text`, `step_raw`, `step_html`, `expected_result_text`, `expected_result_raw`, `expected_result_html`, `requirement_keys`, and `attachments`, so the agent can consume a predictable schema while you still retain the raw plugin response when needed.

If you want only the part you care about, use `--section` on `fetch`:

```text
./jira-context.cmd fetch test-case MFD-7754 --section authored-steps
./jira-context.cmd fetch test-case MFD-7754 --section ad-hoc-runs
./jira-context.cmd fetch test-case MFD-7754 --section comments
```

The CLI now keeps these sections pure: `authored-steps` returns the current test-case steps, `ad-hoc-runs` returns ad hoc execution records, `comments` returns comments, and `links` returns linked issues.

If you add `--include-raw-payload` to a sectioned fetch, stdout still contains only the normalized section you asked for, and the matching raw section payload is written to `jira-output/`.

The `comments` section is already useful for narrative issue history such as reviewer notes, bug discovery notes, repro confirmations, requirement-ID update notes, and sub-task keys mentioned in comments. It does not currently include Jira changelog events such as every status transition or field edit.

The normalized `links` section now carries linked issue semantics such as `issue_kind`, `issue_type`, `status`, and `priority`, which makes linked problem reports easier to reason about without a second fetch.

If you want to fetch a linked problem report directly, use the dedicated issue kind:

```text
./jira-context.cmd fetch problem-report MFD-8100 --include-raw-payload
```

The active workspace skill lives under the deployed workspace `.github/skills/jira-context-cli/` folder.
This repository also keeps a mirror copy at `.github/skills/jira-context-cli/` so skill revisions can stay with the harness.
For the surrounding `Dev-Sidecar` workspace, prefer a workspace-root `.github/copilot-instructions.md` so Copilot context is provided by the live workspace rather than by the simulated deployment tree inside this source repository.

Render a quick human-readable summary:

```text
./jira-context.cmd fetch test-case MFD-1234 --format text
```