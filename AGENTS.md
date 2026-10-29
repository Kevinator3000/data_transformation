# Arbeitsanweisung für Agenten (Codex, Claude)

Du hilfst, die Code-Tabellen aus Dynamics NAV für die Migration nach Business Central
zu harmonisieren. Die Fachbereiche haben ihre Codes in Excel-Tabellen bewertet,
uneinheitlich und teils widersprüchlich. Deine Aufgabe ist es, diese Bewertungen
**nachvollziehbar** zu verstehen, gegen das Data Quality Handbook einzuordnen und am
Ende einen Crosswalk (alter Code → neuer Code, mit Begründung und Zeitpunkt) zu
erstellen, den die Buchhaltung einem Wirtschaftsprüfer vorlegen kann.

**Prüfpfad vor Geschwindigkeit.** Jede Aussage im Ergebnis muss auf eine Quellzelle,
eine Profilregel, eine beantwortete Frage oder einen Abschnitt im Handbook
zurückführbar sein.

Sprache in allen Dateien: Deutsch.

---

## Startroutine (jede Sitzung, ohne Ausnahme)

```bash
python scripts/queue_cli.py status
tail -n 15 state/session_log.md
```

1. Steht eine Einheit auf `in_progress`, wurde die letzte Sitzung unterbrochen.
   Bearbeite **genau diese** Einheit von vorn. Teilergebnisse dürfen überschrieben werden,
   denn alle Ergebnisse sind pro Einheit idempotent.
2. Sonst: Nimm die angezeigte nächste startbare Einheit.
3. Steht etwas auf `review` und du bist nicht der Agent, der es bearbeitet hat:
   Prüfe es zuerst (siehe Vier-Augen-Prinzip).

## Arbeitsschleife (eine Einheit pro Durchlauf)

```bash
python scripts/queue_cli.py start <ID> --agent <claude|codex>
# … Einheit bearbeiten (siehe Einheitentypen) …
python scripts/queue_cli.py done <ID> --agent <…> -m "1–3 Sätze: Ergebnis, Annahmen, Frage-IDs"
git add -A && git commit -m "<ID>: <Kurzfassung>"
```

* `done`/`submit` bei Phase-1-Einheiten führt die Validierung aus und **verweigert** den
  Abschluss, solange Fehler bestehen. Umgehe das nicht, sondern behebe die Ursache.
* Wird dein Kontext knapp: Schließe die laufende Einheit ab oder lass sie sauber auf
  `in_progress` stehen. **Beginne keine neue Einheit**, die du nicht beenden kannst.
* Kannst du eine Einheit nicht abschließen (fehlende Daten, Handbook fehlt …):
  `queue_cli.py block <ID> -m "Grund"` und weiter zur nächsten.

## Goldene Regeln

1. **Quellen sind unantastbar.** `input/raw/` und `input/nav_exports/` niemals ändern.
2. **Nicht raten.** Wenn eine Bewertung mehrdeutig ist, ist der Status `unklar` und es
   wird eine Frage erfasst (`scripts/fragen.py neu …`). Eine Hypothese darfst du in der
   Frage notieren (`--hypothese`), aber nicht als Ergebnis verwenden.
3. **Annahmen markieren.** Interpretierst du eine Spaltenbedeutung (z. B. „relevant = nein“
   ⇒ verwerfen), steht das als `annahme` in der Profilregel *und* es gibt eine Frage zur
   Bestätigung.
4. **Mechanik gehört in Skripte.** Kopiere keine Codes von Hand in Ergebnisdateien. Du
   schreibst Profile und Entscheidungen, die Skripte erzeugen die Tabellen.
5. **Keine Codes erfinden.** Neue Zielcodes gibt es erst in Phase 2, und dann nur mit
   Begründung.
6. **„Löschen“ heißt nicht löschen.** Ein Code, den ein Fachbereich „löschen“ will, kann in
   gebuchten Posten stehen. Was technisch daraus wird (sperren, nicht migrieren …),
   entscheidet erst Phase 2 nach `context/migrationsgrundsaetze.md`.
7. **Nur lesen, was du brauchst.** Für die Profilarbeit reicht die Vorschau
   (`work/extrakt/<blatt_id>.vorschau.md`). Rohdaten (`.jsonl`) nur gezielt mit `grep`.

## Verzeichnisse

| Pfad | Inhalt | wer schreibt |
|---|---|---|
| `input/raw/` | Bereinigungstabellen der Fachbereiche | Mensch |
| `input/nav_exports/` | optional: Verwendungszahlen je Code aus NAV (siehe LIESMICH dort) | Mensch |
| `context/` | Data Quality Handbook, Migrationsgrundsätze, Glossar | Mensch |
| `context/verwendungen.yaml` | Verwendungsorte je Code-Tabelle, aus dem Handbook übertragen | Agent |
| `state/manifest.yaml` | Dateien, Blätter, Signaturen; **du pflegst** `nav_tabelle`, `fachbereich`, `profil` | Skript + Agent |
| `state/queue.yaml` | Arbeitseinheiten und Status, nur über `queue_cli.py` ändern | Skript |
| `state/session_log.md` | append-only Protokoll | Skript |
| `state/offene_fragen.yaml` | Fragen an Fachbereiche, nur über `fragen.py` | Skript |
| `profile/<id>.yaml` | Layout-Profile (Referenz: `profile/_referenz.yaml`) | Agent |
| `work/extrakt/` | Rohextraktion + Vorschau je Blatt | Skript |
| `work/normalisiert/` | einheitliches Schema je Blatt + Bericht | Skript |
| `work/konsolidiert/` | je NAV-Tabelle ein Code pro Zeile | Skript |
| `work/einordnung/<tabelle>.yaml` | Entscheidungen Phase 2 (Vorlage: `_vorlage.yaml`) | Agent |
| `output/` | Crosswalk, Konzept, Fragen-Export | Skript + Agent |

## Einheitentypen

### P1-PROFIL-&lt;signatur&gt;: Layout verstehen

Ziel: ein Profil, mit dem `p1_apply.py` alle Blätter dieser Layout-Gruppe fehlerfrei
und vollständig in das Normalschema überführt.

1. Vorschau(en) der Ziel-Blätter lesen (`queue_cli.py show <ID>` zeigt sie).
2. `profile/<signatur>.yaml` nach `profile/_referenz.yaml` schreiben. Achte besonders auf:
   * **Statusquelle:** Text (Behalten/Löschen, ja/nein, x …), Farbe oder beides?
   * **Farben:** Nur dann als Statusquelle, wenn eine Legende existiert oder der Text sie
     bestätigt. Sonst nur `bedeutung` eintragen, damit der Status `unklar` bleibt.
   * **Lose Notizen:** Spalten, deren Inhalt nicht zur Zeile gehört (siehe Beispiel
     Abwartengründe, Spalte F) → `lose_notizen`.
   * **Matrix-Layouts:** Kopfzeile sind Codes, darunter zugeordnete Codes → `typ: matrix`.
3. `python scripts/p1_apply.py --profil <signatur>`, dann den Bericht lesen.
4. `nicht_abgedeckt` muss leer sein. Jede Zelle wird verbraucht oder mit Grund ignoriert.
5. Für `unklar`-Datensätze und Annahmen Fragen erfassen.
6. Passen einzelne Blätter der Gruppe nicht: im Manifest bei diesem Blatt `profil` auf eine
   neue ID setzen, `queue_cli.py sync`, dafür entsteht eine eigene Profil-Einheit.

### P1-PRUEFUNG-&lt;blatt_id&gt;: Ergebnis inhaltlich prüfen

1. `work/normalisiert/<blatt_id>.bericht.json` und die CSV prüfen.
2. Hinweise auswerten (`leere_beschreibung`, `behalten_ohne_nutzung`, `code_als_zahl_in_excel`,
   `notiz_widerspricht_status` …). Für jeden Hinweis, der eine Entscheidung beeinflusst,
   wird eine Frage erfasst.
3. Fachliche Auffälligkeiten suchen, die kein Skript findet: Beschreibung passt nicht zum
   Code, Lücken in Nummernserien, Beziehungen zu anderen Blättern.
4. Im Manifest `nav_tabelle` (mit `nav_tabelle_quelle`) und ggf. `fachbereich` setzen.
5. Abschluss-Notiz: Zahlen + Frage-IDs.

### P1-KONSOLIDIERUNG

`python scripts/p1_consolidate.py`, dann Konflikte (`status_gesamt = konflikt`) prüfen:
Für jeden Konflikt wird eine Frage an beide Fachbereiche gerichtet. Codes mit
`nicht_bewertet` (in NAV vorhanden, von niemandem bewertet) sammeln und dafür eine
Sammelfrage stellen.

### P1-VERWENDUNGEN: Verwendungsorte aus dem Handbook

Das Handbook beschreibt, wo jede Code-Tabelle verwendet wird. Diese Information
entscheidet später, ob ein Code vor der Migration in NAV geändert werden darf.

1. Ist `context/data_quality_handbook.md` noch ein Platzhalter → `block`.
2. Für jede `nav_tabelle` aus dem Manifest in `context/verwendungen.yaml` eintragen:
   `handbook_bezug`, optional `nav_tabelle_id`, und je Verwendungsort `tabelle`, `feld`, `art`
   (`einrichtung | stammdaten | beleg_offen | gebucht | archiv`) mit eigenem `handbook_bezug`.
   Postentabellen (Debitoren-, Kreditoren-, Sach-, Artikelposten …) und gebuchte Belege
   zählen immer als `gebucht`, auch wenn der Posten noch offen ist.
3. Heißt eine Tabelle im Handbook anders als im Manifest (dort stehen bisher nur
   Vorschläge aus dem Blattnamen): **Manifest an das Handbook angleichen**,
   `nav_tabelle_quelle` auf den Handbook-Abschnitt setzen, danach `p1_consolidate.py`.
4. Behandelt das Handbook eine Tabelle nicht oder nur teilweise: Frage erfassen und
   `frage: F-0xx` bzw. `unvollstaendig: true` setzen. Nicht aus dem Feldnamen raten.
5. `python scripts/verwendungen.py check` muss grün sein (Gate bei `done`), dann
   `python scripts/p1_consolidate.py`. Die Konsolidierung erhält dadurch die Spalten
   `verwendet_in` und `in_gebuchten_daten`.

### P2-EINORDNUNG-&lt;tabelle&gt;: Aktion und Zeitpunkt

Voraussetzungen: P1-VERWENDUNGEN erledigt, `context/data_quality_handbook.md` und
`context/migrationsgrundsaetze.md` gelesen. Maßgeblich ist die Spalte
`in_gebuchten_daten` der Konsolidierung:

* `ja` oder `unbekannt` → Umbenennen/Zusammenführen nur `zeitpunkt: migration` (Mapping);
  Entfernen vor der Migration nur, wenn der NAV-Export 0 gebuchte Verwendungen belegt,
  sonst `sperren`. `p3_build_crosswalk.py` prüft das.
* `nein` → Änderungen vor der Migration in NAV sind möglich.

Für jeden Code in `work/konsolidiert/<tabelle>.csv` eine Entscheidung in
`work/einordnung/<tabelle>.yaml` (Vorlage `_vorlage.yaml`):
`aktion` (behalten | umbenennen | zusammenfuehren | sperren | nicht_migrieren),
`code_neu`, `zeitpunkt` (vor_migration | migration | nach_migration), `begruendung`,
`handbook_bezug`. Codes mit offenen Fragen bekommen eine Entscheidung erst nach der Antwort.
Bis dahin lässt du sie weg, die Einheit bleibt dann `blocked`.

### P3-CROSSWALK / P3-KONZEPT

`python scripts/p3_build_crosswalk.py` muss ohne Fehler laufen. Danach `output/konzept.md`:
Vorgehen je Zeitpunkt, Liste der Vor-Migrations-Maßnahmen in NAV, Mapping-Regeln für die
Migration, offene Punkte, Verweis auf den Crosswalk als Prüfdokument.

## Vier-Augen-Prinzip (optional, empfohlen ab Phase 2)

Bearbeiter schließt mit `submit` statt `done` ab (Status `review`). Der jeweils andere Agent
prüft und setzt `done --agent <reviewer>` oder `reopen -m "Begründung"`.

## Befehlsübersicht

```bash
python scripts/queue_cli.py status|next|show <ID>|start|submit|done|block|reopen|sync
python scripts/p0_extract.py              # nach neuen/geänderten Dateien in input/raw
python scripts/p1_apply.py --profil <id>  # Profil anwenden
python scripts/p1_validate.py [blatt_id]  # prüfen
python scripts/p1_consolidate.py
python scripts/verwendungen.py check
python scripts/fragen.py neu --frage "…" --bezug <blatt_id[:zelle]> … --an "…" --einheit <ID> [--hypothese "…"]
python scripts/fragen.py liste | antwort F-001 --von "Name" "…" | export
python scripts/p3_build_crosswalk.py
```
