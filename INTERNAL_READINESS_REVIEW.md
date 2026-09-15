# Internal Security, Privacy, and Compliance Readiness Review

Project: jira-context-harness CLI  
Reviewer role: Senior secure-code reviewer (internal readiness)  
Date: 2026-09-12

## Executive trust verdict
This CLI is **conditionally trustworthy for internal use** only if release gates are enforced before broad rollout. The code shows several positive controls (input encoding, no shell command execution in runtime paths, and some payload sanitization), but there are material enterprise risks in the install/update trust chain and sensitive-data handling. Most importantly, bootstrap and artifact installation currently lack integrity verification controls, and credentials are persisted in plaintext local configuration. With targeted remediation and release gates, internal deployment can be justified.

## Findings table

| ID | Severity | Category | Evidence location | Risk summary | Exploit path | Recommended fix | Owner suggestion | ETA suggestion |
|---|---|---|---|---|---|---|---|---|
| H-01 | High | Supply chain / installer trust boundary | README.md:54, README.md:258, install-jira-context.ps1:104, install-jira-context.ps1:134, install-jira-context.ps1:209, install-jira-context.ps1:241, install-jira-context.ps1:246 | **Confirmed.** Installer bootstrap pattern downloads and executes installer from moving branch (`raw/main`), then downloads/extracts/copies release artifact without checksum/signature validation. This is a direct path to unintended code deployment. | If GitHub repo/release asset or delivery path is compromised, users run altered installer and receive malicious `jira-context.exe` into workspace tool path. | 1) Publish SHA-256 checksums and verify before extract/install. 2) Sign installer and binary (Authenticode) and verify signatures in script. 3) Prefer pinned release-tag installer URLs over `raw/main`. 4) Enforce repository/host allowlist in installer. | Release engineering + DevSecOps | Immediate (block next release until fixed) |
| M-01 | Medium | Secrets and credential safety | src/jira_context_harness/config.py:69, src/jira_context_harness/config.py:70, src/jira_context_harness/config.py:101, src/jira_context_harness/config.py:102, src/jira_context_harness/config.py:110, install-jira-context.ps1:151, install-jira-context.ps1:153, install-jira-context.ps1:176, install-jira-context.ps1:238, install-jira-context.ps1:248 | **Confirmed.** Password/token values are saved in plaintext `.env` and preserved across upgrades by default. `.gitignore` prevents commit, but at-rest local exposure remains. | Local user/process, endpoint malware, backups, or shared workspace access can read `.env` credentials. | 1) Move secrets to Windows Credential Manager/DPAPI. 2) If file fallback remains, enforce restrictive ACL (`icacls`) and warn user. 3) Store only currently required secret for selected auth mode. | CLI maintainers + endpoint security | 1 week |
| M-02 | Medium | Privacy / data minimization | src/jira_context_harness/cli.py:116, src/jira_context_harness/cli.py:126, src/jira_context_harness/cli.py:328, src/jira_context_harness/cli.py:347, src/jira_context_harness/jira_client.py:321, src/jira_context_harness/jira_client.py:322, src/jira_context_harness/jira_client.py:550, src/jira_context_harness/jira_client.py:554, src/jira_context_harness/models.py:123, src/jira_context_harness/models.py:124, src/jira_context_harness/models.py:134, src/jira_context_harness/models.py:136 | **Confirmed.** Raw payload and full HTML capture options persist potentially sensitive issue content. Sanitization only strips `avatarUrls`, which is insufficient for enterprise data-minimization expectations. | User runs `--include-raw-payload`, `--save-raw-payload-to`, or `inspect-page --include-html`; sensitive comments/custom fields/session artifacts can be written and later shared or retained. | 1) Introduce field-level redaction policy (allowlist-first). 2) Add `--redact-sensitive` default-on for persisted outputs. 3) Add retention/expiry policy for `jira-output`. | CLI maintainers + privacy/compliance | 1-2 weeks |
| M-03 | Medium | Transport and API security | src/jira_context_harness/config.py:13, src/jira_context_harness/config.py:83, src/jira_context_harness/jira_client.py:117, src/jira_context_harness/jira_client.py:240, src/jira_context_harness/jira_client.py:296, src/jira_context_harness/jira_client.py:389, src/jira_context_harness/jira_client.py:425 | **Confirmed.** Default host is HTTPS, but there is no explicit guard preventing `http://` base URLs while sending Authorization headers. | Misconfigured host over HTTP exposes Basic/Bearer credentials on the network. | Enforce HTTPS scheme by default and fail closed; require explicit override flag (for controlled lab use only) with prominent warning. | CLI maintainers | 1 week |
| M-04 | Medium | Dependency and build-chain integrity | pyproject.toml:1, pyproject.toml:2, pyproject.toml:12, .github/workflows/build-portable-bundle.yml:29, .github/workflows/release-portable-bundle.yml:28, .github/workflows/build-portable-bundle.yml:18, .github/workflows/build-portable-bundle.yml:21, .github/workflows/release-portable-bundle.yml:17, .github/workflows/release-portable-bundle.yml:20, .github/workflows/release-portable-bundle.yml:59 | **Confirmed.** Build dependencies are resolved from network without lockfile/hash pinning; GitHub Actions use version tags, not immutable commit SHAs. | Compromised/upstream package or action update can influence build outputs and release artifacts. | 1) Add pinned lock/constraints with hashes for build deps. 2) Pin workflow actions to commit SHAs. 3) Add dependency/SBOM scanning workflow and release attestation. | DevSecOps + build maintainers | 2 weeks |
| L-01 | Low | Operational hardening / data retention | install-jira-context.ps1:10, install-jira-context.ps1:11, install-jira-context.ps1:137, install-jira-context.ps1:157, install-jira-context.ps1:238, install-jira-context.ps1:248 | **Confirmed.** Installer preserves `.env` and `jira-output` by default, which is operationally convenient but increases stale sensitive-data retention risk. | Old artifacts accumulate and may be exposed during workspace sharing, support collection, or endpoint compromise. | Add explicit retention policy and cleanup mode as default-safe option (opt-in preserve). | CLI maintainers | 2-3 weeks |
| L-02 | Low | Validation and release governance | tests/test_cli.py:730, tests/test_cli.py:754, tests/test_jira_client.py:410, tests/test_jira_client.py:438 | **Needs validation.** Security-relevant tests exist (prompt behavior and avatar URL sanitization), but local runtime validation was incomplete due environment drift; one observed failure occurred in partial Python 3.9 run. | Regressions can ship if local and CI gates are not interpreter-matrix aligned and required for release. | 1) Require passing tests in CI for supported versions. 2) Add explicit security test cases for HTTPS enforcement, redaction breadth, and installer integrity checks. | QA + maintainers | Immediate for gate definition |

## Trust evidence summary
Concrete strengths observed in the codebase:

1. Runtime CLI paths do not execute shell commands with user input; subprocess use is isolated to the build script and uses argument lists (no `shell=True`) in build_portable_bundle.py:96 and build_portable_bundle.py:134.
2. Request construction uses URL-safe encoding for issue keys and query parameters (`parse.quote`, `parse.urlencode`) in src/jira_context_harness/jira_client.py:223, src/jira_context_harness/jira_client.py:449, and src/jira_context_harness/jira_client.py:457.
3. Sensitive onboarding prompts use non-echo secret entry via `getpass` in src/jira_context_harness/cli.py:469.
4. Output separation reduces accidental terminal leakage: raw payload is written to file while normalized output remains primary stdout behavior in src/jira_context_harness/cli.py:586 and src/jira_context_harness/cli.py:603.
5. `.gitignore` includes `.env` and `jira-output` to reduce accidental secret/artifact commits in .gitignore:12 and .gitignore:13.
6. Recursive payload sanitization removes `avatarUrls` in src/jira_context_harness/jira_client.py:550 and src/jira_context_harness/jira_client.py:554, with tests at tests/test_jira_client.py:410 and tests/test_jira_client.py:438.
7. Workflow permissions are constrained at job level (`contents: read` for build) in .github/workflows/build-portable-bundle.yml:9 and .github/workflows/build-portable-bundle.yml:10.

## Compliance and privacy due diligence summary

### Covered
1. Basic access control flow exists via Jira auth requirements and missing-setting checks in src/jira_context_harness/config.py:38.
2. Some logging hygiene exists by routing prompts/status to stderr in CLI flows (for cleaner stdout JSON use).
3. Basic secret commit prevention exists via `.gitignore`.

### Partially covered
1. Data minimization is partial: only `avatarUrls` are redacted, while broader Jira/Test artifacts may still contain sensitive business and user data.
2. Auditability is partial: operational status messages exist, but there is no structured audit logging policy or retention standard.
3. Vulnerability management is partial: tests exist, but no repo evidence of dependency scanning, SCA gates, or signed provenance.

### Missing or not evidenced in repository
1. Artifact integrity verification (checksums/signatures) in installer/update path.
2. Secret-at-rest protection beyond plaintext `.env`.
3. Formal retention controls for persisted output artifacts.
4. CI security gates for dependency risk, integrity attestations, and policy checks.

## Remediation roadmap

### Immediate actions (High findings)
1. Block release approval until installer/artifact integrity validation is implemented (H-01).
2. Replace README bootstrap command to version-pinned installer path and document verification steps.
3. Add release gate requiring checksum/signature verification to pass in CI.

### Near-term actions (Medium findings)
1. Implement secure credential storage (Windows Credential Manager/DPAPI) with plaintext fallback explicitly discouraged.
2. Enforce HTTPS-only base URL by default.
3. Expand redaction/minimization policy for raw payload and HTML outputs.
4. Introduce dependency lock/hash strategy and pin GitHub Actions to immutable SHAs.

### Backlog hardening (Low findings)
1. Add configurable retention lifecycle tooling for `jira-output` and config artifacts.
2. Add policy docs for supportability: secure logging, artifact handling, and incident triage workflows.
3. Expand test matrix and security-focused regression tests.

## Approval recommendation
**Approve with conditions**

Release gates required before broad internal deployment:

1. H-01 remediations are implemented and verified (installer and artifact integrity checks).
2. Medium findings M-01 through M-04 have approved remediation plans with committed owner and due dates; at minimum, M-03 HTTPS enforcement must be implemented before release.
3. CI must enforce passing tests and include at least one dependency/integrity security gate.
4. Privacy/data-handling guidance for raw payload and HTML artifacts is documented and distributed to users.

## Validation notes and limitations
1. Static code review was completed across CLI, client, config, installer, build, workflow, and tests.
2. Local runtime test validation was partially blocked by interpreter/environment mismatch (`.venv` broken interpreter path and no local Python 3.11). A partial Python 3.9 run showed at least one failure in test_cli.CliOutputTests.test_configure_updates_saved_settings before timing out.
3. Findings marked **Needs validation** include explicit validation follow-ups and should be closed before final approval.

---

## TLDR
- Conditional trust is justified only after installer/artifact integrity controls are added.
- Highest risk is the bootstrap/update trust chain (download/execute without checksum/signature validation).
- Medium risks include plaintext local credential storage, broad raw artifact persistence, HTTP misconfiguration exposure, and unpinned build-chain dependencies/actions.
- Positive controls exist: input encoding, no runtime shell execution with user input, `.gitignore` hygiene, and tested avatar URL sanitization.
- Recommendation: Approve with conditions and enforce concrete release gates before broad internal rollout.
