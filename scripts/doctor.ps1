[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$KnowledgeRoot
)

$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path -Parent $PSScriptRoot
$adapter = Join-Path $kitRoot 'librarian\scripts\codex_librarian.py'
if (-not (Test-Path -LiteralPath $adapter -PathType Leaf)) {
    throw 'The bundled Librarian adapter is missing.'
}
python $adapter --knowledge-root $KnowledgeRoot doctor

