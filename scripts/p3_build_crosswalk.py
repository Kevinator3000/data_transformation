"""Phase 3 – Crosswalk alt → neu (das Dokument für die Wirtschaftsprüfung).

Liest work/konsolidiert/*.csv und work/einordnung/*.yaml und schreibt
output/crosswalk_alt_neu.csv. Meldet:
  * Codes ohne Entscheidung
  * Entscheidungen zu Codes, die es nicht gibt
  * ungültige Aktion / Zeitpunkt, fehlender Zielcode, fehlende Begründung
  * Zielcodes, auf die zusammengeführt wird, die selbst nicht behalten werden
  * Umbenennen/Zusammenführen vor der Migration bei Tabellen, die laut Handbook in
    gebuchten Daten verwendet werden (oder deren Verwendung unbekannt ist)
  * Entfernen vor der Migration ohne nachgewiesene 0 gebuchte Verwendungen

Aufruf: python scripts/p3_build_crosswalk.py   (Exit 1 bei Lücken/Fehlern)
"""
from __future__ import annotations

import sys

from common import AKTIONEN, EINORD, KONSOL, OUTPUT, ZEITPUNKTE, load_yaml, read_csv, write_csv

FELDER = ["nav_tabelle", "code_alt", "bedeutung_alt", "aktion", "code_neu", "zeitpunkt",
          "begruendung", "handbook_bezug", "bewertung_fachbereich", "in_gebuchten_daten", "nav_anzahl_gebucht",
          "freigabe_durch", "freigabe_datum", "quellen"]


def main():
    out, fehler = [], []
    for kp in sorted(KONSOL.glob("*.csv")):
        kons = {r["code"]: r for r in read_csv(kp)}
        ep = EINORD / f"{kp.stem}.yaml"
        if not ep.exists():
            fehler.append(f"{kp.stem}: work/einordnung/{kp.stem}.yaml fehlt")
            continue
        ein = load_yaml(ep, {})
        ents = {str(e["code"]).upper(): e for e in ein.get("entscheidungen", [])}
        behalten_neu = {e.get("code_neu") or c for c, e in ents.items()
                        if e.get("aktion") in ("behalten", "umbenennen")}
        for code, e in ents.items():
            if code not in kons:
                fehler.append(f"{kp.stem}/{code}: Entscheidung zu unbekanntem Code")
        for code, k in kons.items():
            e = ents.get(code)
            if not e:
                fehler.append(f"{kp.stem}/{code}: keine Entscheidung")
                continue
            if e.get("aktion") not in AKTIONEN:
                fehler.append(f"{kp.stem}/{code}: Aktion {e.get('aktion')!r} ungültig")
            if e.get("zeitpunkt") not in ZEITPUNKTE:
                fehler.append(f"{kp.stem}/{code}: Zeitpunkt {e.get('zeitpunkt')!r} ungültig")
            if not e.get("begruendung"):
                fehler.append(f"{kp.stem}/{code}: Begründung fehlt")
            if e.get("aktion") in ("umbenennen", "zusammenfuehren") and not e.get("code_neu"):
                fehler.append(f"{kp.stem}/{code}: code_neu fehlt")
            if e.get("aktion") == "zusammenfuehren" and e.get("code_neu") not in behalten_neu:
                fehler.append(f"{kp.stem}/{code}: Ziel {e.get('code_neu')} wird selbst nicht behalten")
            gebucht = k.get("in_gebuchten_daten", "unbekannt")
            if e.get("zeitpunkt") == "vor_migration" and e.get("aktion") in ("umbenennen", "zusammenfuehren") \
                    and gebucht != "nein":
                fehler.append(f"{kp.stem}/{code}: {e.get('aktion')} vor der Migration, obwohl die Tabelle "
                              f"in gebuchten Daten verwendet wird ({gebucht}) – nur per Mapping (zeitpunkt: migration)")
            if e.get("zeitpunkt") == "vor_migration" and e.get("aktion") == "nicht_migrieren" \
                    and gebucht != "nein" and k.get("nav_anzahl_gebucht") not in ("0",):
                fehler.append(f"{kp.stem}/{code}: Entfernen vor der Migration nur bei nachweislich 0 gebuchten "
                              f"Verwendungen (NAV-Export) – sonst sperren")
            bedeutung = k["beschreibungen"] or k["nav_beschreibung"]
            if not bedeutung and not e.get("bedeutung_alt"):
                fehler.append(f"{kp.stem}/{code}: Bedeutung des alten Codes nicht dokumentiert")
            fg = e.get("freigabe") or {}
            out.append({
                "nav_tabelle": k["nav_tabelle"], "code_alt": code,
                "bedeutung_alt": e.get("bedeutung_alt") or bedeutung,
                "aktion": e.get("aktion"),
                "code_neu": e.get("code_neu") or (code if e.get("aktion") == "behalten" else ""),
                "zeitpunkt": e.get("zeitpunkt"), "begruendung": e.get("begruendung"),
                "handbook_bezug": e.get("handbook_bezug", ""), "bewertung_fachbereich": k["status_gesamt"],
                "in_gebuchten_daten": gebucht,
                "nav_anzahl_gebucht": k["nav_anzahl_gebucht"],
                "freigabe_durch": fg.get("durch") or "", "freigabe_datum": fg.get("datum") or "",
                "quellen": k["quellen"],
            })
    write_csv(OUTPUT / "crosswalk_alt_neu.csv", out, FELDER)
    print(f"{len(out)} Zeilen → output/crosswalk_alt_neu.csv")
    for f in fehler:
        print(f"  ✗ {f}")
    ohne_freigabe = sum(1 for r in out if not r["freigabe_durch"])
    if ohne_freigabe:
        print(f"  ! {ohne_freigabe} Zeilen ohne Freigabe durch Fachbereich")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
