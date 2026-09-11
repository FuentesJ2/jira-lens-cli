[CmdletBinding()]
param(
    [string]$WorkspaceRoot,
    [string]$Version,
    [string]$Repository = "FuentesJ2/jira-lens-cli",
    [string]$GitHubBaseUrl = "https://github.com",
    [string]$ApiBaseUrl,
    [string]$Token = $env:GITHUB_TOKEN,
    [string]$BundleZipPath,
    [switch]$CleanArtifacts,
    [switch]$ForceConfigReset
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-InstallStep {
    param([string]$Message)

    Write-Host "==> $Message"
}

function Resolve-InstallerWorkspaceRoot {
    param([string]$RequestedRoot)

    if ($RequestedRoot) {
        if (-not (Test-Path -LiteralPath $RequestedRoot -PathType Container)) {
            throw "Workspace root does not exist: $RequestedRoot"
        }

        return (Resolve-Path -LiteralPath $RequestedRoot).Path
    }

    $start = (Get-Location).Path
    $candidate = $start

    while ($true) {
        if (Test-Path -LiteralPath (Join-Path $candidate ".github")) {
            return $candidate
        }

        if (Test-Path -LiteralPath (Join-Path $candidate ".git")) {
            return $candidate
        }

        $parent = Split-Path -Path $candidate -Parent
        if (-not $parent -or $parent -eq $candidate) {
            return $start
        }

        $candidate = $parent
    }
}

function Resolve-ApiRoot {
    param(
        [string]$ExplicitApiBaseUrl,
        [string]$BaseUrl
    )

    if ($ExplicitApiBaseUrl) {
        return $ExplicitApiBaseUrl.TrimEnd("/")
    }

    $trimmedBaseUrl = $BaseUrl.TrimEnd("/")
    if ($trimmedBaseUrl -eq "https://github.com") {
        return "https://api.github.com"
    }

    return "$trimmedBaseUrl/api/v3"
}

function New-TempDirectory {
    $path = Join-Path ([System.IO.Path]::GetTempPath()) ("jira-context-install-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function Get-ReleaseAsset {
    param(
        [string]$ResolvedApiBaseUrl,
        [string]$ResolvedRepository,
        [string]$RequestedVersion,
        [string]$AuthToken
    )

    $headers = @{
        "Accept" = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
    }

    if ($AuthToken) {
        $headers["Authorization"] = "Bearer $AuthToken"
    }

    $releaseUri = if ($RequestedVersion) {
        "$ResolvedApiBaseUrl/repos/$ResolvedRepository/releases/tags/$RequestedVersion"
    }
    else {
        "$ResolvedApiBaseUrl/repos/$ResolvedRepository/releases/latest"
    }

    try {
        $release = Invoke-RestMethod -Uri $releaseUri -Headers $headers -Method Get
    }
    catch {
        throw "Failed to read release metadata from $releaseUri. If this is a private or internal repository, provide a token with -Token or set GITHUB_TOKEN. $($_.Exception.Message)"
    }

    $asset = $release.assets | Where-Object { $_.name -like "jira-context-workspace-bundle-*.zip" } | Select-Object -First 1
    if (-not $asset) {
        throw "No workspace bundle zip asset was found on release '$($release.tag_name)'."
    }

    return [pscustomobject]@{
        TagName = $release.tag_name
        AssetName = $asset.name
        DownloadUrl = $asset.browser_download_url
    }
}

function Save-BundleZip {
    param(
        [string]$DestinationPath,
        [pscustomobject]$ReleaseAsset,
        [string]$AuthToken
    )

    $headers = @{}
    if ($AuthToken) {
        $headers["Authorization"] = "Bearer $AuthToken"
    }

    Invoke-WebRequest -Uri $ReleaseAsset.DownloadUrl -Headers $headers -OutFile $DestinationPath
}

function Preserve-InstallState {
    param(
        [string]$ExistingToolRoot,
        [string]$StashRoot,
        [switch]$PreserveOutput,
        [switch]$PreserveConfig
    )

    if (-not (Test-Path -LiteralPath $ExistingToolRoot -PathType Container)) {
        return
    }

    New-Item -ItemType Directory -Path $StashRoot -Force | Out-Null

    $configPath = Join-Path $ExistingToolRoot ".env"
    if ($PreserveConfig -and (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        Copy-Item -LiteralPath $configPath -Destination (Join-Path $StashRoot ".env") -Force
    }

    $jiraOutputPath = Join-Path $ExistingToolRoot "jira-output"
    if ($PreserveOutput -and (Test-Path -LiteralPath $jiraOutputPath -PathType Container)) {
        Copy-Item -LiteralPath $jiraOutputPath -Destination $StashRoot -Recurse -Force
    }
}

function Restore-InstallState {
    param(
        [string]$StashRoot,
        [string]$ToolRoot,
        [switch]$RestoreConfig,
        [switch]$RestoreOutput
    )

    if (-not (Test-Path -LiteralPath $StashRoot -PathType Container)) {
        return
    }

    $configPath = Join-Path $StashRoot ".env"
    if ($RestoreConfig -and (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        Copy-Item -LiteralPath $configPath -Destination (Join-Path $ToolRoot ".env") -Force
    }

    $jiraOutputPath = Join-Path $StashRoot "jira-output"
    if ($RestoreOutput -and (Test-Path -LiteralPath $jiraOutputPath -PathType Container)) {
        Copy-Item -LiteralPath $jiraOutputPath -Destination $ToolRoot -Recurse -Force
    }
}

$resolvedWorkspaceRoot = Resolve-InstallerWorkspaceRoot -RequestedRoot $WorkspaceRoot
$resolvedApiBaseUrl = Resolve-ApiRoot -ExplicitApiBaseUrl $ApiBaseUrl -BaseUrl $GitHubBaseUrl
$tempRoot = New-TempDirectory

try {
    Write-InstallStep "Using workspace root $resolvedWorkspaceRoot"

    $bundleZip = if ($BundleZipPath) {
        if (-not (Test-Path -LiteralPath $BundleZipPath -PathType Leaf)) {
            throw "Bundle zip was not found: $BundleZipPath"
        }

        (Resolve-Path -LiteralPath $BundleZipPath).Path
    }
    else {
        $releaseAsset = Get-ReleaseAsset -ResolvedApiBaseUrl $resolvedApiBaseUrl -ResolvedRepository $Repository -RequestedVersion $Version -AuthToken $Token
        $downloadPath = Join-Path $tempRoot $releaseAsset.AssetName
        Write-InstallStep "Downloading $($releaseAsset.AssetName) from release $($releaseAsset.TagName)"
        Save-BundleZip -DestinationPath $downloadPath -ReleaseAsset $releaseAsset -AuthToken $Token
        $downloadPath
    }

    $extractRoot = Join-Path $tempRoot "extracted"
    Write-InstallStep "Expanding workspace bundle"
    Expand-Archive -LiteralPath $bundleZip -DestinationPath $extractRoot -Force

    $sourceGithubRoot = Join-Path $extractRoot ".github"
    if (-not (Test-Path -LiteralPath $sourceGithubRoot -PathType Container)) {
        throw "The bundle zip does not contain a .github folder at its root."
    }

    $destinationGithubRoot = Join-Path $resolvedWorkspaceRoot ".github"
    $destinationSkillsRoot = Join-Path $destinationGithubRoot "skills"
    $destinationToolsRoot = Join-Path $destinationGithubRoot "tools"
    $destinationSkill = Join-Path $destinationSkillsRoot "jira-context-cli"
    $destinationTool = Join-Path $destinationToolsRoot "jira-context"

    $sourceSkill = Join-Path $sourceGithubRoot "skills\jira-context-cli"
    $sourceTool = Join-Path $sourceGithubRoot "tools\jira-context"

    if (-not (Test-Path -LiteralPath $sourceSkill -PathType Container)) {
        throw "The bundle zip is missing .github/skills/jira-context-cli."
    }

    if (-not (Test-Path -LiteralPath $sourceTool -PathType Container)) {
        throw "The bundle zip is missing .github/tools/jira-context."
    }

    Write-InstallStep "Ensuring workspace .github folders exist"
    New-Item -ItemType Directory -Path $destinationSkillsRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $destinationToolsRoot -Force | Out-Null

    $stashRoot = Join-Path $tempRoot "preserved"
    Preserve-InstallState -ExistingToolRoot $destinationTool -StashRoot $stashRoot -PreserveOutput:(-not $CleanArtifacts) -PreserveConfig:(-not $ForceConfigReset)

    Write-InstallStep "Installing skill files"
    Remove-Item -LiteralPath $destinationSkill -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $sourceSkill -Destination $destinationSkillsRoot -Recurse -Force

    Write-InstallStep "Installing tool files"
    Remove-Item -LiteralPath $destinationTool -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $sourceTool -Destination $destinationToolsRoot -Recurse -Force

    Restore-InstallState -StashRoot $stashRoot -ToolRoot $destinationTool -RestoreOutput:(-not $CleanArtifacts) -RestoreConfig:(-not $ForceConfigReset)

    Write-Host ""
    Write-Host "Install complete"
    Write-Host "WorkspaceRoot : $resolvedWorkspaceRoot"
    Write-Host "SkillPath      : $destinationSkill"
    Write-Host "ToolPath       : $destinationTool"
    if ($BundleZipPath) {
        Write-Host "Source         : $bundleZip"
    }
    elseif ($releaseAsset) {
        Write-Host "ReleaseTag     : $($releaseAsset.TagName)"
        Write-Host "AssetName      : $($releaseAsset.AssetName)"
    }
}
finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}