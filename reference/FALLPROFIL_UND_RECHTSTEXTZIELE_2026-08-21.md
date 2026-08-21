# Fallprofile, Rechtstextziele und externe Analysehinweise

Stand: 21.08.2026

Status: implementiert und lokal verifiziert

Beispiel: Ankerkraut / Shopify

## 1. Zweck und fachliche Trennung

Der Fallmonitor sucht keine Erstverstöße. Eine Mitarbeiterin der
Verbraucherzentrale dokumentiert einen bereits fachlich geprüften Verstoß und
legt fest, wo und in welchen Erscheinungsformen dieser später gesucht werden
soll. Erst nach menschlicher Freigabe beginnt das Monitoring.

Das BeweisLab ist davon getrennt. Es erfasst den tatsächlich erreichbaren
öffentlichen Zustand einer URL und erstellt technische Artefakte. Es trifft
keine juristische Entscheidung über Kerngleichheit, Vertragsstrafe oder einen
neuen Rechtsverstoß.

```text
Verbraucherzentrale dokumentiert Erstverstoß
→ Fallprofil mit verbindlichen URLs und Varianten
→ menschliche Fallfreigabe
→ technischer Monitoringlauf
→ Kandidat oder dokumentierte technische Grenze
→ juristische Vorprüfung nur im freigegebenen Fall
→ menschliche Befundentscheidung
```

Diese Trennung verhindert insbesondere, dass eine unvollständige Erfassung als
Entlastung des Unternehmens oder ein technischer Treffer als verbindliche
Rechtsentscheidung dargestellt wird.

## 2. Ausgangsproblem bei Ankerkraut

Die Ankerkraut-AGB liegen unter:

```text
https://www.ankerkraut.de/policies/terms-of-service
```

Eine reine Linksuche auf der zuerst abgerufenen Seite kann diese URL übersehen.
Das geschieht beispielsweise, wenn der direkte Abruf nur eine JavaScript-Hülle,
eine abweichende Navigation oder keinen auswertbaren Footer enthält. Eine
Browserdarstellung kann zusätzlich wegen dynamischer Seitenhöhe, Schutzstatus
oder fehlendem relevantem Text unvollständig bleiben.

Die ursprüngliche Meldung „Die konfigurierte Extraktion ergab keinen relevanten
Text“ sagte deshalb nur etwas über diesen konkreten Abruf- und
Extraktionszustand aus. Sie bewies weder, dass keine AGB existieren, noch dass
die überwachte Praxis beseitigt wurde.

Für eine robuste Überwachung müssen bekannte fachliche Ziele Vorrang vor einer
automatischen Seitensuche haben. Die automatische Suche bleibt eine Ergänzung,
nicht die Definition des Prüfumfangs.

## 3. Implementiertes Fallprofil

Ein `MonitoringCase` enthält neben den bisherigen Angaben folgende
Profilinformationen:

| Feld | Bedeutung |
|---|---|
| `target_urls` | Bis zu 20 verbindliche öffentliche Prüf-URLs. |
| `relevant_page_types` | Fachliche Seitentypen, etwa Startseite, AGB, FAQ, Produktseite oder Kündigungsseite. |
| `element_labels` | Bis zu 20 bekannte Beschriftungen desselben Buttons oder Links. |
| `nicht_umfasst` | Bis zu 20 ausdrückliche Abgrenzungen gegen Fehlalarme. |
| `allowed_subdomains` | Einzeln freigegebene echte Subdomains der überwachten Domain. |
| `screenshot` | Optionaler lokaler Screenshot des menschlich festgestellten Erstverstoßes. |

Die Fundstellen-URL wird immer automatisch in `target_urls` aufgenommen. Alle
Ziele müssen zur überwachten Domain oder einer ausdrücklich erlaubten Subdomain
gehören. URLs mit eingebetteten Zugangsdaten werden nicht akzeptiert.

Für einen Klauselfall ist `clause_text` erforderlich. Für einen Elementfall
sind Hauptbezeichnung, Funktion und Fehlerart erforderlich. Unterstützte
Fehlerarten sind:

- `fehlt`,
- `nicht_sichtbar`,
- `nicht_leicht_zugaenglich`,
- `falsches_ziel`,
- `zusaetzliche_huerde`.

### Abwärtskompatible Speicherung

Für diese Erweiterung wurde keine Datenbankmigration eingeführt. Die neuen
Werte liegen als Objekt im vorhandenen SQLite-Feld
`relevant_page_types_json`:

```json
{
  "page_types": ["AGB", "Kündigungsseite"],
  "target_urls": [
    "https://www.ankerkraut.de/policies/terms-of-service",
    "https://www.ankerkraut.de/pages/abo-verwalten"
  ],
  "nicht_umfasst": [
    "Ein freiwilliger Supportlink ohne Kündigungsfunktion."
  ],
  "element_labels": [
    "Abo kündigen",
    "Abonnement beenden",
    "Vertrag kündigen"
  ]
}
```

Alte Datensätze, in denen dieses Feld noch eine reine Liste der Seitentypen
enthält, bleiben lesbar. Sie erhalten beim Laden die bisherige Fundstellen-URL
als einziges verbindliches Ziel und gegebenenfalls die alte
Elementbezeichnung als einzige Variante.

## 4. Bedienung und API

In der lokalen Ein-Seiten-Oberfläche unter `http://127.0.0.1:8000` können
verbindliche URLs, Nicht-umfasst-Abgrenzungen und Buttonvarianten jeweils
zeilenweise erfasst werden. Die Fallliste zeigt anschließend die Anzahl der
verbindlichen Prüf-URLs.

Die API nimmt dieselben Felder über `POST /api/v1/cases` entgegen. Beispiel für
einen Ankerkraut-Elementfall:

```json
{
  "fall_id": "VZ-ANKERKRAUT-001",
  "domain": "ankerkraut.de",
  "source_url": "https://www.ankerkraut.de/pages/abo-verwalten",
  "violation_type": "element",
  "description": "Dokumentierter Kündigungszugang wird erneut technisch geprüft.",
  "tenor_element": "Der vorgeschriebene Kündigungszugang muss leicht und unmittelbar zugänglich sein.",
  "monitoring_target": "Öffentlicher Zugang zur Kündigungsfunktion",
  "relevant_page_types": ["AGB", "Kündigungsseite"],
  "target_urls": [
    "https://www.ankerkraut.de/policies/terms-of-service",
    "https://www.ankerkraut.de/pages/abo-verwalten"
  ],
  "nicht_umfasst": [
    "Ein allgemeiner Kontakt- oder Supportlink ohne Kündigungsfunktion."
  ],
  "element_label": "Abo kündigen",
  "element_labels": [
    "ABO KÜNDIGEN",
    "Abonnement kündigen",
    "Vertrag kündigen"
  ],
  "element_function": "/pages/abo-verwalten",
  "element_error": "falsches_ziel",
  "allowed_subdomains": []
}
```

Der angelegte Fall beginnt mit `weitere_pruefung`. Erst
`POST /api/v1/cases/{case_id}/review` mit der menschlichen Entscheidung
`freigegeben` autorisiert einen Monitoringlauf.

## 5. Reihenfolge der Zielauflösung

Der Fallmonitor prüft Ziele in folgender Reihenfolge:

1. verbindliche URLs aus dem menschlich freigegebenen Fallprofil,
2. ein kleines, seitentypabhängiges Set bekannter gleichursprünglicher
   Rechtstextpfade,
3. öffentliche Sitemap-Ziele,
4. priorisierte interne Links innerhalb des freigegebenen Hosts und Budgets.

Explizite Profilziele gelten auch dann als fachlich relevant, wenn ihre URL
keinen Begriff wie `agb`, `terms` oder `kündigen` enthält. Sie werden sowohl in
die Klausel- als auch in die DOM-Prüfung einbezogen.

Das BeweisLab ergänzt bei einer erkannten Shopify-Seite nur dann bekannte
Policy-Pfade, wenn für die betreffende Rolle kein HTML-Link gefunden wurde:

```text
/policies/terms-of-service
/policies/privacy-policy
```

Die Quelle wird in `legal_pages.json` als
`known_shopify_public_path` dokumentiert. Das ist ein eng begrenzter
Plattformfallback und kein allgemeines Erraten beliebiger Pfade.

Alle Ziele unterliegen weiterhin denselben Regeln für öffentliche URLs,
Netzwerkzugriff, Schutzseiten und `robots.txt`.

## 6. Vollständigkeitsnachweis

Der Domainlauf schreibt den verbindlichen Prüfumfang nach `coverage.json`:

```json
{
  "required_target_urls": ["https://example.test/agb"],
  "captured_required_target_urls": [],
  "missing_required_target_urls": ["https://example.test/agb"]
}
```

Fehlt mindestens eine verbindliche URL, lautet der Fallstatus
`pruefung_unvollstaendig`. Der Lauf darf dann insbesondere nicht als
`beseitigt` ausgegeben werden.

Ein optional ergänzter bekannter Pfad, der nachvollziehbar nicht existiert,
kann übersprungen werden. Ein ausdrücklich vom Menschen eingetragenes Ziel ist
dagegen verbindlich; sein Fehlschlag bleibt sichtbar.

## 7. Button- und Linkmonitoring

Die DOM-Prüfung sucht nicht nur den ursprünglichen Wortlaut, sondern alle
freigegebenen `element_labels`. Bei dem bereitgestellten Ankerkraut-Text sind
unter anderem folgende Kandidaten relevant:

- `ABO KÜNDIGEN`,
- `Vertrag widerrufen`,
- `Kostenpflichtig Bestellen`,
- `Zahlungspflichtig bestellen`,
- `Kaufen`,
- `Jetzt bezahlen`.

Je Treffer werden technische Eigenschaften wie Sichtbarkeit, zugänglicher
Name, Deaktivierung, Überdeckung und Linkziel dokumentiert. Ein vorhandenes
gleichursprüngliches Linkziel kann als sicherer Pfad festgehalten werden.

Das System führt keine Bestellung, Kündigung oder Formularübermittlung aus. Es
überwindet keine Logins und automatisiert keine allgemeinen Klickpfade. Ob ein
Element rechtlich ausreichend gestaltet ist, bleibt eine menschliche
Bewertung.

## 8. Technische Ergebnisstufen des BeweisLabors

Jeder BeweisLab-Lauf erhält genau eine technische Eignungsaussage. Diese ist
von einem juristischen Befund getrennt:

| Code | Anzeige | Bedeutung |
|---|---|---|
| `technisch_verwendbar` | Als technischer Beleg verwendbar | Öffentliche Seite und wesentliche Artefakte wurden regulär erfasst. Das garantiert keine rechtliche Verwertbarkeit. |
| `eingeschraenkt` | Nur eingeschränkt verwendbar | Es liegen verwertbare Teile vor, aber etwa Screenshot, Text, Vollständigkeit oder Robots-Prüfung ist eingeschränkt. |
| `hinweis` | Nicht als Beleg verwendbar – nur Hinweis | Gesichert wurde nur ein Schutz-, Fehler- oder ausdrücklich demonstrativer God-Mode-Zustand. |
| `nicht_erfassbar` | URL nicht erfassbar | Es konnte kein regulärer öffentlicher Seiteninhalt aufgenommen werden. |

God-Mode-Aufnahmen bleiben immer Demonstrationshinweise und werden weder mit
regulären Beweispaketen vermischt noch einer juristischen
Kerngleichheitsprüfung zugeführt.

Eine Browserseite, deren Höhe während der Kachelerfassung schrumpft, führt
nicht mehr automatisch zum Verlust aller Bilder. Vor jeder Kachel werden Höhe
und Breite neu gemessen. Bereits valide Kacheln bleiben als Teilaufnahme
erhalten; Fehler und nicht erreichte Bereiche werden im Kachelindex
dokumentiert.

## 9. Einordnung des bereitgestellten Context.dev-Ergebnisses

### Was daran hilfreich ist

Das bereitgestellte Ergebnis bestätigt für die Fallanlage:

- die konkrete AGB-URL,
- den ausgewiesenen AGB-Stand `19.06.2026`,
- den Inhalt einzelner Klauseln,
- interne Ziele wie `/pages/abo-verwalten`,
- sichtbare Button- und Linkbeschriftungen,
- weitere Rechtstextpfade im Footer.

Es eignet sich daher als Ausgangsmaterial, aus dem eine Mitarbeiterin
URL-Vorschläge, Klauselkandidaten und Bezeichnungsvarianten in ein Fallprofil
übernimmt.

### Warum es kein Primärbeweis ist

Aus dem gelieferten Text allein sind insbesondere nicht verlässlich
nachprüfbar:

- Original-Response-Header und Redirectkette,
- exakt empfangene Rohbytes,
- verwendeter User-Agent und Abrufmodus,
- Browser- und Consent-Zustand,
- pixelgetreue Darstellung,
- Zeitpunkt und Integrität jeder einzelnen Originaldatei,
- WARC/CDX, lokales SHA-256-Manifest und RFC-3161-Status.

Der Text enthält außerdem viel Navigations-, Filter- und dynamisches
Kampagnenrauschen. Solche Bestandteile müssen für einen stabilen Hash
deterministisch normalisiert werden.

### Zulässige Rolle im System

Eine spätere optionale Context.dev-Anbindung dürfte ausschließlich als
Analysespur arbeiten. Ein Ergebnis wäre klar als `external_analysis_hint` zu
kennzeichnen und getrennt zu speichern, beispielsweise mit:

```json
{
  "kind": "external_analysis_hint",
  "provider": "context.dev",
  "source_url": "https://www.ankerkraut.de/policies/terms-of-service",
  "received_at": "<lokaler Empfangszeitpunkt>",
  "response_sha256": "<Hash der empfangenen Antwort>",
  "suggested_target_urls": [],
  "suggested_element_labels": [],
  "accepted_by_human": null
}
```

Verbindliche Regeln dafür:

1. Keine Roh-HTML-, Header-, WARC- oder Screenshot-Beweisspur wird an den
   Fremddienst geleitet.
2. Der Fremdtext wird nicht als Ursprungsaufnahme ausgegeben und nicht in eine
   reguläre Beweis-Hashkette eingeschleust.
3. Vorschläge werden erst nach menschlicher Sichtung Teil eines Fallprofils.
4. Das Ergebnis trifft keine juristische Entscheidung.
5. Ein Fremdabruf ersetzt keine lokale Robots-, Schutz- oder
   Vollständigkeitsdokumentation.

Diese Integration ist derzeit bewusst nicht implementiert. Für den
Hackathon-Golden-Path genügt die manuelle Übernahme belegter URLs und Varianten
in das Fallprofil; dadurch bleibt die Herkunft der Beweisspur eindeutig.

## 10. Ergebnis des realen Ankerkraut-Tests

Die neue Shopify-Erkennung fand den AGB-Kandidaten korrekt. Der reguläre
automatische Abruf wurde anschließend von `robots.txt` für den
Projekt-User-Agent untersagt.

Das korrekte technische Ergebnis lautet deshalb:

```text
AGB-Ziel bekannt
→ Kandidat und Ausschlussgrund dokumentiert
→ kein automatischer AGB-Inhaltsbeweis
→ Prüfumfang unvollständig beziehungsweise eingeschränkt
→ gegebenenfalls zusätzliche manuelle Sicherung durch einen Menschen
```

Dass ein externer Dienst dennoch Text liefern kann, ist kein Widerspruch: Dessen
Abrufbedingungen, User-Agent und technische Herkunft sind aus dem Ergebnis
nicht mit der lokalen Erfassung gleichzusetzen. Der externe Text darf daher
nicht verwendet werden, um den lokalen Robots-Ausschluss verdeckt zu umgehen.

## 11. Artefakte und Nachvollziehbarkeit

Ein Domain-Monitoringlauf hält unter anderem fest:

- `coverage.json` mit erforderlichen, erfassten und fehlenden Zielen,
- `monitoring-findings.json` mit Erstverstoß, Profil und technischen
  Kandidaten,
- gespeicherte Seitenbytes und Response-Header,
- DOM-Prüfungen und Screenshots, soweit technisch möglich,
- WARC/CDX aus den tatsächlich gespeicherten Bytes,
- SHA-256-Manifest und Verifikation,
- `freigabe_durch_mensch: null` für noch nicht entschiedene Befunde.

Das BeweisLab führt zusätzlich die Rollen Hauptseite, AGB und Datenschutz sowie
deren Fund- und Auswahlmethoden in den paketbezogenen Indizes getrennt.

## 12. Verifikation

Die Änderung ist durch Regressionstests abgedeckt für:

- Lesen alter Fallprofile,
- Speichern verbindlicher URLs, Varianten und Abgrenzungen,
- Monitoring einer nicht verlinkten Pflicht-AGB-Seite,
- Weitergabe mehrerer Buttonvarianten an die DOM-Prüfung,
- Shopify-Policy-Discovery ohne Footerlink,
- Erhalt valider Screenshotkacheln bei schrumpfender Seite,
- technische Eignungsklassifikation und Terminalpakete.

Verifizierter Stand am 21.08.2026:

```text
python -m compileall -q muclegal app.py
python -m pytest -q -k "not test_wget_warc_is_validated_by_warcio"
→ 123 passed, 1 deselected

GET http://127.0.0.1:8000/beweis-labor
→ HTTP 200
```

Der ausgesparte Test betrifft den separat bekannten, sporadischen
GNU-Wget/`warcio`-Digestfehler unter WSL. Der produktive Golden Path erzeugt
WARC aus den exakt lokal gespeicherten Bytes und ist davon unabhängig. Dieser
externe Flake darf nicht als grüner Wget-Test dargestellt werden.

## 13. Verbleibende Grenzen

- Unbekannte, nirgends verlinkte Seiten können nur über ein menschliches
  Fallprofil, einen eng begrenzten bekannten Plattformpfad oder eine öffentliche
  Sitemap in den Prüfumfang gelangen.
- `robots.txt`, Login, Paywall, CAPTCHA und sonstige technische Schutzgrenzen
  werden im regulären Modus nicht umgangen.
- Ein nicht gefundenes Element bedeutet nur „nicht im dokumentierten
  Prüfumfang gefunden“.
- Buttonvarianten verbessern die Wiedererkennung, ersetzen aber keine
  Funktions- oder Rechtsprüfung.
- Screenshots werden nicht per Vision analysiert.
- Dynamische, personalisierte oder regionale Darstellungen können einen
  zusätzlichen menschlichen Abruf erfordern.
- Context.dev und vergleichbare Dienste können Hinweise liefern, aber keine
  lokale Primärbeweisspur ersetzen.

## 14. Zugehörige Dokumentation

- `reference/KERNGLEICHHEIT_BACKEND_FLOW.md`: Zielablauf der späteren
  juristischen Vorprüfung.
- `reference/TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md`: belegte Fehlerbilder,
  Ursachen, Lösungen und Restgrenzen.
- `reference/LOCAL_BEWEISLAB_IMPLEMENTATION_PLAN.md`: kanonischer technischer
  Erfassungsplan.
- `reference/BROWSER_MODE_AUDIT.md`: Browsermodus, Transparenz und
  Schutzgrenzen.
- `reference/BACKEND_ALIGNMENT_2026-08-20.md`: fachliche Abgrenzung der
  Backend-Komponenten.
