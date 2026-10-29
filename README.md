<<<<<<< HEAD
# data_transformation
=======
# NAV → BC: Harmonisierung der Code-Tabellen

Arbeitsrepository, in dem Claude und Codex die Bereinigungstabellen der Fachbereiche
in mehreren Sitzungen systematisch abarbeiten. Der Fortschritt steht vollständig im
Repository (`state/`), deshalb kann jede Sitzung nach einem Abbruch nahtlos weitermachen.

**Für Agenten gilt `AGENTS.md`.** Diese Datei hier ist für Menschen.

## Einrichtung

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
git init && git add -A && git commit -m "Ausgangsstand"
```

Das Repository enthält firmeninterne Daten. Es darf nur in internen Git-Systemen liegen.

## Ablauf

```
 input/raw/*.xlsx ──p0_extract──▶ work/extrakt/ (Zellen + Vorschau + Layout-Signatur)
                                        │
            Agent schreibt profile/*.yaml (eins je Layout-Gruppe)
                                        │
                  ──p1_apply──▶ work/normalisiert/ (einheitliches Schema + Bericht)
                                        │   Validierung: jede Zelle verwertet, nichts geraten
                  ──p1_consolidate──▶ work/konsolidiert/ (je NAV-Tabelle)
            Agent überträgt Verwendungsorte aus dem Handbook → context/verwendungen.yaml
                                        │   (in gebuchten Daten? → bestimmt den Zeitpunkt)
                                        │
            Agent schreibt work/einordnung/*.yaml (Aktion + Zeitpunkt je Code)
                                        │
                  ──p3_build_crosswalk──▶ output/crosswalk_alt_neu.csv  ◀── Prüfdokument
                                          output/konzept.md
```

Warum Profile statt „Agent liest jede Datei“: Bei einigen hundert Dateien gibt es
erfahrungsgemäß deutlich weniger verschiedene Layouts. Der Agent interpretiert jedes
Layout einmal, und das Skript wendet die Interpretation deterministisch an. Jede
Interpretation steht damit nachvollziehbar in einer Datei. Wird ein Profil korrigiert,
werden alle betroffenen Blätter automatisch neu erzeugt.

## Agent starten

Claude Code oder Codex im Repository-Ordner öffnen und zum Beispiel sagen:

> Lies AGENTS.md und arbeite Einheiten aus der Queue ab, bis keine startbare mehr übrig ist
> oder dein Kontext knapp wird. Committe nach jeder Einheit.

Beide Agenten lesen dieselbe Anweisung (`CLAUDE.md` bindet `AGENTS.md` ein).
Nicht beide gleichzeitig auf derselben Queue arbeiten lassen. Empfohlen: einer bearbeitet,
der andere reviewt (siehe Vier-Augen-Prinzip in AGENTS.md).

## Was Menschen tun

| Wann | Was |
|---|---|
| Start | Bereinigungstabellen nach `input/raw/` legen, gern in Unterordnern je Fachbereich (der Ordnername wird als Fachbereich übernommen). Dann `python scripts/p0_extract.py`. |
| Start | Data Quality Handbook als Markdown nach `context/data_quality_handbook.md`. |
| Start | `context/migrationsgrundsaetze.md` mit Buchhaltung/Partner abstimmen. |
| vor Phase 2 | Optional: Verwendungszahlen je Code nach `input/nav_exports/`, nur nötig, um Codes schon vor der Migration zu entfernen (siehe LIESMICH dort). |
| laufend | Offene Fragen: `python scripts/fragen.py export` → `output/offene_fragen.csv` an die Fachbereiche geben, Antworten mit `fragen.py antwort F-00x --von "Name" "…"` eintragen. |
| laufend | Neue oder überarbeitete Excel-Dateien einfach nach `input/raw/` legen und `p0_extract.py` ausführen. Geänderte Blätter werden automatisch wieder geöffnet. |
| Ende | Crosswalk prüfen und Freigaben eintragen. |

Fortschritt jederzeit: `python scripts/queue_cli.py status`

## Beispielstand in diesem Repository

Das Repository enthält deine drei Beispieldateien, und Phase 1 ist dafür bereits
einmal durchgelaufen (Profile in `profile/`, Ergebnisse in `work/`, Fragen in `state/`).
Das zeigt, wie die Ergebnisse aussehen. Für den echten Start zurücksetzen:

```bash
rm -rf state/* work/extrakt work/normalisiert work/konsolidiert output/* profile/L*.yaml input/raw/*.xlsx
```

## Grenzen

* Nur `.xlsx`/`.xlsm`. Alte `.xls`-Dateien werden im Manifest als nicht lesbar markiert
  (Umwandlung z. B. mit `soffice --headless --convert-to xlsx *.xls`).
* Profiltypen: `liste` und `matrix`. Taucht ein Layout auf, das keins von beiden ist,
  kann der Agent `p1_apply.py` um einen Typ erweitern. Das ist eine eigene Einheit und
  wird reviewt.
>>>>>>> master
