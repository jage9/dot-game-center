<#
.SYNOPSIS
    Bump version, commit, tag, and push to trigger a GitHub Actions release build.

.DESCRIPTION
    Updates the version in pyproject.toml, commits that change, tags the commit,
    and pushes. GitHub Actions picks up the tag and builds + uploads the release.

.PARAMETER Version
    New version string, e.g. "0.3"

.EXAMPLE
    .\release.ps1 0.3
#>
param(
    [Parameter(Mandatory)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$tag = "v$Version"

# Guard against re-running after a partial failure.
if (git tag -l $tag) {
    Write-Error "Tag $tag already exists locally. If a previous run failed, delete it with: git tag -d $tag"
    exit 1
}

# --- Update pyproject.toml ---
$toml = Get-Content "pyproject.toml" -Raw
$toml = $toml -replace '(?m)^version = ".*"', "version = `"$Version`""
Set-Content "pyproject.toml" $toml -NoNewline
Write-Host "pyproject.toml -> $Version"

# --- Commit, tag, push ---
git add pyproject.toml
git commit -m "Bump version to $Version

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

git tag $tag
Write-Host "Tagged $tag"

git push
git push origin $tag
Write-Host ""
Write-Host "Pushed $tag. GitHub Actions will build and publish the release."
Write-Host "Monitor at: https://github.com/$(git remote get-url origin | Select-String '(?<=github\.com[:/])[\w.-]+/[\w.-]+(?=\.git|$)' | ForEach-Object { $_.Matches.Value })/actions"
