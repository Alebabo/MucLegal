<p align="center">
  <img src="assets/muclegal-logo-light.png" alt="MucLegal" width="520">
</p>

# MucLegal

MucLegal ist ein Hackathon-Prototyp für die laufende Kontrolle von Unterlassungserklärungen. Er erkennt, wenn eine bereits untersagte Geschäftspraxis auf einer öffentlichen Webseite verändert wieder auftaucht – etwa unter einer anderen URL, auf einer anderen Ebene oder mit einer neuen Formulierung.

Die Software trifft keine autonome Rechtsentscheidung. Sie sammelt technische Anhaltspunkte, erstellt eine begründete Vorprüfung zur **kerngleichen Verletzungsform** und überlässt die Freigabe einem Menschen.

## Der Kern: Hashing spart Modellkosten

Jeder erfasste Seitenstand wird lokal normalisiert: dynamisches Rauschen wie Cookie-Banner, Session-IDs oder laufende Countdown-Werte wird entfernt. Erst danach bildet MucLegal einen SHA-256-Hash.

```text
öffentliche Seite → normalisieren → SHA-256 vergleichen
                                  ├─ unverändert: Ende, kein LLM-Aufruf
                                  └─ verändert: Diff + juristische Vorprüfung
```

Damit bleibt der häufige tägliche Prüfschritt deterministisch und ohne laufende KI-Kosten. Ein kostenpflichtiger Modellaufruf erfolgt nur, wenn sich der relevante normalisierte Inhalt tatsächlich geändert hat. Die teure Prüfung wird so vom Regelfall zum Ausnahmefall.

## Compliance-orientiertes Crawling

MucLegal arbeitet mit einem transparenten Projekt-User-Agent und ausschließlich auf öffentlich erreichbaren Seiten. Im Normalbetrieb:

- wird `robots.txt` geprüft und beachtet,
- gelten feste URL-, Timeout- und Wiederholungslimits,
- werden Logins, Paywalls, CAPTCHAs und technische Schutzmaßnahmen nicht umgangen,
- bleiben HTML, Header, Screenshots, WARC und Hash-Manifeste lokal,
- werden Abrufstatus, Grenzen und Beweisartefakte nachvollziehbar protokolliert.

Ist `robots.txt` nicht eindeutig prüfbar, wird dieser Zustand sichtbar als ungeprüft dokumentiert. Eine technische Erfassung wird nie als juristische Bewertung ausgegeben.

## Ablauf

1. Öffentliche Seite regelkonform abrufen.
2. Inhalt deterministisch normalisieren und hashen.
3. Nur bei einer Hash-Änderung den relevanten Diff untersuchen.
4. Kerngleichheit gegen den hinterlegten Tenor vorprüfen.
5. Beweise mit Screenshot, WARC/CDX, SHA-256-Manifest, Zeitstempelversuch und PDF/ZIP sichern.
6. Ergebnis durch einen Menschen freigeben oder verwerfen.

## Lokal starten

Voraussetzung: Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[demo]"
.venv\Scripts\python -m playwright install chromium
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Danach sind der Fallmonitor unter `http://127.0.0.1:8000` und das BeweisLab unter `http://127.0.0.1:8000/beweis-labor` erreichbar. Für die Offline-Demo ist kein API-Schlüssel erforderlich.

## Status

Entstanden für den Legal Loves Tech Hackathon 2026 in München. Der Prototyp ist eine lokale Demo und kein autonomes Produktivsystem oder Ersatz für eine juristische Prüfung.

Die ausführliche technische und fachliche Dokumentation liegt im [MucLegal-Funktionshandbuch](reference/MUCLEGAL_FUNKTIONSHANDBUCH.md).
