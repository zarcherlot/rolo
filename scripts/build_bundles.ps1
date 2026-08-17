$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

uv build --wheel
$wheel = Get-ChildItem -LiteralPath (Join-Path $projectRoot "dist") -Filter "robot_loop-*.whl" |
    Sort-Object LastWriteTimeUtc |
    Select-Object -Last 1

if ($null -eq $wheel) {
    throw "uv build did not produce a robot_loop wheel"
}

uv run robotctl bundle build --robot robot_a --robot robot_b --wheel $wheel.FullName
