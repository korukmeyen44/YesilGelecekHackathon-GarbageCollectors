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
if ($Upload -and $Environment[0] -eq 'esp32_gateway') {
    & $toolPython (Join-Path $PSScriptRoot 'configure_gateway.py') --check
    if ($LASTEXITCODE -ne 0) { throw 'Gateway ag ayarlari eksik; once configure_gateway.py calistirin.' }
}
$previousCoreDir = $env:PLATFORMIO_CORE_DIR
$previousPackagesDir = $env:PLATFORMIO_PACKAGES_DIR
try {
    $env:PLATFORMIO_CORE_DIR = Join-Path $firmwareRoot '.tools/platformio'
    # GCC 8 on Windows cannot reliably open headers beyond MAX_PATH.
    $packagesDirectory = Join-Path (Split-Path -Parent $firmwareRoot) '.pio-packages'
    New-Item -ItemType Directory -Force -Path $packagesDirectory | Out-Null
    $shortPackages = & $toolPython (Join-Path $PSScriptRoot 'short_path.py') $packagesDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Paket yolu hazirlanamadi.' }
    $env:PLATFORMIO_PACKAGES_DIR = $shortPackages.Trim()
    $pioArguments = @('-m', 'platformio', 'run', '--project-dir', $firmwareRoot)
    foreach ($targetEnvironment in $Environment) { $pioArguments += @('-e', $targetEnvironment) }
    if ($Upload) { $pioArguments += @('--target', 'upload', '--upload-port', $Port) }
    & $toolPython @pioArguments
    if ($LASTEXITCODE -ne 0) { throw 'Derleme veya yukleme basarisiz.' }
}
finally {
    $env:PLATFORMIO_CORE_DIR = $previousCoreDir
    $env:PLATFORMIO_PACKAGES_DIR = $previousPackagesDir
}

