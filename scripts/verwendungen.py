"""Verwendungsorte je Code-Tabelle laut Data Quality Handbook.

Der Agent überträgt in Einheit P1-VERWENDUNGEN aus dem Handbook nach
context/verwendungen.yaml, in welchen Tabellen/Feldern jede Code-Tabelle verwendet
wird und ob das gebuchte Daten sind. Daraus leiten Konsolidierung und Crosswalk ab,
ob ein Code vor der Migration in NAV geändert werden darf.

  python scripts/verwendungen.py check     Vollständigkeit/Format prüfen (Exit 1 bei Fehlern)
"""
from __future__ import annotations

import sys

from common import KONSOL, MANIFEST, ROOT, iter_sheets, load_yaml, read_csv

VERWENDUNGEN = ROOT / "context" / "verwendungen.yaml"
HANDBOOK = ROOT / "context" / "data_quality_handbook.md"
ARTEN = ["einrichtung", "stammdaten", "beleg_offen", "gebucht", "archiv"]


def handbook_vorhanden() -> bool:
    return HANDBOOK.exists() and "**Platzhalter.**" not in HANDBOOK.read_text(encoding="utf-8")


def laden() -> dict:
    return (load_yaml(VERWENDUNGEN, {}) or {}).get("tabellen", {}) or {}


def info(nav_tabelle: str) -> dict:
    """{'verwendet_in': 'Tab.Feld (art), …', 'in_gebuchten_daten': ja|nein|unbekannt}"""
    t = laden().get(nav_tabelle)
    if not t:
        return {"verwendet_in": "", "in_gebuchten_daten": "unbekannt"}
    orte = t.get("verwendet_in") or []
    return {
        "verwendet_in": ", ".join(f"{o.get('tabelle')}.{o.get('feld')} ({o.get('art')})" for o in orte),
        "in_gebuchten_daten": "ja" if any(o.get("art") == "gebucht" for o in orte) else
                              ("nein" if orte and not t.get("unvollstaendig") else "unbekannt"),
    }


def check() -> list[str]:
    fehler = []
    if not handbook_vorhanden():
        return ["context/data_quality_handbook.md ist noch ein Platzhalter"]
    tabs = laden()
    benoetigt = {b["nav_tabelle"] for _, b in iter_sheets(load_yaml(MANIFEST, {"dateien": {}}))
                 if b.get("nav_tabelle")}
    if KONSOL.exists():
        for p in KONSOL.glob("*.csv"):
            benoetigt |= {r["nav_tabelle"] for r in read_csv(p)[:1]}
    for nav in sorted(benoetigt):
        t = tabs.get(nav)
        if t is None:
            fehler.append(f"{nav}: kein Eintrag (Tabellenname wie im Manifest verwenden)")
            continue
        if not t.get("handbook_bezug"):
            fehler.append(f"{nav}: handbook_bezug fehlt")
        if not t.get("verwendet_in") and not t.get("frage"):
            fehler.append(f"{nav}: keine Verwendungsorte und keine Frage-ID (frage: F-0xx)")
        for o in t.get("verwendet_in") or []:
            if o.get("art") not in ARTEN:
                fehler.append(f"{nav}: art {o.get('art')!r} ungültig ({', '.join(ARTEN)})")
            if not o.get("tabelle") or not o.get("feld"):
                fehler.append(f"{nav}: Verwendungsort ohne tabelle/feld")
    return fehler


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "check":
        sys.exit(__doc__)
    f = check()
    for x in f:
        print(f"  ✗ {x}")
    print("OK" if not f else f"{len(f)} Fehler")
    sys.exit(1 if f else 0)
