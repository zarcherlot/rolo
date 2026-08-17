$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

uv build --wheel
$wheel = Get-ChildItem -LiteralPath (Join-Path $projectRoot "dist") -Filter "rolo-*.whl" |
    Sort-Object LastWriteTimeUtc |
    Select-Object -Last 1

if ($null -eq $wheel) {
    throw "uv build did not produce a rolo wheel"
}

uv run robotctl bundle build --wheel $wheel.FullName
