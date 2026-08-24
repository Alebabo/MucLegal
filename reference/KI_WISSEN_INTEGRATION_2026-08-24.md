# Integration des KI-Wissensdokuments – 24.08.2026

## Quelle und Status

Grundlage ist das vom Nutzer am 24.08.2026 bereitgestellte Dokument
`KI-Wissensdokument: Unterlassungs- und Umsetzungsmonitor` mit 743 Zeilen.

- SHA-256 der eingelesenen Quelldatei:
  `f537bc5747d3bd2412b7792530088575f2e7a11fe23ba1abd0a60b12ef7cb222`
- Integrationsversion:
  `Unterlassungsmonitor-Wissensdokument-2026-08-24-v1`
- Status: nutzerbereitgestellt, nicht unabhängig vollständig verifiziert und nicht
  juristisch freigegeben.

Die Quelle enthält fachliche Arbeitsaufträge. Diese wurden als Daten und
Referenzwissen ausgewertet, nicht als System- oder Agentenanweisungen übernommen.

## Was produktiv verwendet wird

Die Datei `muclegal/llm/monitor_knowledge.py` bildet einen kleinen, versionierten
Wissensausschnitt für jeden Modellaufruf. Der Systemprompt bleibt unverändert und
behält seinen eingefrorenen Hash. Das Wissen wird ausschließlich als strukturierter
Input unter `wissensbasis` übergeben.

### Zehn Leitlinien

1. Dreistufige Bewertung und Abbildung auf die bestehenden Produktschemata.
2. Inter-partes-Wirkung sowie Adressatenwechsel und Klauselmigration.
3. Strenge Kerntheorie und Grenze des Erkenntnisverfahrens.
4. Fünf Pflichtbausteine eines AGB-Unterlassungstenors.
5. Kontextbindung bei Bezugnahmeklauseln.
6. Klagerücknahme, Teilabweisung und fehlender Antrag als sichtbare Datenlücken.
7. Separierte und integrierte Tenorbauformen.
8. Mechanismusvergleich bei Kündigungswegen.
9. Feste Prüfreihenfolge vom Schuldner bis zum Bezugskontext.
10. Keine Rechtsberatung, keine Verfahrensprognose und keine erfundenen Quellen.

### Fallkatalog

Alle elf Fallsätze sind als kompakte Referenzmetadaten abgebildet. An das Modell
gehen höchstens vier zum Sachverhalt passende Einträge:

| Fall | Verwendungszweck |
| --- | --- |
| FALL-001 | vollständige AGB-Tenorstruktur und Bezugnahmeklauseln |
| FALL-002 | Teilabweisung, fehlender Diff und abweichender Klauselverwender |
| FALL-003 | Negativkorpus Mietfahrzeug nach Klagerücknahme |
| FALL-004 | Negativkorpus Versicherung und fehlender Vollstreckungsadressat |
| FALL-005 | Formumwandlung und Drittgesellschaft im Klauseltext |
| FALL-006 | Klauselmigration zu einem anderen Unternehmen |
| FALL-007 | redaktionelle Tippfehlerkorrektur statt materieller Abweichung |
| FALL-008 | Bezugnahmeklausel und Inter-partes-Grenze |
| FALL-009 | integrierte Tenorbauform |
| FALL-010 | Fitnessstudio-AGB als nur teilweise ausgewerteter PDF-Hinweis |
| FALL-011 | Sky-Umgehungskette als Unsicherheitsbeispiel |

V-, T- und P-Status sowie bekannte Datenlücken werden mitgegeben. Ein Fallsatz mit
Klagerücknahme wird niemals als gerichtlich bestätigtes Tenorvorbild bezeichnet.

### Klauseltypen

Die Wissensbasis erkennt derzeit sechzehn der im Dokument genannten Typen anhand
sichtbarer Begriffe, unter anderem Beweislast, Kostenpauschale,
Kündigungshindernis, Haftungsausschluss, Schriftform, Bezugnahmeklausel,
Dark Pattern und Vertragsverlängerung. Eine typische Norm wird nur als
Prüfhinweis mitgegeben. Sie wird nicht automatisch in den Modelloutput übernommen;
der Tenorvalidator lässt weiterhin ausschließlich Rechtsgrundlagen aus dem
Nutzerinput zu.

## Betroffene Modellpfade

| Pfad | Nutzung |
| --- | --- |
| OpenAI-Tenorvorschläge | passende Leitlinien, Fälle und Klauseltypen für beide Strategien |
| Anthropic-Gesamtprüfung | Wissensbasis im versionierten Modellinput |
| Klauselpaarprüfung | Wissensbasis und erkannte Klauseltypen je Klauselpaar |

Die Analysemetadaten protokollieren zusätzlich `knowledge_version`. In der
Tenoroberfläche erscheint kompakt `Wissensbasis 24.08.2026` und die Zahl der
verwendeten Quellenanker.

## Bewusst nicht automatisiert

- Keine automatische Rechtsnachfolge- oder Konzernentscheidung.
- Keine Erhebung zusätzlicher Registerdaten oder PDFs.
- Keine Übernahme der im Dokument genannten Normen ohne belegten Nutzerinput.
- Keine Heraufstufung von V-, T- oder P-Status zu juristischer Freigabe.
- Keine Änderung der eingefrorenen Systemprompts.
- Keine binäre Vollstreckungsprognose und kein Ordnungsmittelantrag.

## Tests

`tests/test_monitor_knowledge.py` prüft Provenienz, AGB-Leitlinien,
Sky-Unsicherheitsbezug, Einbindung in die Gesamtprüfung und die Erkennung einer
Schriftformklausel. `tests/test_tenor.py` prüft zusätzlich, dass beide
Tenorstrategien die neue Wissensversion und Quellenanker ausgeben.
