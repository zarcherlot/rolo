param(
    [ValidateSet("setup", "check", "serve", "test", "lint")]
    [string]$Action = "check"
)

$ErrorActionPreference = "Stop"
$Workspace = Split-Path -Parent $PSScriptRoot
Push-Location $Workspace
try {
    switch ($Action) {
        "setup" {
            uv sync --dev
            uv run robotctl schema export
        }
        "check" { uv run robotctl doctor }
        "serve" { uv run robotctl serve }
        "test" { uv run pytest }
        "lint" { uv run ruff check . }
    }
}
finally {
    Pop-Location
}
