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
$uninstallScript = Join-Path $PSScriptRoot 'scripts\uninstall.py'
if (Test-Path -LiteralPath $HermesPython -PathType Leaf) {
    $HermesPython = (Resolve-Path -LiteralPath $HermesPython).Path
}
if (Test-Path -LiteralPath $HermesHome -PathType Container) {
    $HermesHome = (Resolve-Path -LiteralPath $HermesHome).Path
    # Release the launcher's own working-directory handle before archiving a plugin
    # that may contain the directory from which this command was started.
    Set-Location -LiteralPath $HermesHome
    [System.Environment]::CurrentDirectory = $HermesHome
}
& $HermesPython $uninstallScript --hermes-home $HermesHome
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
