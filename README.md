# MucLegal

MucLegal ist ein Hackathon-Prototyp zur nachvollziehbaren Überwachung
öffentlicher Webseiten nach einer Unterlassungserklärung. Der aktuelle Stand
deckt Bautag 1 ab: Abruf, deterministische Normalisierung, SHA-256 und
Änderungsvergleich. Eine Änderung ist noch keine juristische Entscheidung.

## Einrichtung

Voraussetzung ist Python 3.11 oder neuer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[demo]"
```

## Ein vollständiger Abruf

Der Abruf benötigt eine öffentliche HTTP(S)-URL und ein festes
Normalisierungsprofil. Für eine lokale Demo kann im Repository ein HTTP-Server
gestartet werden:

```powershell
python -m http.server 8765 --directory fixtures
```

In einem zweiten Terminal verarbeitet genau ein Befehl die Seite:

```powershell
python -m muclegal check --url http://127.0.0.1:8765/baseline.html --profile fixtures/demo-profile.json --store .muclegal
```

Das JSON-Ergebnis nennt Hash, Vorgänger-Hash, Diff und ob eine nachgelagerte
Prüfung erforderlich wäre. Der erste erfolgreiche Lauf legt nur die Baseline
an. Bei identischem Hash wird `needs_review` nicht gesetzt.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Die CSS-Unterstützung ist absichtlich eng: Profile dürfen einfache Selektoren
wie `main`, `#cookie-banner`, `.countdown` oder `div.notice` verwenden. So
bleiben die tatsächlich unterdrückten DOM-Bereiche leicht prüfbar. Ein
Include-Selektor muss genau einen Knoten treffen.

## Vollständige Offline-Demo

Der Golden Path startet selbst eine lokale HTTP-Fixture, erzeugt zwei
Snapshots, bewertet die Änderung über eine schema-validierte Offline-Antwort,
erstellt und validiert WARC plus Manifest und versucht einen RFC-3161-
Zeitstempel. Ist freeTSA nicht erreichbar, bleibt der Status sichtbar offen und
alle lokalen Beweise bleiben vollständig.

```powershell
python -m muclegal demo --case kerngleich --store .muclegal-demo --report output/pdf/demo-pruefbericht.pdf
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Danach liegt die Ein-Seiten-Prüfung unter `http://127.0.0.1:8000`. Der zweite
Demo-Fall wird mit `--case nicht-umfasst` erzeugt. Modellbewertung und
menschliche Entscheidung werden getrennt gespeichert; der Modelloutput darf
`freigabe_durch_mensch` nie selbst setzen.

Auf Windows bevorzugt die WARC-Stufe GNU Wget in WSL, weil verbreitete native
Wget-Builds fehlerhafte WARC-Digests erzeugen. Außerhalb von Windows wird das
lokale `wget` verwendet. `warcio check -v` ist immer ein harter Prüfschritt.

Für eine Live-Vorprüfung ist `ANTHROPIC_API_KEY` erforderlich. Der Adapter nutzt
`claude-sonnet-5` und schema-erzwungene Ausgaben; die Demo benötigt keinen Key.

