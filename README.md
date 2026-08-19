<p align="center">
  <img src="assets/muclegal-logo-light.png" alt="MucLegal" width="520">
</p>

# MucLegal

## Für alle, die das Problem verstehen wollen

### Worum geht es?

Wenn ein Unternehmen eine rechtswidrige Geschäftspraxis unterlassen muss, ist der Fall damit noch nicht unbedingt erledigt. Dieselbe Praxis kann später in leicht veränderter Form wieder auftauchen – zum Beispiel auf einer anderen Unterseite, im Warenkorb oder mit einer neuen Formulierung.

Ein einfacher Textvergleich übersieht solche Varianten häufig. MucLegal unterstützt deshalb bei der entscheidenden Frage: **Ist die neue Darstellung im Kern derselbe bereits untersagte Verstoß?** Juristisch spricht man von einer kerngleichen Verletzungsform.

### Was macht MucLegal?

MucLegal beobachtet öffentlich erreichbare Webseiten und dokumentiert nachvollziehbar, wenn sich eine rechtlich relevante Aussage ändert:

1. Die Seite wird abgerufen und der unveränderte Ausgangszustand wird lokal gesichert.
2. Unwichtiges Seitenrauschen wie Cookie-Hinweise oder laufende Countdown-Zahlen wird ausgeblendet.
3. Eine echte Textänderung wird sichtbar hervorgehoben.
4. Eine KI erstellt eine begründete juristische Vorprüfung anhand des hinterlegten Unterlassungstenors.
5. Die zugehörigen Beweise werden mit Prüfsummen, Webarchiv und Zeitstempel gesichert.
6. Ein Mensch prüft das Ergebnis und trifft die abschließende Entscheidung.

MucLegal entscheidet also **nicht selbst über einen Rechtsverstoß**. Die Software bereitet den Fall strukturiert auf und macht die Prüfung schneller und nachvollziehbarer.

### Für wen ist das gedacht?

- Verbraucherzentralen und Wettbewerbsverbände
- Industrie- und Handelskammern
- Kanzleien und Rechtsabteilungen
- Stellen, die die Einhaltung von Unterlassungserklärungen kontrollieren

### Was zeigt die Demo bereits?

Die Demo enthält zwei künstlich erstellte und klar gekennzeichnete Beispielszenarien:

- **Im Kern wiederholter Verstoß:** Die Formulierung hat sich geändert, die beanstandete Wirkung bleibt jedoch gleich.
- **Nicht vom Verbot umfasst:** Die neue Darstellung fällt nach der Vorprüfung nicht unter den hinterlegten Tenor.

Auf einer einzigen Prüfseite werden die Änderung, die KI-Begründung, bestehende Unsicherheiten und die gesicherten Beweismittel gezeigt. Die menschliche Entscheidung wird davon getrennt erfasst.

### Welche Grenzen gelten?

MucLegal arbeitet ausschließlich mit öffentlich zugänglichen Seiten. Es umgeht keine Logins, Paywalls, CAPTCHAs oder technischen Schutzmaßnahmen und respektiert `robots.txt`. Rohdaten und Beweismittel werden nicht zur Analyse an fremde Extraktionsdienste weitergegeben.

Der aktuelle Stand ist ein Hackathon-Prototyp und noch kein autonomes Produktivsystem. Insbesondere gibt es keine Benutzerverwaltung, kein Mehrmandanten-Dashboard, keine Screenshot-Analyse und keine automatische rechtliche Freigabe.

---

<p align="center">
  <img src="assets/muclegal-logo-dark.png" alt="MucLegal – technischer Teil" width="520">
</p>

# Technischer Teil

## Funktionsumfang

Der aktuelle Golden Path umfasst:

- kontrollierten HTTP-Abruf mit identifizierbarem User-Agent, Timeout und begrenzten Wiederholungen
- Prüfung von `robots.txt` und Abbruch bei Login-, CAPTCHA- oder Blockseiten
- lokale Ablage von HTML, Response-Headern, Zeitpunkten und Snapshot-Metadaten
- deterministische Normalisierung mit `trafilatura` und eng begrenzten CSS-Regeln
- SHA-256-Hashvergleich und Text-Diff bei relevanten Änderungen
- schema-validierte juristische Vorprüfung mit Offline-Fixtures oder Anthropic
- WARC/CDX-Erzeugung und Validierung mit `warcio`
- Hash-Manifest und RFC-3161-Zeitstempel mit dokumentiertem Offline-Fallback
- PDF-Prüfbericht und eine FastAPI-Ein-Seiten-Ansicht
- getrennte Speicherung von Modellbewertung und menschlicher Freigabe
- versionierte Eval-Suite mit maschinenlesbarem und fachlichem Bericht

## Voraussetzungen und Installation

Benötigt werden Python 3.11 oder neuer und Git. Für die vollständige WARC-Stufe wird GNU Wget benötigt; unter Windows verwendet das Projekt bevorzugt GNU Wget über WSL.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[demo]"
```

Für die Offline-Demo ist kein API-Schlüssel erforderlich. Die optionale Live-Vorprüfung benötigt `ANTHROPIC_API_KEY`.

## Schnellstart: vollständige Offline-Demo

Der folgende Befehl startet eine lokale Fixture-Seite, erzeugt Vorher- und Nachher-Snapshots, führt die Offline-Vorprüfung aus und erstellt das Beweispaket samt PDF:

```powershell
python -m muclegal demo --case kerngleich --store .muclegal-demo --report output/pdf/demo-pruefbericht.pdf
```

Alternativ steht der Gegenfall zur Verfügung:

```powershell
python -m muclegal demo --case nicht-umfasst --store .muclegal-demo --report output/pdf/demo-pruefbericht.pdf
```

Anschließend wird die Prüfoberfläche gestartet:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Die Ansicht ist danach unter `http://127.0.0.1:8000` erreichbar.

## Eine einzelne URL prüfen

Der `check`-Befehl deckt Abruf, Normalisierung, Speicherung und Änderungserkennung ab. Für einen lokalen Test kann zuerst ein Fixture-Server gestartet werden:

```powershell
python -m http.server 8765 --directory fixtures
```

In einem zweiten Terminal:

```powershell
python -m muclegal check --url http://127.0.0.1:8765/baseline.html --profile fixtures/demo-profile.json --store .muclegal
```

Der erste Lauf legt eine Baseline an. Weitere Läufe liefern als JSON unter anderem den aktuellen Hash, den Vorgänger-Hash, den Diff-Pfad und `needs_review`. Bei identischem Hash wird keine juristische Vorprüfung angestoßen.

Die CSS-Unterstützung ist absichtlich eng gehalten. Zulässig sind einfach prüfbare Selektoren wie `main`, `#cookie-banner`, `.countdown` oder `div.notice`. Ein Include-Selektor muss genau einen Knoten treffen.

## Juristische Vorprüfung

LLM-Aufrufe sind in `muclegal/llm/` gekapselt. Jeder Output wird gegen ein festes Schema validiert. Ungültige oder fehlende Antworten werden gespeichert, aber nicht als Bewertung freigegeben. `freigabe_durch_mensch` muss bis zur menschlichen Entscheidung `null` bleiben.

Der Offline-Modus verwendet gekennzeichnete Fixtures. Der Live-Adapter nutzt `claude-sonnet-5` und benötigt einen gesetzten Anthropic-Schlüssel.

## Eval-Auswertung

Die versionierte Eval-Suite prüft beide juristischen Demo-Fälle gegen feste Qualitäts-Gates:

```powershell
python -m muclegal eval --suite fixtures/eval-suite.json --output output/eval
```

Erzeugt werden:

- `eval-results.json` für die maschinelle Auswertung
- `eval-report.md` für die fachliche Sichtung

Gemessen werden Schema-Validität, erwartetes Ergebnis, Begründung, stärkstes Gegenargument und die weiterhin ausstehende menschliche Freigabe. Prompt-Version und Prompt-SHA-256 werden im Bericht festgehalten und durch einen Regressionstest geschützt.

Mit gesetztem `ANTHROPIC_API_KEY` läuft dieselbe Suite live:

```powershell
python -m muclegal eval --suite fixtures/eval-suite.json --output output/eval-live --live
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

Die Tests decken unter anderem stabile Hashes, Countdown- und Cookie-Rauschen, relevante Änderungen, HTTP-Fehler, Timeouts, Login-/CAPTCHA-Abbruch, Schemafehler, TSA-Ausfälle, WARC-Validierung, PDF-Bericht, UI-Freigabe und Eval-Gates ab.

## Projektstruktur

```text
muclegal/
  fetch/          HTTP-Abruf und optionaler Playwright-Fallback
  normalize/      Extraktion, Normalisierung und stabiler Hash
  storage/        SQLite und lokale Snapshot-Artefakte
  llm/            juristische Vorprüfung und Schema-Validierung
  evidence/       WARC, Manifest, Zeitstempel und PDF
  templates/      Ein-Seiten-Prüfoberfläche
fixtures/         synthetische Demo- und Eval-Fälle
tests/            automatisierte Abnahme- und Regressionstests
app.py            FastAPI-Einstiegspunkt
```

## Verlässlichkeit der Beweiskette

Rohes HTML, Header, normalisierter Text, Diff sowie Modellinput und -output werden lokal gespeichert und über ein Manifest miteinander verknüpft. Das WARC wird nach der Erstellung mit `warcio check -v` validiert. Der Manifest-Hash kann über RFC 3161 gestempelt und anschließend lokal geprüft werden.

Ist freeTSA oder eine optionale Wayback-Sicherung nicht erreichbar, bleibt dieser Status sichtbar offen. Die lokal erzeugten Artefakte und Hashes bleiben dennoch vollständig erhalten.
