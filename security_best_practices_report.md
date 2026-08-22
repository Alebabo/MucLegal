# Security-Best-Practices-Review

Stand: 19.08.2026. Geprüft wurden der lokale FastAPI-/Jinja-Server, das eingebettete
JavaScript, ausgehende HTTP-Abrufe und die lokale Artefaktausgabe.

## Kurzfazit

Keine kritischen oder hohen Befunde. Die Anwendung ist weiterhin ausdrücklich ein lokal auf
`127.0.0.1` betriebenes Ein-Nutzer-Werkzeug ohne Login. Host-Allowlist, Größenlimit,
Origin-Prüfung, schema-strikte Schreib-APIs, CSP, inerte HTML-Ausgabe und die Ablehnung privater
Ziele sind im Anwendungscode umgesetzt und automatisiert getestet.

## Mittlere Befunde

### SEC-001 - DNS-Auflösung und Verbindungsaufbau sind nicht atomar

- **Schweregrad:** Mittel im Fall eines öffentlich erreichbaren Servers; niedrig im vorgesehenen lokalen Betrieb.
- **Ort:** `muclegal/fetch/http.py`, `_validate_url` Zeilen 98-123 und `_fetch_once` ab Zeile 165.
- **Evidenz:** Öffentliche IP-Adressen werden mit `socket.getaddrinfo` geprüft; `urllib` löst den Host beim späteren Verbindungsaufbau erneut auf.
- **Auswirkung:** Ein kontrollierter DNS-Name könnte zwischen Prüfung und Verbindung auf eine private Adresse wechseln.
- **Mitigation:** Der Server bleibt ausschließlich an `127.0.0.1` gebunden, Redirectziele werden erneut geprüft und die primäre WARC-Datei wird ohne zweiten Netzabruf aus den bereits geprüften Snapshotbytes erzeugt.
- **Empfohlene spätere Behebung:** Für einen produktiven Mehrnutzerbetrieb einen HTTP-Client mit gepinnter, geprüfter Ziel-IP und korrektem TLS-SNI/Host-Header oder einen ausgehenden Proxy mit Netzwerk-Allowlist verwenden.

## Niedrige Befunde

### SEC-002 - Inline-CSS und Inline-JavaScript benötigen CSP-Ausnahmen

- **Schweregrad:** Niedrig.
- **Ort:** `muclegal/ui.py` Zeilen 424-445 und `muclegal/templates/case.html`.
- **Evidenz:** Die CSP erlaubt wegen der absichtlich einzelnen HTML-Datei `unsafe-inline` für Styles und Skripte.
- **Auswirkung:** Eine zukünftige Escaping-Lücke hätte weniger CSP-Abwehrtiefe.
- **Bestehende Kontrollen:** Jinja-Autoescaping, keine Nutzung von `innerHTML`, dynamische Inhalte werden mit `textContent` gesetzt, Roh-HTML wird als `text/plain` und Download ausgeliefert.
- **Empfohlene spätere Behebung:** CSS und JavaScript in statische Dateien auslagern und `unsafe-inline` aus der CSP entfernen.

## Verifizierte Kontrollen

- `TrustedHostMiddleware` erlaubt nur `127.0.0.1`, `localhost` und den Testhost.
- Zustandsändernde Browseranfragen fremder Origins sowie Körper über 64 KiB werden abgewiesen.
- URL-Zugangsdaten, private/netzinterne Ziele, Loginseiten, CAPTCHAs und robots.txt-Verbote werden abgebrochen.
- Unbekannte JSON-Felder werden in Run- und Tenor-APIs abgelehnt.
- Modelloutputs können keine menschliche Freigabe setzen und keine unbelegte Rechtsgrundlage in einen Tenorentwurf einschleusen.
- Artefaktpfade bleiben innerhalb der lokalen Ablage; Roh-HTML wird nie aktiv im App-Origin gerendert.
- API-Schlüssel werden nur aus Server-Umgebungsvariablen gelesen und nicht an den Browser ausgegeben.
