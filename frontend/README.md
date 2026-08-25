# MucLegal-Frontend

TanStack-Start-Frontend im Aura-Design für Fallmonitor und BeweisLab. Die Oberfläche
läuft standardmäßig lokal; auf ausdrückliche Nutzeranweisung darf sie entsprechend
den Projektvorgaben zeitlich begrenzt über einen ngrok-Tunnel demonstriert werden.

## Lokal starten

Zuerst das Python-Backend auf Port 8000 starten:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Danach das Frontend auf Port 4173 starten:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

Der Fallmonitor ist unter `http://127.0.0.1:4173/` erreichbar. Das technisch
getrennte BeweisLab wird unter `http://127.0.0.1:4173/beweis-labor` sicher an den
lokalen FastAPI-Prozess weitergeleitet.

Für einen isolierten Test kann das Proxy-Ziel überschrieben werden:

```powershell
$env:MUCLEGAL_API_ORIGIN = "http://127.0.0.1:8010"
npm run dev -- --host 127.0.0.1 --port 4175
```

## Seiten und Backend-Anbindung

- `/`: Dashboard mit Kennzahlen und Prioritäten;
- `/hinweise`: Fälle mit Tenor, Prüfumfang und menschlicher Entscheidung;
- `/archiv`: Falltabelle mit Detailansicht;
- `/neu`: Intake eines bekannten Erstverstoßes;
- `/tenorhilfe`: zwischen der geführten UE-Tenorhilfe und der strukturierten
  Maske mit menschlicher Entscheidung wechseln;
- `/beweis-labor`: rein technische URL-Erfassung des FastAPI-Backends.

Das Frontend verwendet ausschließlich die versionierten Endpunkte:

```text
GET  /api/v1/monitoring-cases
POST /api/v1/cases
POST /api/v1/cases/{case_id}/review
POST /api/v1/runs
GET  /api/v1/runs/{run_id}
POST /api/v1/tenor-drafts
POST /api/v1/tenor-drafts/{draft_id}/review
POST /api/v1/tenor-proposals
```

`POST /api/v1/tenor-proposals` erzeugt genau einen vollständigen, schema-validierten
UE-Entwurf (`complete`). Er bleibt bis zur menschlichen Prüfung ausdrücklich nicht
freigegeben. Der API-Schlüssel liegt nur in der lokalen
Server-`.env` und wird weder an das Frontend noch an einen ngrok-Link übergeben.

Ohne gespeicherte Monitoringfälle bleiben die fünf klar synthetischen Lotto-Fälle
als Demo sichtbar. Sobald das Backend Fälle liefert, zeigt die Oberfläche diese
persistierten Daten. Ein Monitoringlauf kann erst nach einer ausdrücklichen
menschlichen Freigabe gestartet werden.

## Verifikation

```powershell
npm run typecheck
npm run lint
npm run build
```

Für die gesamte Anwendung zusätzlich im Repository-Stamm:

```powershell
python -m compileall -q muclegal app.py
python -m pytest -q
```
