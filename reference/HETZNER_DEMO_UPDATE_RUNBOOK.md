# Hetzner-Demo: Deployment, Aktualisierung und Rollback

Stand: 24.08.2026. Dieses Runbook beschreibt die temporäre, passwortgeschützte
Hackathon-Demo. Es ist kein Produktions- oder Mandantensystem.

## 1. Zielzustand

| Bestandteil | Pfad oder Dienst |
| --- | --- |
| Öffentlicher Reverse Proxy | Caddy auf Port 80/443 |
| Frontend | `muclegal-frontend.service`, nur `127.0.0.1:4173` |
| Backend | `muclegal-backend.service`, nur `127.0.0.1:8000` |
| Aktive Version | Symlink `/opt/muclegal/current` |
| Unveränderliche Releases | `/opt/muclegal/releases/<release-id>` |
| Python-Umgebung | `/opt/muclegal/venv` |
| Playwright-Browser | `/opt/muclegal/playwright` |
| Isolierter Demo-Speicher | `/var/lib/muclegal-demo` |
| Servergeheimnisse | `/etc/muclegal/muclegal.env`, Modus `600`, Eigentümer `root` |
| Caddy-Konfiguration | `/etc/caddy/Caddyfile` |

`/var/lib/muclegal-demo` und `/etc/muclegal/muclegal.env` liegen absichtlich
außerhalb jedes Releases. Ein Codeupdate darf weder Beweisdaten noch Schlüssel
überschreiben. Lokale `.env`-Dateien, `.muclegal-ui/`, SQLite-Dateien, WARC-Dateien,
Screenshots und ZIP-Beweispakete werden nie hochgeladen.

Die öffentliche Demo ist mit Caddy Basic Auth geschützt. Benutzername, Passwort und
API-Schlüssel gehören nicht in Git, dieses Dokument, Kommandozeilenargumente, URLs
oder Screenshots.

## 2. Voraussetzungen

- Aktiver Branch: `agent/live-url-ui`.
- Der zu veröffentlichende Stand ist vollständig committed und auf `origin` gepusht.
- SSH-Zugang zum Server funktioniert mit dem lokalen Deployment-Schlüssel.
- Auf dem Server sind Python 3.11+, Node 22.12+ und Caddy installiert.
- Die Dienste und Pfade aus Abschnitt 1 existieren bereits.
- Die zeitliche Begrenzung der Demo ist bewusst geprüft:

```powershell
ssh -i $DeployKey "root@$ServerIp" "systemctl list-timers muclegal-demo-expire.timer --no-pager"
```

Der Timer stoppt die Webdienste nach dem Demozeitraum. Der Hetzner-Server bleibt
danach kostenpflichtig, bis er in der Hetzner-Konsole gelöscht wird.

## 3. Lokalen Stand prüfen und pushen

Zuerst dürfen keine fremden oder ungewollten Änderungen übergangen werden:

```powershell
git status --short
git branch --show-current
git remote -v
git fetch origin
```

Vor dem Commit mindestens die verbindlichen Prüfungen ausführen:

```powershell
python -m compileall -q muclegal app.py
python -m pytest -q

Push-Location frontend
npm run test:minimal
npm run typecheck
npm run build
Pop-Location
```

Danach nur die beabsichtigten Dateien stagen, den Index prüfen und pushen:

```powershell
git add <beabsichtigte-dateien>
git diff --cached --check
git diff --cached --stat
git commit -m "<aussagekräftige Nachricht>"
git push origin agent/live-url-ui
```

Der Release wird erst aus dem gepushten Commit gebaut. Dadurch entspricht der
Serverstand exakt einem auf GitHub nachvollziehbaren SHA und nicht einem zufälligen
Arbeitsbaum.

## 4. Release-Archiv aus dem Git-Commit erzeugen

Die folgenden Variablen gelten nur für die aktuelle PowerShell-Sitzung. Der konkrete
Pfad zum privaten SSH-Schlüssel bleibt lokal:

```powershell
$ServerIp = "5.75.146.212"
$DeployKey = "C:\Pfad\zum\muclegal_hetzner_ed25519"
$Commit = git rev-parse HEAD
$ShortCommit = git rev-parse --short HEAD
$Release = "$(Get-Date -Format 'yyyyMMdd-HHmmss')-$ShortCommit"
$Archive = Join-Path ([IO.Path]::GetTempPath()) "muclegal-$Release.tar.gz"
```

Nur Laufzeitdateien aus dem Commit archivieren. `git archive` nimmt weder ignorierte
Dateien noch lokale Änderungen auf:

```powershell
git archive --format=tar.gz --output=$Archive $Commit `
  app.py pyproject.toml muclegal fixtures prompts assets frontend `
  reference/ue_examples.json

tar -tf $Archive | Select-String -Pattern `
  '(?i)(^|/)(\.env|\.muclegal|node_modules|\.output)(/|$)|\.(sqlite3?|warc|pem|key)$'
```

Der letzte Befehl darf keine Schlüssel, Laufzeitdaten oder Build-Caches melden. Ein
Treffer wird vor dem Upload geklärt; er wird nicht nur weggefiltert und ignoriert.

## 5. Release hochladen und vorbereiten

Das neue Verzeichnis wird als unprivilegierter Benutzer angelegt und das Archiv
dorthin übertragen:

```powershell
ssh -i $DeployKey "muclegal@$ServerIp" `
  "mkdir -p /opt/muclegal/releases/$Release"

scp -i $DeployKey $Archive `
  "muclegal@${ServerIp}:/opt/muclegal/releases/$Release/source.tar.gz"

ssh -i $DeployKey "muclegal@$ServerIp" `
  "tar -xzf /opt/muclegal/releases/$Release/source.tar.gz -C /opt/muclegal/releases/$Release"
```

Abhängigkeiten installieren und beide Builds prüfen, bevor der aktive Symlink
geändert wird:

```powershell
$Prepare = @"
set -e
export PATH=/opt/node/bin:/usr/local/bin:/usr/bin:/bin
export PLAYWRIGHT_BROWSERS_PATH=/opt/muclegal/playwright
/opt/muclegal/venv/bin/python -m pip install -e '/opt/muclegal/releases/$Release[demo]'
cd '/opt/muclegal/releases/$Release/frontend'
npm install --no-audit --no-fund
npm run test:minimal
npm run build
"@

ssh -i $DeployKey "muclegal@$ServerIp" $Prepare
```

`npm install` wird verwendet, weil das Repository derzeit kein `package-lock.json`
enthält. Sobald ein npm-Lockfile verbindlich eingecheckt ist, wird hier auf
`npm ci` gewechselt. Ein Release mit fehlgeschlagenem Build wird nicht aktiviert.

## 6. Aktivieren

Der Symlink-Wechsel ist atomar. Der Dienstneustart verursacht nur eine kurze
Unterbrechung:

```powershell
$Activate = @"
set -e
ln -sfn '/opt/muclegal/releases/$Release' /opt/muclegal/current
systemctl restart muclegal-backend.service
systemctl restart muclegal-frontend.service
systemctl is-active muclegal-backend.service
systemctl is-active muclegal-frontend.service
"@

ssh -i $DeployKey "root@$ServerIp" $Activate
```

Caddy, Basic Auth, der OpenAI-Schlüssel und der Demo-Speicher werden bei einem
normalen Codeupdate nicht verändert. Caddy muss nur nach einer Änderung an
`/etc/caddy/Caddyfile` validiert und neu geladen werden:

```powershell
ssh -i $DeployKey "root@$ServerIp" `
  "caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy"
```

## 7. Verifikation nach jedem Update

Serverseitig:

```powershell
$Verify = @'
set -e
readlink -f /opt/muclegal/current
systemctl is-active muclegal-backend muclegal-frontend caddy
curl -fsS -o /dev/null -w 'backend=%{http_code}\n' http://127.0.0.1:8000/beweis-labor
curl -fsS -o /dev/null -w 'frontend=%{http_code}\n' http://127.0.0.1:4173/
journalctl -u muclegal-backend -u muclegal-frontend -u caddy --since '-5 minutes' -p err --no-pager
'@

ssh -i $DeployKey "root@$ServerIp" $Verify
```

Erwartet werden der neue Releasepfad, dreimal `active`, zweimal HTTP 200 und keine
neuen Fehlereinträge. Zusätzlich im Browser mit den getrennt verwahrten Demo-
Zugangsdaten prüfen:

1. Ohne Zugangsdaten erscheint HTTP 401 beziehungsweise die Passwortabfrage.
2. `/` zeigt den Fallmonitor.
3. `/tenorhilfe` lädt und eine synthetische Eingabe erreicht den erwarteten Zustand.
4. `/beweis-labor` zeigt URL-Feld, Modus, Verlauf, Vorschau und Downloadbereich.
5. Ein kleiner Lauf mit `https://example.com` erzeugt ausschließlich technische
   Artefakte im isolierten Demo-Speicher.
6. Browserkonsole und Serverjournal enthalten keine neuen Fehler.

Ein realer OpenAI-Smoke-Test wird nur bewusst ausgeführt, weil er Guthaben verbraucht.
Der API-Schlüssel darf zur Prüfung niemals ausgegeben werden. Zulässig ist nur eine
boolesche Präsenzprüfung im Backendprozess.

## 8. Rollback

Zuerst vorhandene Releases und das aktuelle Ziel anzeigen:

```powershell
ssh -i $DeployKey "root@$ServerIp" `
  "readlink -f /opt/muclegal/current; find /opt/muclegal/releases -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort"
```

Dann den letzten bekannten guten Release explizit wählen. Weil die Python-Umgebung
gemeinsam genutzt wird, wird auch das alte Paket erneut editable installiert:

```powershell
$PreviousRelease = "<bekannter-guter-release>"
$Rollback = @"
set -e
/opt/muclegal/venv/bin/python -m pip install -e '/opt/muclegal/releases/$PreviousRelease[demo]'
ln -sfn '/opt/muclegal/releases/$PreviousRelease' /opt/muclegal/current
systemctl restart muclegal-backend.service
systemctl restart muclegal-frontend.service
systemctl is-active muclegal-backend.service
systemctl is-active muclegal-frontend.service
"@

ssh -i $DeployKey "root@$ServerIp" $Rollback
```

Anschließend Abschnitt 7 vollständig wiederholen. Alte Releases erst nach einem
separaten, bestätigten Aufräumschritt entfernen. Demo-Daten und Servergeheimnisse
werden bei einem Rollback nicht verändert.

## 9. Schlüssel ändern

Schlüsselupdates sind kein Code-Deployment. Sie erfolgen ausschließlich in
`/etc/muclegal/muclegal.env` mit Eigentümer `root`, Gruppe `root` und Modus `600`.
Danach wird nur `muclegal-backend.service` neu gestartet. Niemals die lokale `.env`
als Ganzes kopieren und niemals einen Schlüssel in einen Shellbefehl, Git-Commit,
Browser, Log oder eine URL schreiben.

Prüfung ohne Ausgabe des Werts:

```powershell
ssh -i $DeployKey "root@$ServerIp" `
  "test \$(stat -c '%a:%U:%G' /etc/muclegal/muclegal.env) = '600:root:root' && grep -q '^OPENAI_API_KEY=.' /etc/muclegal/muclegal.env"
```

## 10. GitHub und Entire abschließen

Entire ist im Repository über `.entire/settings.json` und die Codex-Hooks in
`.codex/hooks.json` aktiviert. Die Hooks erzeugen Checkpoints aus der Agent-Sitzung;
`git push origin` synchronisiert die zugehörigen Checkpoint-Refs. Keine Checkpoint-ID
manuell erfinden.

Nach Commit und Push prüfen:

```powershell
git status --short
git log -1 --oneline --decorate
git ls-remote --heads origin agent/live-url-ui
entire status
entire checkpoint list --json
```

Für einen bestimmten Commit liefert folgender Befehl die verknüpfte Historie, sobald
der Hook den Checkpoint abgeschlossen hat:

```powershell
entire checkpoint explain --commit HEAD --json --no-pager
```
