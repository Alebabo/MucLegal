# Reference findings

Stand: 18.08.2026. Geprueft wurden die unten genannten Commits sowie die aktuellen, verlinkten Primaerquellen. Empfehlung fuer die zwei Bautage: **nur `trafilatura` als neue Python-Abhaengigkeit uebernehmen**. Alles andere ist ein kleines eigenes Modul, ein CLI-Aufruf oder reine Eval-Quelle.

## 1. Entscheidung

| Repo (gepruefter Commit) | Entscheidung | Begruendung in einem Satz | Integration |
| --- | --- | --- | ---: |
| `dgtlmoon/changedetection.io` (`811256d`) | **nachbauen** | Fetcher-Auswahl, Due-Time plus Jitter und Include-/Exclude-Filter sind gute Muster, der Gesamtserver ist fuer einen taeglichen Ein-User-Job aber unverhaeltnismaessig. | 4 h |
| `adbar/trafilatura` (`a397f89`) | **als Abhaengigkeit uebernehmen** | Die gepflegte Extraktionsheuristik ersetzt weit mehr als 30 Zeilen und entfernt Navigation, Footer, Linkfarmen und viele Consent-Bloecke reproduzierbar. | 3 h |
| `webrecorder/pywb` (`9de84be`) | **ignorieren** | pywb ist ein GPL-Replay-/Proxy-System mit Redis-, gevent-, UI- und Index-Komponenten; fuer einen kleinen WARC reicht GNU Wget. | 2 h fuer Wget + Test |
| `trbs/rfc3161ng` (`f9b2964`) | **ignorieren** | Die Bibliothek verifiziert fest mit RSA-PKCS#1, freeTSA signiert seit 16.03.2026 mit P-384-ECC; der Live-Test endete mit `TypeError: ECPublicKey.verify() takes 3 positional arguments but 4 were given`. | 2 h fuer OpenSSL-Wrapper |
| `wolfgangihloff/rechtsinformationen-bund-de-mcp` (`ce9128a`) | **nachbauen** | Drei kleine `requests.get()`-Funktionen gegen die amtliche API sind kuerzer und aktueller als MCP, Axios und Fuse.js zusammen. | 2 h |
| `Klotzkette/claude-fuer-deutsches-recht` (`964eb58d9`) | **nachbauen** | Fuenf Quellen- und Subsumtionsregeln sind brauchbar, das riesige, stark repetitive Prompt-Paket wuerde Kontext und Fehlerflaeche vergroessern. | 2 h |
| `Liquid-Legal-Institute/Legal-Text-Analytics` (`1debe1b`) | **ignorieren** | Es ist nur ein Linkkatalog; einzelne Datensaetze werden direkt fuer die Eval genutzt. | 1 h |

### Was wir aus changedetection.io kopieren

- Pro URL einen fest gespeicherten Fetch-Modus: schneller HTTP-Fetch standardmaessig, Playwright nur bei nachgewiesenem JS-Bedarf. Kein automatischer Wechsel zwischen zwei Laeufen, weil das selbst Hash-Aenderungen erzeugt.
- `next_check_at`, optional kleines Jitter, und die Regel „nicht erneut einreihen, wenn queued/running“. Fuer taegliche Checks genuegt ein System-Cron/Task-Scheduler, der faellige SQLite-Zeilen verarbeitet; kein eigener Scheduler-Daemon.
- Erst subtraktive DOM-Selektoren, dann ein optionaler Include-Selektor, danach Textfilter. Die Regeln gehoeren versioniert zur URL.
- Snapshots als Dateien, Metadaten/Hash/Pfad in SQLite. Nicht dessen Dateiindex und Brotli-Lifecycle kopieren.

Die Filterlogik wird damit **konzeptionell**, nicht als Abhaengigkeit uebernommen.

### Trafilatura: notwendig, aber nicht hinreichend

Fest einzustellende API-Optionen:

```python
extract(
    html,
    output_format="txt",
    favor_precision=True,
    include_comments=False,
    include_tables=True,
    include_links=False,
    include_images=False,
    with_metadata=False,
    deduplicate=False,
)
```

`with_metadata=False` vermeidet wechselnde Metadaten, `deduplicate=False` vermeidet zustandsabhaengige Deduplizierung; ausserdem Version pinnen. Ein lokaler Wiederholungstest mit identischem HTML ergab zweimal bytegleich:

```text
Nur heute 20 % Rabatt
Diese Aktion endet heute um 23:59 Uhr.
Lieferbar in 2-3 Werktagen.
Noch 01:12:44
```

Navigation, Cookie-Hinweis, Sidebar und Footer verschwanden; Countdown und Lieferzeit blieben. **Daher brauchen wir eine eigene, kleine Nachbereinigung.** Sie ersetzt nur in vorab konfigurierten DOM-Knoten volatile Werte, etwa `Noch 01:12:44` -> `Noch <COUNTDOWN>`, und behaelt damit das rechtlich relevante Vorhandensein der Dringlichkeitsaussage. Keine globale Regex darf Daten, Preise, Mengen oder „nur heute“ entfernen.

### WARC: Wget, nicht pywb

Kleinster Weg fuer eine statische bzw. serverseitig gerenderte Seite:

```bash
wget --warc-file=capture --warc-cdx --page-requisites --span-hosts "https://example.org/page"
warcio check -v capture.warc.gz
```

Wget schreibt Request/Response, Digests und optional CDX; `--page-requisites` holt die fuer die Darstellung referenzierten Ressourcen ([GNU-Wget-Handbuch](https://www.gnu.org/software/wget/manual/wget.html)). `warcio check` prueft Block- und Payload-Digests ([warcio-Dokumentation](https://warcio.readthedocs.io/en/latest/)). Ein einmaliger Replay-Smoke-Test kann mit pywb als Entwicklungswerkzeug erfolgen; pywb ist keine Runtime-Abhaengigkeit.

Grenze: Wget fuehrt kein JavaScript aus. Fuer die Demo deshalb bekannte statische Zielseiten verwenden. Bei JS-Seiten im Beweispaket WARC, Playwright-HTML, Screenshot, Header und gemeinsame Zeit-/URL-Metadaten speichern und die moegliche Abweichung sichtbar markieren; keinen Browser-Recorder mehr in den Zwei-Tage-Scope ziehen.

### RFC 3161: aktueller funktionierender Minimalweg

Ein SHA-256-Hash wird direkt gestempelt; die Nutzdatei verlaesst das System nicht:

```bash
openssl ts -query -digest "$SHA256_HEX" -sha256 -cert -out hash.tsq
curl -H "Content-Type: application/timestamp-query" --data-binary @hash.tsq \
  https://freetsa.org/tsr -o hash.tsr
curl https://freetsa.org/files/tsa.crt -o tsa.crt
curl https://freetsa.org/files/cacert.pem -o cacert.pem
openssl ts -verify -in hash.tsr -queryfile hash.tsq \
  -CAfile cacert.pem -untrusted tsa.crt
```

Live getestet: `Status: Granted`, `Hash Algorithm: sha256`, `Verification: OK`. freeTSA dokumentiert Endpoint, Zertifikate und den Zertifikatswechsel selbst ([freeTSA](https://www.freetsa.org/index_en.php)). Zertifikatsdateien mit dem dort publizierten SHA-256 pruefen und im Beweispaket mitspeichern. `rfc3161ng` kann zwar aktuell ein Token anfordern und den Message-Imprint lesen, aber die Signatur des neuen EC-Zertifikats nicht verifizieren; deshalb nicht uebernehmen.

### Rechtsinformationen des Bundes

Direkt verwenden:

- `GET /v1/legislation?searchTerm=...&size=...`
- `GET /v1/case-law?searchTerm=...&court=...&dateFrom=...&dateTo=...&size=...`
- `GET /v1/document?searchTerm=...&size=...`
- Detailpfade aus `item.encoding[].contentUrl`, vorzugsweise XML oder HTML.

Antworten sind JSON-LD/Hydra: `totalItems`, `member[]`, darin `item` und `textMatches[]`; Gesetze tragen ELI-/Fassungsdaten und Entscheidungen Dokumentnummer, Gericht, Datum, Aktenzeichen sowie HTML/XML/ZIP-Encoding. Die aktuelle Spezifikation steht unter [OpenAPI](https://testphase.rechtsinformationen.bund.de/openapi.json), die [amtliche Dokumentation](https://docs.rechtsinformationen.bund.de/) nennt JSON, XML und HTML.

**Zitierfaehigkeit:** Gut als amtliche Fund- und Volltextquelle, wenn nicht der Such-Snippet, sondern der konkrete versionierte Detaildatensatz mit ELI bzw. Dokumentnummer, Datum, Aktenzeichen, Pinpoint und `contentUrl` zitiert wird. Nicht als alleinige dauerhafte Autoritaet behandeln: Der Betreiber kennzeichnet den Dienst als Testphase, den Datenbestand als unvollstaendig und Aenderungen als moeglich. Die API dokumentiert 600 Requests/Minute/IP; wir liegen mit Cache und Backoff weit darunter ([Rate Limit](https://docs.rechtsinformationen.bund.de/guides/rate-limiting/)).

Der MCP-Wrapper ist bereits partiell veraltet: Er sendet bei Rechtsprechung `limit`, waehrend die aktuelle API `size` erwartet (der Test lieferte deshalb die Default-Seitengroesse 100), verweist auf einen nicht mehr vorhandenen `/endpoints/`-Dokupfad und bildet aktuelle Endpunkte fuer Literatur, Verwaltungsvorschriften, Changelogs, Statistiken und Bulk-ZIP-Links nicht ab. Seine konkreten Behauptungen zu fehlenden Einzelgesetzen nicht uebernehmen; nur die amtliche API selbst als Quelle verwenden.

### Prompt-Muster fuer deutsches Recht

Nur diese Muster uebernehmen:

1. Ergebnis zuerst; dann `Rechtsfolge -> Norm -> Tatbestandsmerkmal -> konkrete Tatsache -> Beleg -> Subsumtion -> staerkstes Gegenargument -> Antwort`.
2. Aktenfund, verifizierte Rechtsquelle, Schlussfolgerung und offene Pruefung als getrennte Felder ausgeben.
3. Normzitat als `§ 433 Abs. 1 Satz 1 BGB` bzw. `Art. 6 Abs. 1 lit. f DSGVO`; Normstand vor tragender Aussage live pruefen.
4. Rechtsprechung nur mit Gericht, Entscheidungsform, Datum, Aktenzeichen, frei pruefbarer Quelle und echtem Pinpoint; keine BeckRS-/juris-, Kommentar- oder Aufsatzfundstelle aus Modellwissen.
5. Wenn die Quelle fehlt: `[nicht verifiziert]` und keine scheinpraezise Ergaenzung; menschliche Freigabe bleibt Pflicht.

Kritik: Das Repo enthaelt gute Anti-Blindzitat-Regeln, zugleich aber tausende repetitive/autogenerierte Skills, unscharfe Fachanker und unbelegte Einzelfallbehauptungen. Das Gesamtpaket wird ignoriert; die fuenf Regeln passen in unseren eigenen Systemprompt und Schema-Validator.

### Maximal fuenf Fundstellen aus Legal-Text-Analytics

1. [AGB-DE](https://github.com/DaBr01/AGB-DE) — direkt einschlaegiger deutscher Datensatz zur Erkennung unwirksamer Klauseln in Verbraucher-AGB; erste Wahl fuer eine kleine Eval.
2. [Legal Sentence Classification (German)](https://github.com/sebischair/Legal-Sentence-Classification-Datasets-and-Models) — zeigt deutschsprachige Satzklassifikation und ist als Muster fuer den Passage-Vorfilter nuetzlich.
3. [GerDaLIR](https://github.com/lavis-nlp/GerDaLIR) — deutscher Legal-IR-Datensatz fuer Retrieval-Evaluation, sinnvoll zum Testen des lokalen Passage-Finders.
4. [Corpus des Deutschen Bundesrechts (C-DBR)](https://doi.org/10.5281/zenodo.3832111) — amtlichkeitsnahes Normkorpus fuer Paragraphen- und Zitier-Checks, nicht fuer Kerngleichheitstraining.
5. [CUAD](https://www.atticusprojectai.org/cuad) — englischer, fachlich annotierter Klauseldatensatz; nur dessen Label-/Annotationsschema uebernehmen, nicht die Sprachdaten als deutsche Eval ausgeben.

### Wayback als Eval-Zeitmaschine

Alle erfassten Snapshots eines kanonischen URL-Schluessels im Zeitraum:

```text
GET https://web.archive.org/cdx/search/cdx
  ?url=https%3A%2F%2Fexample.org%2Fpage
  &matchType=exact
  &from=20240101000000
  &to=20241231235959
  &output=json
  &fl=urlkey,timestamp,original,statuscode,mimetype,digest
  &showResumeKey=true
  &limit=1000
```

`from`/`to` sind inklusiv und duerfen 1 bis 14 Stellen haben. Fuer buchstaeblich alle Captures keine Filter und kein `collapse` setzen; fuer eine Inhalts-Eval sind zusaetzlich `filter=statuscode:200`, `filter=mimetype:text/html` und optional `collapse=digest` sinnvoll. Wegen URL-Kanonisierung koennen HTTP/HTTPS- oder `www`-Varianten im selben Schluessel erscheinen; bei Bedarf auch `original` streng filtern. Grosse Ergebnisse mit dem von `showResumeKey=true` gelieferten Schluessel und `resumeKey=...` fortsetzen. Das ist in der [primaeren CDX-Dokumentation](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md) beschrieben und wurde gegen den Live-Endpoint getestet.

**Save Page Now:** SPN2 ist der dokumentierte asynchrone Weg: authentifizierter `POST https://web.archive.org/save` mit `url=...` liefert `job_id`; `GET /save/status/{job_id}` liefert bei Erfolg `timestamp` und `original_url`, daraus entsteht `https://web.archive.org/web/{timestamp}/{original_url}`. Die [SPN2-Dokumentation](https://docs.google.com/document/d/1Nsv52MvSjbLb2PCpHlat0gkzw0EvtSgpKHu4mk0MnrA/) ist allerdings weiterhin als Public-API-Draft publiziert. Der Systemstatus war im Test `200 {"status":"ok"}`. Entscheidung: als zusaetzliche Bestaetigung mit Timeout, Backoff und Fehlerstatus nutzen, nie als Primaerbeweis oder synchronen Erfolgs-Garant.

## 2. Konkrete Normalisierungs-Pipeline fuer Stufe 1

1. **Zulaessigkeit und Abrufprofil:** `robots.txt` pruefen; pro URL Fetch-Modus, User-Agent, Locale, Zeitzone und bei Playwright Viewport festschreiben.
2. **Abrufen:** HTTP zuerst; Playwright nur fuer vorher klassifizierte JS-Seiten. Status, finale URL, Redirectkette, Header und rohe Bytes unveraendert lokal speichern, aber noch nicht taeglich als WARC.
3. **DOM gezielt begrenzen:** Optionaler, pro URL getesteter Include-Selektor; dann `script`, `style`, `noscript`, `template`, Navigation, Footer, Werbung und Consent-Knoten ueber strukturelle und versionierte Selektoren entfernen. Ein leerer Include-Treffer ist Fehler, kein leerer Snapshot.
4. **Volatile Widgets kanonisieren:** Nur in konfigurierten Knoten Countdown-/Bestandszahlen durch typisierte Marker ersetzen; Session-IDs in sichtbarem Text ebenso. Aussage und Kontext bleiben stehen.
5. **Trafilatura:** Mit den oben festgelegten Optionen Haupttext extrahieren; Tabellen behalten, weil Preise und Bedingungen dort stehen koennen.
6. **Text kanonisieren:** Unicode NFC, `CRLF/CR -> LF`, NBSP -> Leerzeichen, horizontale Leerzeichen zusammenziehen, Zeilen trimmen, hoechstens eine Leerzeile; Reihenfolge, Grossschreibung, Preise, Daten und Mengen sonst unangetastet lassen.
7. **Hash und Vergleich:** SHA-256 ueber UTF-8-Text; daneben `normalizer_version`, Hash der Selektorkonfiguration, Fetch-Modus und Pfad zum Rohsnapshot speichern. Nur Hashes derselben Version vergleichen; bei Regelwechsel neue Baseline statt Fehlalarm.

Warum stabil: Globale Seiten-Chrome und bekannte Tick-Werte verschwinden, waehrend rechtlich relevante Formulierungen, Reihenfolge und das Vorhandensein von Countdown/Knappheit erhalten bleiben. Warum nachvollziehbar: Rohdaten bleiben separat unveraendert und jede Unterdrueckung ist URL-spezifisch versioniert.

## 3. Drei Deadline-Risiken

| Risiko | Gegenmittel |
| --- | --- |
| Normalisierung unterdrueckt einen echten Verstoss oder produziert taegliches Rauschen. | Pro Zielseite drei eingefrorene HTML-Fixtures (gleich, nur volatil, echter Inhalt) und Golden-Text/Hash; neue Selektoren nur nach menschlicher Sichtung. |
| WARC und Playwright-Screenshot zeigen bei JS-Seiten nicht exakt denselben Zustand. | Demo auf statische/SSR-Seiten begrenzen; alle Artefakte in einem Lauf mit URL/Zeit/Hash-Manifest erfassen und die JS-Grenze im Paket ausweisen. |
| freeTSA, Wayback oder die Testphasen-Rechts-API aendern sich/fallen aus. | Lokale Rohbeweise bleiben primaer; OpenSSL statt `rfc3161ng`, Retries/Backoff, gespeicherte Zertifikate und SPN/Rechts-API als optionale Anreicherung mit sichtbarem Fehlerstatus. |

## 4. Anti-Bot-Stellen und legaler Umgang

| Stelle | Erwartbares Problem | Erlaubtes Vorgehen im Projekt |
| --- | --- | --- |
| Shops/PDP/Checkout | Cloudflare/Akamai, 403/429, JS-Challenge, CAPTCHA, wechselndes DOM | `robots.txt` respektieren, identifizierbarer UA, niedrige Host-Rate, Cache/ETag, Backoff; Playwright nur zum normalen Rendern oeffentlicher Seiten; bei Challenge abbrechen und manuelle/erlaubte Aufnahme oder Zustimmung einholen. |
| Wayback CDX/SPN2 | Quoten, Ueberlastung, blockierte Ziel-URL oder Zielserver blockiert Archive-IP | Ergebnisse cachen, Resume-Key/Pagination, authentifizierten eigenen Account, Backoff und Fehler als Befund; keine Quoten- oder IP-Umgehung. |
| Rechtsinformationen-API | 503 oberhalb 600 RPM/IP, Schemaaenderung in der Testphase | Weit unter Limit bleiben, `view.next` folgen, Cache, exponentieller Backoff und Schema-Contract-Test gegen OpenAPI. |
| freeTSA | Verfuegbarkeit, Zertifikatsrotation, ausdrueckliches „do not abuse“ | Nur Stufe-4-Hashes einzeln senden, Timeout/Retry begrenzen, aktuelle Zertifikate und Fingerprints sichern, lokal mit Vertrauenskette verifizieren. |

Ausgeschlossen bleiben Login-/Paywall-Umgehung, CAPTCHA-Loesung, Stealth-/Fingerprint-Manipulation, rotierende Proxies, fremde Cookies oder jede andere Umgehung technischer Schutzmassnahmen. Blockiert eine Seite den normalen oeffentlichen Zugriff, ist das ein dokumentierter manueller Fall und kein Engineering-Problem, das wir „wegautomatisieren“.
