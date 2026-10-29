# Migrationsgrundsätze für Code-Tabellen (Arbeitsstand)

> **Status: Arbeitsannahmen.** Diese Grundsätze sind ein Vorschlag als Startpunkt für
> Phase 2. Sie sind mit Buchhaltung, NAV-/BC-Partner und ggf. Steuerberatung/Wirtschafts-
> prüfung abzustimmen. Bestätigte Punkte bitte mit Datum und Person kennzeichnen.
> Bei Widerspruch zum Data Quality Handbook gilt das Handbook. Der Agent meldet den
> Widerspruch als offene Frage.

## 1. Ziel

Jeder Code, der jemals in einem gebuchten Beleg oder Posten verwendet wurde, muss auch
nach der Umstellung in seiner **damaligen Bedeutung** erklärbar sein. Das leistet der
Crosswalk `output/crosswalk_alt_neu.csv`. Er ist Teil der Verfahrensdokumentation
im Sinne der GoBD und wird so lange aufbewahrt wie die Buchungsdaten, auf die er sich
bezieht (§ 147 AO; Fristen je nach Unterlagenart, mit Steuerberatung klären).

## 2. Begriffe

| Fachbereich sagt | heißt im Konzept | technisch |
|---|---|---|
| behalten | `behalten` | Code wird unverändert übernommen |
| umbenennen | `umbenennen` | neuer Code in BC, alter Code über Mapping |
| zusammenlegen | `zusammenfuehren` | mehrere alte Codes → ein neuer Code |
| löschen | `sperren` **oder** `nicht_migrieren` | **nie physisch löschen, solange er in gebuchten Daten vorkommt** |

## 3. Was in NAV *vor* der Migration passieren darf

Erlaubt (`zeitpunkt: vor_migration`):
* Beschreibungen ergänzen oder korrigieren, vor allem leere Beschreibungen. Das verbessert
  den Prüfpfad und ändert keine Buchung.
* Codes für die **künftige** Verwendung sperren (sofern die Tabelle ein Sperrkennzeichen hat
  oder per Berechtigung/Prozess), damit keine neuen Belege mehr damit entstehen.
* Codes ohne jede Verwendung dürfen entfernt werden. Die Entfernung wird im Crosswalk
  dokumentiert. *Wo* eine Code-Tabelle verwendet wird, steht im Handbook
  (`context/verwendungen.yaml`). *Ob ein einzelner Code* dort tatsächlich vorkommt, belegt
  nur eine Zählung in NAV (`input/nav_exports/`). Ohne diese Zählung gilt bei Tabellen mit
  Verwendung in gebuchten Daten jeder Code als verwendet und wird gesperrt statt entfernt.

Nicht erlaubt bzw. nur nach ausdrücklicher Freigabe:
* **Umbenennen in NAV.** Arbeitsannahme, beim NAV-Partner zu bestätigen: Eine Umbenennung
  (RENAME) des Primärschlüssels schreibt den neuen Wert in alle Datensätze mit
  Tabellenrelation auf diese Tabelle, auch in gebuchte Posten. Die historischen Daten
  zeigen danach einen Code, der zum Buchungszeitpunkt nicht existierte.
* **Löschen verwendeter Codes.** NAV verhindert das Löschen eines referenzierten Codes in der
  Regel nicht. Die Verweise in gebuchten Daten zeigen dann ins Leere und die Bedeutung ist
  im System nicht mehr nachvollziehbar.

## 4. Was *während* der Migration passiert (`zeitpunkt: migration`)

* Umbenennungen und Zusammenführungen werden als Mapping im Migrationsweg umgesetzt.
* Welche Daten migriert werden (nur Stammdaten + offene Posten oder auch Historie), legt
  das Migrationsprojekt fest. Bleibt die Historie in NAV, ist der Crosswalk die Brücke
  zwischen alten und neuen Codes und das NAV-System bzw. ein Datenexport muss für den
  Datenzugriff der Finanzverwaltung verfügbar bleiben.
* Codes mit `nicht_migrieren` dürfen in keinem migrierten offenen Beleg vorkommen. Prüfung
  vor dem Cut-over gegen die offenen Posten.

## 5. Was *nach* der Umstellung passiert (`zeitpunkt: nach_migration`)

* Neue Code-Strukturen, die BC-Funktionen oder geänderte Prozesse voraussetzen.
* Endgültige Bereinigung von Codes, die nur noch in archivierter Historie vorkommen.

## 6. Technische Prüfpunkte je Code

* Länge und Zeichen: Codes mit Leerzeichen, `/`, `.` oder Filterzeichen (`& | ( ) < > = * @ ? ' "`, `..`)
  können in BC beim Filtern, in Schnittstellen oder Exporten stören. Für neue Codes vermeiden.
  Für alte Codes nur über Mapping ändern (siehe 3.).
* In Excel als Zahl gespeicherte Codes: führende Nullen können verloren sein. Immer gegen
  den NAV-Export abgleichen, nie gegen die Excel-Darstellung.
* Umlaute (Ä, Ö, Ü, ß) funktionieren in BC, können aber in Schnittstellen problematisch sein.
  Das wird je Schnittstelle geprüft.

## 7. Freigabe

Jede Zeile im Crosswalk braucht vor der Umsetzung eine Freigabe durch den verantwortlichen
Fachbereich (`freigabe.durch`, `freigabe.datum`). Antworten auf offene Fragen werden mit
Person und Datum in `state/offene_fragen.yaml` festgehalten.
