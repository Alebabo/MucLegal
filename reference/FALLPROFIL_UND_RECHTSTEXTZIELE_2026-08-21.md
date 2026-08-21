# Fallprofil und nicht verlinkte Rechtstextziele

## Ziel

Der Fallmonitor sucht keine Erstverstöße. Eine Mitarbeiterin der
Verbraucherzentrale dokumentiert einen bereits fachlich geprüften Verstoß und
gibt den technischen Prüfumfang anschließend ausdrücklich frei. Das BeweisLab
bleibt davon getrennt und sichert nur den tatsächlich erfassten öffentlichen
Zustand.

## Fallprofil

Ein Fallprofil enthält zusätzlich zu Fall-ID, Domain, Fundstelle, Tenorelement
und Monitoringziel:

- bis zu 20 verbindliche öffentliche Prüf-URLs,
- relevante Seitentypen wie Startseite, AGB, FAQ oder Kündigungsseite,
- bei Elementfällen eine Hauptbezeichnung und bis zu 20 bekannte
  Button-/Linkvarianten,
- bis zu 20 `nicht_umfasst`-Abgrenzungen gegen Fehlalarme,
- optional einen Screenshot des menschlich festgestellten Erstverstoßes.

Alle Ziele müssen zur freigegebenen Domain oder einer ausdrücklich erlaubten
Subdomain gehören. Monitoring startet erst nach menschlicher Freigabe. Das
System meldet technische Zustände und Kandidaten; `freigabe_durch_mensch`
bleibt für den späteren Befund offen.

Die zusätzlichen Profildaten werden abwärtskompatibel im vorhandenen
JSON-Feld der lokalen SQLite-Tabelle abgelegt. Es ist keine Schema- oder
Datenbankmigration erforderlich; alte Fälle erhalten beim Lesen die
Fundstellen-URL als einziges verbindliches Ziel.

## Rechtstextauflösung

Die technische Zielauflösung kombiniert:

1. verbindliche URLs aus dem menschlich freigegebenen Fallprofil,
2. Links aus dem gespeicherten HTML beziehungsweise DOM,
3. eng begrenzte bekannte öffentliche Rechtstextpfade,
4. Sitemap-Ziele und priorisierte interne Links innerhalb des freigegebenen
   Hosts.

Für erkannte Shopify-Seiten ergänzt das BeweisLab bei fehlendem HTML-Link
gezielt:

- `/policies/terms-of-service`,
- `/policies/privacy-policy`.

Diese Pfade werden mit den normalen URL-, Netzwerk- und Robots-Regeln
abgerufen. Es gibt kein Pfadraten, keinen Login und keine Schutzumgehung.

## Ankerkraut-Beispiel

Für einen freigegebenen öffentlichen Fall sollten mindestens diese Ziele im
Fallprofil stehen:

```text
https://www.ankerkraut.de/
https://www.ankerkraut.de/policies/terms-of-service
https://www.ankerkraut.de/pages/fragen-antworten
```

Im realen Test wurde der AGB-Pfad damit gefunden, sein automatischer Abruf aber
von `robots.txt` für den Projekt-User-Agent untersagt. Das ist ein dokumentierter
unvollständiger Prüfumfang und darf nicht umgangen oder als AGB-Beweis
dargestellt werden.

Bei einem Kündigungsbutton können zusätzlich Varianten wie `Abo kündigen`,
`Abonnement beenden` und `Vertrag kündigen` dokumentiert werden. Die
DOM-Prüfung untersucht Sichtbarkeit, zugängliche Beschriftung, Deaktivierung,
Überdeckung und ein vorhandenes gleichursprüngliches Linkziel. Finale Aktionen,
Formularübermittlungen, Logins und allgemeine Klickpfade werden nicht
ausgeführt.

## Ergebnisgrenzen

- Eine fehlende verbindliche URL führt zu `pruefung_unvollstaendig` und wird in
  `coverage.json` ausdrücklich als `missing_required_target_urls` ausgewiesen.
- Ein nicht gefundenes Element bedeutet nur: innerhalb der vollständig
  dokumentierten Prüf-URLs nicht gefunden.
- Buttonvarianten verbessern die technische Wiedererkennung, ersetzen aber
  keine juristische Kerngleichheitsprüfung.
- Nicht verlinkte oder unbekannte Seiten können nur über ein Fallprofil, einen
  bekannten eng begrenzten Plattformpfad oder eine öffentliche Sitemap erfasst
  werden.
- Geschützte Kundenkonten, Paywalls und CAPTCHAs bleiben außerhalb des
  automatischen Prüfumfangs.
