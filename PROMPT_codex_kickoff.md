# Kickoff-Prompt für Codex

Zuerst `AGENTS.md` lesen. Danach den folgenden Prompt einmal ausführen,
**bevor** Code geschrieben wird.

---

## PROMPT (kopieren)

Lies zuerst AGENTS.md vollständig. Schreibe in diesem ersten Durchlauf noch
keinen Produktionscode.

Deine Aufgabe: Sichte die unten stehenden Repositories und liefere mir eine
Entscheidungsvorlage, was wir übernehmen, was wir nachbauen und was wir
ignorieren. Wir haben zwei echte Bautage – jede übernommene Abhängigkeit muss
sich gegen "selbst schreiben in 30 Zeilen" rechtfertigen.

Klone in `./reference/` (nicht in den Projektbaum) und arbeite dich in dieser
Reihenfolge durch:

**1. https://github.com/dgtlmoon/changedetection.io**
Interessiert: Scheduling-Modell, Fetch-Abstraktion (requests vs. Playwright),
wie Rauschen aus Seiten gefiltert wird, wie Snapshots persistiert werden.
Nicht interessiert: UI, Notification-Plugins, Docker-Setup.
Frage: Übernehmen wir die Filterlogik konzeptionell oder als Abhängigkeit?

**2. https://github.com/adbar/trafilatura**
Interessiert: API-Oberfläche für Boilerplate-Entfernung, Optionen für
deterministischen Output (gleicher Input → gleicher Output, zwingend für
Hashing), Umgang mit Cookie-Bannern und Navigation.
Frage: Reicht trafilatura allein für die Normalisierung, oder brauchen wir
eine eigene Nachbereinigung? Zeig mir konkret, was übrig bleibt.

**3. https://github.com/webrecorder/pywb**
Interessiert: nur, ob wir WARC-Erzeugung damit machen sollten oder ob
`wget --warc` reicht. pywb ist wahrscheinlich zu groß für uns.
Frage: Was ist der kleinste Weg zu einem validen, wiederabspielbaren WARC?

**4. https://github.com/trbs/rfc3161ng**
Interessiert: Zeitstempel-Anfrage gegen freeTSA, Verifikation des Tokens,
Abhängigkeiten.
Frage: Zeig mir ein minimales Beispiel, das einen SHA-256-Hash stempelt und
das Token danach wieder verifiziert.

**5. https://github.com/wolfgangihloff/rechtsinformationen-bund-de-mcp**
Interessiert: die verwendeten Endpunkte von testphase.rechtsinformationen.bund.de
und das Antwortformat. Wir brauchen keinen MCP-Server, nur die API-Kenntnis.
Frage: Wie zitierfähig sind die Rückgaben, und was fehlt im Datenbestand?

**6. https://github.com/Klotzkette/claude-fuer-deutsches-recht**
Interessiert: Prompt-Muster für deutsche Rechtssprache, Umgang mit
Paragraphenzitaten, ob dort Halluzinationsgegenmaßnahmen drinstehen.
Nicht übernehmen ohne Prüfung – bewerte kritisch.

**7. https://github.com/Liquid-Legal-Institute/Legal-Text-Analytics**
Das ist eine kuratierte Linksammlung, kein Code. Durchsuche sie gezielt nach:
deutschsprachigen Rechtsdatensätzen, Arbeiten zu Klauselklassifikation und
allem, was mit AGB-Analyse zu tun hat. Liefere mir maximal fünf Fundstellen,
die für uns relevant sind, mit je einem Satz warum.

**Zusätzlich prüfen (kein Repo):**
- Wayback CDX Server API – wie hole ich programmatisch alle Snapshots einer URL
  in einem Zeitraum? Das ist unsere Zeitmaschine für die Eval.
- Wayback "Save Page Now" – gibt es einen dokumentierten, stabilen Weg, eine
  Archivierung auszulösen und die resultierende URL zurückzubekommen?

### Was ich als Ergebnis will

Eine Datei `reference/FINDINGS.md` mit:

1. Tabelle: Repo | übernehmen als Abhängigkeit / nachbauen / ignorieren |
   Begründung in einem Satz | geschätzter Integrationsaufwand in Stunden
2. Ein konkreter Vorschlag für die Normalisierungs-Pipeline (Stufe 1), mit
   Begründung, warum genau diese Schritte das Rauschen entfernen und der Hash
   trotzdem stabil bleibt
3. Die drei größten technischen Risiken für unsere Deadline, mit je einem
   Gegenmittel
4. Eine Liste der Stellen, an denen ich mit Anti-Bot-Schutz rechnen muss,
   und was wir dagegen legal tun dürfen (keine Umgehung von Schutzmaßnahmen)

Halte dich kurz und triff Entscheidungen, statt Optionen aufzuzählen. Wenn du
etwas nicht prüfen kannst, weil kein Netzzugriff besteht, sag es explizit,
statt zu raten.
