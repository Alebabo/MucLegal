# MucLegal Scan

Kleine eigenständige Vercel-Version: statisches HTML/CSS/JavaScript und eine Python-Function. Keine KI, Chromium, SQLite oder serverseitigen Hintergrundjobs.

## Deployment

Vercel-Projekt `muclegal-scan`, Root Directory `scanner`, Framework Other, Build Command `python build.py`, Region Frankfurt. Die HTTP- und Normalisierungsengine wird aus dem bestehenden Projekt übernommen; `build.py` aktualisiert die kleinen Engine-Kopien. Die Kopien ermöglichen auch ein isoliertes Deployment dieses Ordners.

## Verhalten

- URL → öffentliche AGB-Seite → Normalisierung → SHA-256 → Absatz- und Wort-Diff.
- Echte Statusereignisse werden als NDJSON gestreamt. Keine simulierte Prozentangabe.
- Frühere Live-Stände bleiben im jeweiligen Browser in localStorage. Ist kein Stand vorhanden, wird der letzte erfolgreiche HTML-Snapshot vor heute über Wayback CDX gesucht. Ist kein Archivstand verfügbar, wird der erste Stand gespeichert. Kein serverseitiger Speicher oder API-Schlüssel nötig.
- Decathlon: vollständiger Webarchiv-Stand 08.10.2024 gegen vorhandene PDF, Stand 20.07.2026. PDF-Text wurde einmalig extrahiert; pypdf ist keine Runtime-Abhängigkeit.
- Müller: vollständiges archiviertes HTML vom 03.07.2025 gegen öffentliches HTML, abgerufen am 13.10.2026. Quell-Hashes stehen in `data/mueller.json`.
- URL-Prüfung, öffentliche IP-Adressen, robots.txt und Schutzseiten-Erkennung stammen aus der bestehenden Engine. Keine Umgehung von Zugriffshürden. HTTP(S) auf Port 80/443, begrenzte Abrufe und HTML-Dokumente. PDF-URLs und Seiten, deren AGB ausschließlich per JavaScript zugänglich sind, werden nicht live gerendert.
- Normalisierung entfernt Layout-Zeilenumbrüche, aber keine materiellen Vertragsänderungen. Ein technischer Text-Diff ist keine juristische Prüfung oder vollständiges Beweispaket.

## Lokal prüfen

```sh
python -m pip install -r scanner/requirements.txt uvicorn pytest
python scanner/build.py
python -m pytest scanner/tests -q
python -m uvicorn dev:app --app-dir scanner --port 8000
```
