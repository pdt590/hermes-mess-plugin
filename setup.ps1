param(
    [string]$HermesPython = $env:HERMES_PYTHON,
    [string]$HermesHome = $env:HERMES_HOME
)
$ErrorActionPreference = 'Stop'
if (-not $HermesHome) {
    $HermesHome = Join-Path $env:LOCALAPPDATA 'hermes'
}
if (-not $HermesPython) {
    $candidates = @(
        (Join-Path $HermesHome 'hermes-agent\venv\Scripts\python.exe'),
        (Join-Path $HermesHome 'hermes-agent\.venv\Scripts\python.exe'),
        (Join-Path $HermesHome 'venv\Scripts\python.exe'),
        (Join-Path $HermesHome '.venv\Scripts\python.exe')
    )
    $HermesPython = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $HermesPython) {
    throw 'Hermes Python not found. Use -HermesPython <path-to-Hermes-python.exe>.'
}
& $HermesPython (Join-Path $PSScriptRoot 'scripts\install.py') --hermes-home $HermesHome
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
