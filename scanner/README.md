# MucLegal Scan

Kleine eigenständige Vercel-Version: statisches HTML/CSS/JavaScript und eine Python-Function. Keine KI, Chromium, SQLite oder serverseitigen Hintergrundjobs.

## Deployment

Vercel-Projekt `muclegal-scan`, Root Directory `scanner`, Framework Other, Build Command `python build.py`, Region Frankfurt. Die HTTP- und Normalisierungsengine wird aus dem bestehenden Projekt übernommen; `build.py` aktualisiert die kleinen Engine-Kopien. Die Kopien ermöglichen auch ein isoliertes Deployment dieses Ordners.

## Verhalten

- URL → öffentliche AGB-Seite → Normalisierung → SHA-256 → Absatz- und Wort-Diff.
- Echte Statusereignisse werden als NDJSON gestreamt. Keine simulierte Prozentangabe.
- Frühere Live-Stände bleiben im jeweiligen Browser in localStorage. Ist kein Stand vorhanden, werden bei den exakt passenden Decathlon-/Müller-AGB-URLs die hinterlegten, belegten Archivstände genutzt. Für andere URLs wird der letzte erfolgreiche HTML-Snapshot vor heute über Wayback CDX gesucht. Ist kein Archivstand verfügbar, wird der erste Stand gespeichert. Kein serverseitiger Speicher oder API-Schlüssel nötig.
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

## Design und Sprachen

Die App übernimmt die echten Light-Theme-Tokens und das Logo aus dem bestehenden Frontend, mit Manrope/Lora, Schwarz/Weiß und eckigen Komponenten. Die lokal gespeicherten WOFF2-Schriften sind für Englisch/Deutsch verkleinert. DE/EN wechseln die Oberfläche, Statusmeldungen und Fehlertexte; Vertragsquellen bleiben unverändert. Längere Absätze zeigen zunächst eine Vorschau und lassen sich für beide Spalten gemeinsam ausklappen.

Der Scan-Verlauf ist ein aufklappbarer Aktivitätsgraph mit echten Prozessereignissen. Jeder Schritt lässt sich separat öffnen; nach dem Lauf ergänzen Quellen, SHA-256-Prüfsummen und Absatzanzahlen die Details. Hero- und Marketingtexte wurden entfernt.

## God Mode und Anzeigeverzögerung

Auf ausdrückliche Nutzeranweisung vom 13.10.2026 nutzt jeder Live-Abruf die vorhandene `god_mode_session`. robots.txt wird weiterhin geprüft und protokolliert, stoppt den Abruf aber nicht. Weiterleitungen werden auch im God Mode gegen öffentliche Zieladressen geprüft. Ein ablehnender robots.txt-Status erscheint als Dokumentationshinweis mit Aufforderung zu manuellen Screenshots; es gibt keine Upload-Funktion. Der JSON-Export kennzeichnet technische God-Mode-Abrufe ausdrücklich, ohne juristische Verwertbarkeit zu behaupten. HTTP-Zugriffssperren, Logins und CAPTCHAs können den direkten Abruf weiterhin verhindern; es wird kein Browser-/Stealth-Stack hinzugefügt. Jeder gestreamte Scan-Schritt bleibt durch eine Sekunde künstliche Verzögerung sichtbar.

Gespeicherte Vergleichsvorschläge laden ausschließlich die jeweilige AGB-URL ins Eingabefeld. Der gespeicherte Vergleich startet erst durch Scan oder Enter. Eine manuelle Änderung der URL hebt die Beispielauswahl auf und startet beim Absenden einen Live-Scan.
