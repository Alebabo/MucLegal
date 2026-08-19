# Live-Eval-Baseline vom 19.08.2026

## Ergebnis

**Status: BESTANDEN**

- Modus: `live_anthropic`
- Modell: `claude-sonnet-5`
- Eval-Suite: `muclegal-golden-path-v1`, Version 1
- Prompt-Version: `2026-08-19-freeze-candidate-1`
- Prompt-SHA-256: `6c0e6c09e73faa18cc2c1ea196a7e18d1bdc01ec67708c463e8a3ca037be9289`
- Lauf beendet: `2026-08-19T08:57:00.878145+00:00`

## Qualitäts-Gates

| Metrik | Ergebnis | Gate | Status |
|---|---:|---:|---|
| Schema-Validität | 100 % | 100 % | bestanden |
| Erwartetes Ergebnis | 100 % | 100 % | bestanden |
| Menschliche Freigabe bleibt `null` | 100 % | 100 % | bestanden |
| Begründung vorhanden | 100 % | 100 % | bestanden |
| Stärkstes Gegenargument vorhanden | 100 % | 100 % | bestanden |

## Fälle

| Fall | Erwartet | Tatsächlich | Schema | Dauer |
|---|---|---|---|---:|
| `kerngleiche-restmengenanzeige` | `kerngleich_umfasst` | `kerngleich_umfasst` | valide | 22.410 ms |
| `echte-befristete-aktion` | `nicht_umfasst` | `nicht_umfasst` | valide | 24.891 ms |

## Technischer Kontext

Ein erster Lauf zeigte zwei relevante Adapterprobleme: Ein Output wurde durch das zu knappe
Token-Limit abgeschnitten, ein weiterer enthielt ein leeres Pflichtfeld. Vor dem erfolgreichen
Baseline-Lauf wurden deshalb das Output-Limit erhöht, der API-Stop-Grund ausdrücklich geprüft
und die Anforderungen an nichtleere Pflichtfelder im Ausgabeschema beschrieben. Der lokale
Validator blieb unverändert streng. Der juristische System-Prompt wurde nicht verändert; sein
oben dokumentierter SHA-256 ist identisch mit dem eingefrorenen Kandidaten.

Diese Baseline umfasst zwei synthetische Golden-Path-Fälle. Sie belegt die Funktionsfähigkeit
der Live-Schnittstelle und der definierten Qualitäts-Gates, ist aber keine statistisch belastbare
Aussage über die allgemeine juristische Modellgenauigkeit und keine abschließende Rechtsentscheidung.
