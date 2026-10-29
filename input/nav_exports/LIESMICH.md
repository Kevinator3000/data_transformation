# NAV-Exporte

Pro Code-Tabelle eine CSV-Datei, Name = Tabellenname wie in `state/manifest.yaml`
(`nav_tabelle`) in Kleinbuchstaben, Umlaute ausgeschrieben, Sonderzeichen → `_`
(z. B. `Hauptreklamationsgrund` → `hauptreklamationsgrund.csv`).

Trennzeichen `;`, UTF-8, Spalten:

| Spalte | Inhalt |
|---|---|
| `code` | Code exakt wie in NAV |
| `beschreibung` | Beschreibung aus NAV |
| `anzahl_gebuchte_verwendungen` | Anzahl Verweise aus **gebuchten** Belegen/Posten |
| `letzte_verwendung` | Datum der letzten Verwendung (JJJJ-MM-TT) |

**Optional.** Wo eine Code-Tabelle verwendet wird, kommt aus dem Data Quality Handbook
(`context/verwendungen.yaml`). Der Export beantwortet nur die Frage, *ob ein einzelner
Code* an diesen Stellen tatsächlich vorkommt. Gebraucht wird er nur für Codes, die schon
vor der Migration entfernt werden sollen, obwohl ihre Tabelle in gebuchten Daten verwendet
wird. Ohne Export werden solche Codes gesperrt statt entfernt.

Die Zählung lässt sich gezielt aufbauen: je Verwendungsort aus `context/verwendungen.yaml`
ein `COUNT … GROUP BY <feld>` auf die genannte Tabelle.
