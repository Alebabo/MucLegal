param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }

& $Python --version
& $Python -c "import fastapi, PIL, playwright, psutil, uvicorn; print('Abhängigkeiten: OK')"
if ($LASTEXITCODE -ne 0) {
    throw 'Abhängigkeiten fehlen. Bitte zuerst: python -m pip install -e ".[demo]"'
}
& $Python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); print('Chromium:', b.version); b.close(); p.stop()"
if ($LASTEXITCODE -ne 0) {
    throw "Chromium fehlt. Bitte ausführen: python -m playwright install chromium"
}
$Drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($ProjectRoot).Substring(0,1))
if ($Drive.Free -lt 2GB) {
    throw "Weniger als 2 GB freier Speicher. Ein Beweislauf wird nicht gestartet."
}
Write-Host "Lokale Ablage: $ProjectRoot\.muclegal-ui"
Write-Host "BeweisLab: http://127.0.0.1:$Port/beweis-labor"
Set-Location -LiteralPath $ProjectRoot
& $Python -m uvicorn app:app --host 127.0.0.1 --port $Port

