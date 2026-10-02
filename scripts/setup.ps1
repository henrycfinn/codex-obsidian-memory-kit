[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$KnowledgeRoot,
    [switch]$SkipSkillInstall
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $KnowledgeRoot).Path
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    throw "KnowledgeRoot must be an existing directory: $KnowledgeRoot"
}

$kitRoot = Split-Path -Parent $PSScriptRoot
$librarianRoot = Join-Path $kitRoot 'librarian'
$skillSource = Join-Path $librarianRoot 'skills\codex-librarian'
if (-not (Test-Path -LiteralPath (Join-Path $librarianRoot 'scripts\codex_librarian.py') -PathType Leaf)) {
    throw 'The bundled Librarian adapter is missing. Refresh the kit checkout.'
}

[Environment]::SetEnvironmentVariable('CODEX_LIBRARIAN_REPO', $librarianRoot, 'User')
if (-not $SkipSkillInstall) {
    $skillDestination = Join-Path $env:USERPROFILE '.codex\skills\codex-librarian'
    New-Item -ItemType Directory -Path (Split-Path -Parent $skillDestination) -Force | Out-Null
    Copy-Item -LiteralPath $skillSource -Destination $skillDestination -Recurse -Force
}

Write-Host "Configured CODEX_LIBRARIAN_REPO for this user."
Write-Host "Canonical vault (unchanged): $root"
Write-Host 'Restart Codex, then use the Codex Librarian workflow for durable vault writes.'

