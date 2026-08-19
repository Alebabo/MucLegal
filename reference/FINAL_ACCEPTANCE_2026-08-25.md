# Freeze-Abnahme zum 25.08.2026

Stand der Prüfung: 19.08.2026. Ziel ist die belastbare Entscheidung, ob der Unterlassungs- und Umsetzungsmonitor in den Feature-Freeze gehen kann.

## Ergebnis

**Bedingt abnahmefähig, noch nicht final freeze-ready.** Die lokale technische Kette und der Demo-Pfad sind grün. Für eine endgültige Freigabe fehlen drei externe beziehungsweise menschliche Gates: der 12-Fälle-Live-Lauf mit dem vorgesehenen Anthropic-Modell, der Live-Nachweis für Wayback Save Page Now und zwei ausgefüllte, unabhängig verblindete Juristinnenbewertungen.

| Bereich | Status | Befund |
|---|---|---|
| Technische Funktion | Grün | 54/54 Tests unter Python 3.12 und 3.13; öffentlicher Smoke-Test; Browserprüfung ohne Konsolenfehler |
| Beweiskette | Grün/Gelb | WARC enthält exakt die gespeicherte HTTP-Nutzlast; Hashgleichheit bestätigt; RFC-3161 live verifiziert; Wayback ohne Zugangsdaten noch offen |
| Challenge-Fit | Grün | Kernthese „kerngleiche Verletzungsform“ sichtbar; Human-in-the-loop, Gegenargument und Beweispaket sind pitchfähig |
| Juristische Belastbarkeit | Gelb | Rechtspositionen sind als Vorprüfung gekennzeichnet; unabhängige Juristinnenbewertung steht noch aus |
| Sicherheit/Datenschutz | Grün/Gelb | Keine kritischen oder hohen Befunde; Produktions-Härtung gegen DNS-Rebinding bleibt Roadmap |

## Durchgeführte Abnahme

- Vollständige Unit-/Integrationstests: 54 von 54 bestanden unter Python 3.12.13 und Python 3.13.
- Browserprüfung der Ein-Screen-Oberfläche bei 1366×768 und 900×768: Tenorentwurf, menschliche Freigabe, Persistenz und responsive Darstellung funktionieren; keine Browser-Konsolenfehler.
- Öffentlicher Smoke-Test auf `https://example.org`: erster Lauf legt die Baseline an, zweiter Lauf beendet sich bei unverändertem Normalisierungs-Hash.
- Offline-Eval: 12 synthetische Fälle, gleichmäßig verteilt auf `kerngleich_umfasst`, `nicht_umfasst` und `unklar`; Schema-, Begründungs-, Gegenargument- und Human-Release-Gates jeweils 100 %. Dieser Lauf prüft Determinismus und Verkabelung, **nicht** die Modellgüte.
- Blind-Review-Pakete für zwei Juristinnen wurden unabhängig randomisiert erzeugt; Erwartungswerte und Modellantworten fehlen bewusst.
- Demo-Beweispaket: WARC valide; `snapshot_payload_sha256` und `warc_payload_sha256` identisch (`c241a00b…d95`); RFC-3161-Status `verified`; Manifest und Hashkette erzeugt; PDF visuell auf zwei Seiten geprüft.
- Sicherheitsprüfung: keine kritischen/hohen Befunde; Eingabegrenzen, strikte Schemas, Host-/Origin-Prüfung, sichere Header und inerte Artefaktauslieferung umgesetzt.

## Challenge-Bewertung

Vorläufig **82/100**, mit realistischer Zielspanne **88–92/100**, sobald die drei offenen Gates grün sind.

Stärken:

- Das Produkt beantwortet die eigentliche juristische Frage statt nur Textänderungen zu zeigen.
- `nicht_umfasst`, Unsicherheit und stärkstes Gegenargument reduzieren Bestätigungsfehler.
- Die Kostenlogik ist überzeugend: kostenloser täglicher Hash-Pfad, teure Analyse nur bei Kandidaten.
- Der Wow-Moment ist nachvollziehbar: vom freigegebenen Tenor zur Fundstelle und zum prüfbaren Beweispaket auf einem Screen.
- Die menschliche Freigabe ist technisch erzwungen und im Datenmodell sichtbar.

Abzüge bis zur Schlussabnahme:

- Die 12 Fälle sind noch nicht live mit dem vorgesehenen Modell gelaufen.
- Juristische Inter-Rater-Übereinstimmung und Fehlalarmquote sind noch unbekannt.
- Wayback ist implementiert, aber mangels Zugangsdaten nicht live belegt.
- Python 3.11 wurde nicht geprüft; der unterstützte Pfad ist durch 3.12 und 3.13 abgedeckt.

## Juristische Bewertung

Das System ist als **Entscheidungsunterstützung und Beweissicherung**, nicht als automatische Rechtsentscheidung, vertretbar positioniert. `freigabe_durch_mensch` bleibt in Modellantworten zwingend `null`; erst eine bewusste UI-Aktion aktiviert einen Tenor oder bestätigt einen Befund.

Folgende Aussagen müssen im Pitch präzise bleiben:

1. Eine menschliche Freigabe allein schafft keine pauschale RDG-Ausnahme. Der Prototyp ist für interne Nutzung durch befugte Verbraucherverbände, Wettbewerbsverbände, IHKs oder Rechtsdienstleister konzipiert; die konkrete Betreiber- und Prozessgestaltung bleibt zu prüfen.
2. Die Vertragsstrafe aus einer Unterlassungserklärung ist von Ordnungsmitteln aus einem gerichtlichen Titel zu trennen. Vertragsstrafenbezug: insbesondere § 339 BGB beziehungsweise die konkrete Vereinbarung; Ordnungsmittel: § 890 ZPO.
3. Die Aktivlegitimation nach § 8 Abs. 3 UWG ist organisationsbezogen zu prüfen. Für IHKs ist nach heutiger Fassung die einschlägige Nummer gesondert und aktuell zu verifizieren; keine harte Nummer ohne Quellenprüfung in der Demo behaupten.
4. WARC, Hashkette und Zeitstempel stützen Integrität und zeitliche Nachweisbarkeit. Sie beweisen nicht automatisch Wahrheit, Zurechnung, Vollständigkeit oder rechtliche Erheblichkeit des Inhalts.
5. Wayback ist eine zusätzliche Drittbestätigung, nicht die primäre Beweisspur. Rohdaten und Beweisartefakte bleiben lokal; externe LLMs erhalten nur die minimierte Analysespur.
6. Nur öffentliche, ohne Schutzumgehung erreichbare Seiten dürfen verarbeitet werden. Robots-Regeln, Nutzungsbedingungen, Datenschutz, Datenminimierung und Löschkonzept sind vor Pilotbetrieb organisationsbezogen zu dokumentieren.

## Verbindliche Freeze-Gates

Bis 25.08.2026 müssen folgende Punkte nachgewiesen werden:

- [ ] 12-Fälle-Live-Eval mit dem eingefrorenen Prompt und vorgesehenen Modell; Rohoutputs archiviert; Schemafehler 0; menschliche Freigabe in Modelloutputs stets `null`.
- [ ] Beide Blind-Review-Dateien vollständig ausgefüllt; Abweichungen adjudiziert; Fehlalarm- und Unklar-Quote dokumentiert.
- [ ] Ein credentialed Wayback-SPN-Lauf auf einer zulässigen öffentlichen Testseite oder eine ausdrücklich beschlossene Deaktivierung mit Pitch-Formulierung „optional“.
- [ ] Prompt-Hash und Modellbezeichner nach Abschluss unveränderlich dokumentiert; keine Promptänderung nach 20.08. abends.
- [ ] Abschluss-Smoke am Freeze-Tag: Baseline → unverändert → Kandidat → menschliche Freigabe → Beweispaket → Manifestprüfung → PDF.
- [ ] Juristische Pitch-Folien durch beide Juristinnen freigegeben, insbesondere RDG, § 8 UWG, Vertragsstrafe/§ 890 ZPO und Beweiswert.

## Go/No-Go-Regel

**Go**, wenn alle verbindlichen Gates erfüllt sind und kein kritischer/hoher Sicherheits- oder Beweiskettenfehler entsteht. **No-Go für Live-Behauptungen**, wenn Modell-Live-Eval oder juristische Doppelprüfung fehlen; dann darf nur der deterministische Offline-Demopfad gezeigt und ausdrücklich als solcher bezeichnet werden. Wayback darf bei fehlendem Live-Nachweis nur als optionale Integration beschrieben werden.
