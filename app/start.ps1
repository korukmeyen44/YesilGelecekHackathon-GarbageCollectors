# Repo kokune gecerek yerel operasyon panelini baslatir. Python 3.10+ gerekir.
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    python -m app.server @args
}
finally {
    Pop-Location
}
