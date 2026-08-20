# Lokale BeweisLab-Abnahme – August 2026

Stand: 20.08.2026  
Rechner: Windows, Python 3.13.13, Playwright 1.59.0, Chromium 147.0.7727.15  
Betrieb: ausschließlich lokal, sequenziell, Projekt-User-Agent, kein Proxy/Stealth/Profil

## Baseline vor dem Umbau

Die Vorhermessung lief am 20.08.2026 ab 20:46:40 UTC mit genau einem Durchlauf pro Ziel und
`max_attempts=1`. Der alte Code erfasste noch keine Phasenpeaks, Kachelindizes oder getrennten
Rollenmetriken. Deshalb sind für die Baseline ausschließlich Prozess-RSS vor/nach dem Ziel,
Gesamtlaufzeit, Ablaufereignisse und der alte Ergebnisstatus belegt; fehlende Peakwerte werden
nicht geschätzt.

| URL | Alter Status | Laufzeit | Python-RSS vorher → nachher | Wesentlicher Befund |
|---|---|---:|---:|---|
| `https://www.temu.com/de` | `completed_with_warnings` | 27,086 s | 50,9 → 113,2 MB | Hauptseite Challenge; AGB-Ersatzquelle erfasst |
| `https://mirageperfume.com/` | `completed_with_warnings` | 49,620 s | 113,2 → 149,5 MB | Haupt-, AGB- und Datenschutzbild, aber kein Vollständigkeitsstatus |
| `https://www.ikea.com/de/de/` | `completed_with_warnings` | 39,236 s | 149,5 → 147,5 MB | AGB-Übersicht aufgelöst; keine Weißbildvalidierung |
| `https://www.mcfit.com/` | `completed_with_warnings` | 16,551 s | 147,5 → 154,1 MB | Rechtstexte vorhanden; keine Rollenabdeckung |
| `https://www.mediamarkt.de/` | `completed_with_warnings` | 60,274 s | 154,1 → 152,5 MB | Rechtstextbilder vorhanden; Containerinhalt nicht plausibilisiert |
| `https://example.com/` | `completed` | 3,476 s | 152,5 → 147,6 MB | Kleiner vollständiger Smoke-Test |

Baseline-Artefakt: `output/baseline-before-2026-08-20/baseline-results.json`.

## Doctor und deterministische Diagnose

- Schreibrechte: bestanden.
- Freier Speicher: 15,45 GB.
- Port 8000: frei.
- Chromium-Start: bestanden; `navigator.webdriver=true`.
- Synthetische 30.000-Pixel-Seite: `vollstaendig_erfasst`, Footer vorhanden.
- Weißer Vollbildversuch: im Test verworfen; lückenloser 2.000-Pixel-Kachelfallback erreicht
  30.000 CSS-Pixel und enthält den Footer in der letzten Originalkachel.
- Consent-Regression: `Alle ablehnen` wird gewählt, `Alle akzeptieren` nie; generisches
  `Ablehnen` benötigt Dialog-, Consent- und Alternativnachweis.
- Browserabbruch nach Initialsicherung: `teilweise_erfasst`, `dom-initial.html` bleibt erhalten.

Diagnoseartefakte: `output/capture-diagnose/`.

## Nachher-Abnahme

`example.com` bestand zuerst separat den vollständigen Golden Path. Anschließend liefen die
übrigen fünf Ziele ab 21:19:29 UTC genau einmal und streng sequenziell. Das Prozess-RSS der
gemeinsamen Messhülle erreichte maximal 290,3 MB; dies ist kein Chromium-Phasenpeak. Der aktuelle
Code speichert für neue Läufe zusätzlich durchschnittliches/maximales Python-RSS je Ziel und
weist den unter Windows nicht stabil zuordenbaren Chromium-Peak ausdrücklich als
`not_available` mit Grund aus.

| URL | Laufzeit | Ergebnis | Tatsächlich erfasst | Rollen / Textzeichen / Klauseln | ZIP |
|---|---:|---|---|---|---:|
| `https://example.com/` | 5,85 s | `vollstaendig_erfasst` | gleiche URL | main 127 / 3 | 88.078 B |
| `https://www.temu.com/de` | 22,662 s | `durch_seitenschutz_begrenzt` | `/de/terms-of-use.html`; Haupt-Challenge getrennt | AGB-Ersatz 75.068 / 378; Datenschutz 30.629 / 164; Schutzbild 377 / 3 | 11.946.124 B |
| `https://mirageperfume.com/` | 63,722 s | `vollstaendig_erfasst` | gleiche URL und Shopify-Policies | main 5.897 / 25; AGB 27.992 / 155; Datenschutz 65.429 / 457 | 50.748.496 B |
| `https://www.ikea.com/de/de/` | 44,906 s | `vollstaendig_erfasst` | gleiche URL; konkrete AGB-Seite und Datenschutz | main 14.066 / 73; AGB 27.835 / 214; Datenschutz 61.209 / 424 | 62.505.705 B |
| `https://www.mcfit.com/` | 28,443 s | `vollstaendig_erfasst` | gleiche URL; beide Rechtstextrollen | main 17.919 / 74; AGB 22.681 / 193; Datenschutz 42.952 / 345 | 35.979.295 B |
| `https://www.mediamarkt.de/` | 60,709 s | bei Lauf zunächst `vollstaendig_erfasst`, nach Befund fachlich-technisch `teilweise_erfasst` | gleiche URL; AGB-Übersicht und Datenschutz-Shop | main 26.278 / 177; AGB 35.654 / 177; gerenderter Datenschutz nur 957 / 3 | 30.720.969 B |

Alle Nachherbilder wurden als validierte Playwright-Vollbilder erzeugt; Seitenhöhen reichten von
900 bis 21.229 CSS-Pixeln. Die synthetische Abnahme deckt zusätzlich den zwingenden Kachelfallback
ab. Jede Rolle enthält Rohantwort, initiales und finales DOM, sichtbare Texte, normalisierten Text,
Klauseln, Consent-/Expansionsprotokoll, Bildindex, Preview und Ressourcenmetriken.

## Consent-Ergebnisse

- IKEA AGB und Datenschutz: `Optionale Cookies ablehnen`, Dialog danach verschwunden.
- McFit Datenschutz: `Nur notwendige Cookies verwenden`, Dialog danach verschwunden.
- Für die übrigen Rollen wurde keine datensparsame Aktion ausgeführt.
- Der während der Matrix geladene Zwischenstand bezeichnete sichtbare, aber nicht als Consent
  belegte Controls noch als `consent_ungeklaert`. Der finale Code meldet dies jetzt korrekt als
  `kein_eindeutiger_consent_kandidat`; unbekannte echte Consent-Dialoge bleiben ungeklärt.

## Integrität und Paketinhalt

- `example.com`: 32 manifestierte Artefakte, WARC 829 B.
- Jedes große Realziel: 75 manifestierte Artefakte; WARC 93.482 bis 273.028 B.
- ZIP enthält das vollständige fallgebundene Verzeichnis und zusätzlich kompatible
  `artefakte/<label>`-Aliase. Damit liegen alle manifestierten Rollenoriginale und Kacheln im ZIP.
- `capture-index.json`, `capture-metrics.json`, `run-result.json`, Transparenzdatei,
  Interaktionsprotokoll, WARC/CDX, Manifest, Zeitstempelstatus und PDF sind lokal vorhanden.
- freeTSA und Wayback bleiben optionale Zusatzdienste; lokale Primärbeweise werden bei deren
  Ausfall nicht verworfen.

## Verbleibende reale Grenzen

1. Temu: Die Hauptseite bleibt durch eine JavaScript-Challenge begrenzt. Es wurde nichts gelöst
   oder umgangen. Der finale Code ordnet die erreichbare `/de/terms-of-use.html` im Paket explizit
   der Rolle `agb` statt `main` zu; eine synthetische Regression deckt diese Zuordnung ab.
2. MediaMarkt: Der reale Lauf deckte einen zu dünnen gerenderten Datenschutzcontainer und eine
   ungelöste AGB-Übersicht auf. Der finale Code erzwingt dafür `teilweise_erfasst`. Wegen des
   verbindlichen Requestbudgets wurde das Ziel nicht wiederholt; eine spätere manuelle Abnahme
   muss den neuen Teilstatus bestätigen oder eine inhaltsreichere Same-Origin-Seite belegen.
3. Chromium-Peak-RSS ist unter Windows ohne stabile Browser-PID nicht belastbar. Er bleibt
   `not_available`; Python-RSS, CPU-Zeit, Handles, Laufzeit, Requests, übertragene bekannte Bytes,
   temporärer Speicher und Artefaktgrößen werden gemessen.

Maschinenlesbare Nachherdaten liegen unter `output/post-acceptance/`.

