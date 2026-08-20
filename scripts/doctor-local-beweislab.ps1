param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$DoctorRoot = Join-Path $ProjectRoot ".muclegal-ui\doctor"
New-Item -ItemType Directory -Force -Path $DoctorRoot | Out-Null

& $Python --version
& $Python -c "import importlib.metadata as m; print('Playwright:',m.version('playwright')); print('Pillow:',m.version('Pillow')); print('psutil:',m.version('psutil'))"
& $Python -c "from pathlib import Path; p=Path(r'$DoctorRoot')/'write-test.tmp'; p.write_text('ok'); p.unlink(); print('Schreibrechte: OK')"
& $Python -c "from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); page=b.new_page(); page.set_content('<main>Doctor</main>'); page.screenshot(path=str(Path(r'$DoctorRoot')/'doctor.png')); print('Chromium:',b.version,'webdriver=',page.evaluate('navigator.webdriver')); b.close(); p.stop()"
$Drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($ProjectRoot).Substring(0,1))
Write-Host ("Freier Speicher: {0:N2} GB" -f ($Drive.Free / 1GB))
$Listening = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Listening) {
    Write-Host "Port $Port ist bereits belegt."
} else {
    Write-Host "Port $Port ist frei."
}
Write-Host "Doctor abgeschlossen; es wurde keine öffentliche URL erfasst."

