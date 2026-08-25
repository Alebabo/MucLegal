# Anonyme Kalibrierungsfälle für den Kerngleichheitscheck

Stand: 25.08.2026

## Lokale Quelle

Das vom Nutzer bereitgestellte Google-Dokument `statistik-mit-falltext` wurde als
strukturierter, unveränderlicher Snapshot unter
`reference/kerngleichheit_anonyme_stimmen_2026-08-25.json` abgelegt.

- Google-Drive-Dokument-ID:
  `12ElAk3j8x99gIulELGeYY9afEp2iXdSodhPFO2dJqvE`
- gespeicherte Drive-Revisions-ID:
  `AIroW34qg7nf0KQfpDzGYV-dvIAjYMVtFtuByUxYvzqjB2bmOSLP4JEdZveJi1rz2m8phMgoGMvLfyJ5ihBmbSdSlIROw-c4vP9pTMt6Be0`
- SHA-256 des auf LF-Zeilenenden kanonisierten JSON-Snapshots:
  `e737fac1e701f490cc194ead1c9cfe7024fccc4a9ff178fb53d2e42a4a0a401b`
- Umfang: 20 Fälle mit Tenor, Ausgangsfassung, aktueller Fassung und
  anonymer Stimmenverteilung
- Status: nutzerbereitgestellt, anonym und nicht juristisch freigegeben

Der lokale Snapshot ist die reproduzierbare Laufzeitquelle. Spätere Änderungen am
Drive-Dokument verändern ihn nicht still. Die LF-Kanonisierung verhindert, dass ein
Windows-Release-Archiv mit CRLF-Zeilenenden fälschlich eine andere Quelle ausweist.

## Laufzeitverwendung

`muclegal/llm/monitor_knowledge.py` wählt anhand informativer Wortüberschneidungen
höchstens drei passende Fälle aus. Diese werden im bestehenden strukturierten
`wissensbasis`-Input unter `anonyme_kalibrierung` an Haiku beziehungsweise Sonnet
übergeben.

Die eingefrorenen Dateien `prompts/classify_v1.md` und
`prompts/baseline_mapping_v1.md` bleiben unverändert. Analysemetadaten speichern
zusätzlich Version und SHA-256 des Kalibrierungskontexts.

## Fachliche Grenzen

- Die Stimmen sind kein juristischer Goldstandard und entscheiden keine Klasse.
- Vollständiger Tenor, `nicht_umfasst`, belegte Tatsachen und menschliche Freigabe
  haben Vorrang.
- Die drei Stimmenklassen werden nur begrifflich auf
  `kerngleich`, `beseitigt` und `neuer_sachverhalt` abgebildet.
- Stimmenanteile und Dissens bleiben erhalten. Bei 50 Prozent oder weniger wird keine
  `mehrheitsklasse` gespeichert.
- Der Kontext darf Unsicherheit sichtbar machen, aber ein Ergebnis nicht allein wegen
  einer Stimmenpluralität hochstufen.
