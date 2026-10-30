param(
    [ValidateSet('uno_node_1', 'uno_node_2', 'uno_node_3', 'esp32_gateway')]
    [string[]]$Environment = @('uno_node_1', 'esp32_gateway'),
    [switch]$Setup,
    [switch]$Upload,
    [string]$Port
)
$ErrorActionPreference = 'Stop'
$firmwareRoot = Split-Path -Parent $PSScriptRoot
$toolPython = Join-Path $firmwareRoot '.tools/venv/Scripts/python.exe'
if ($Upload -and ($Environment.Count -ne 1 -or -not $Port)) {
    throw 'Yukleme icin tek Environment ve Port belirtin.'
}
if (-not (Test-Path -LiteralPath $toolPython)) {
    python -m venv (Join-Path $firmwareRoot '.tools/venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python ortami olusturulamadi.' }
    $Setup = $true
}
if ($Setup) {
    & $toolPython -m pip install -r (Join-Path $firmwareRoot 'requirements-dev.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Gelistirme araclari indirilemedi.' }
}
$previousCoreDir = $env:PLATFORMIO_CORE_DIR
try {
    $env:PLATFORMIO_CORE_DIR = Join-Path $firmwareRoot '.tools/platformio'
    $pioArguments = @('-m', 'platformio', 'run', '--project-dir', $firmwareRoot)
    foreach ($targetEnvironment in $Environment) { $pioArguments += @('-e', $targetEnvironment) }
    if ($Upload) { $pioArguments += @('--target', 'upload', '--upload-port', $Port) }
    & $toolPython @pioArguments
    if ($LASTEXITCODE -ne 0) { throw 'Derleme veya yukleme basarisiz.' }
}
finally {
    $env:PLATFORMIO_CORE_DIR = $previousCoreDir
}

