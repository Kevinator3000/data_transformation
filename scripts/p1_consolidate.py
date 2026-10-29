"""Phase 1 Abschluss – alle normalisierten Blätter je NAV-Tabelle zusammenführen.

Schreibt work/konsolidiert/<nav_tabelle>.csv mit einer Zeile je Code:
  status_gesamt = einheitlicher Status | 'konflikt' | 'unklar' | 'nicht_bewertet'

Liegt ein NAV-Export input/nav_exports/<nav_tabelle>.csv vor
(Spalten: code;beschreibung;anzahl_gebuchte_verwendungen;letzte_verwendung),
werden dessen Kennzahlen ergänzt und Codes, die in NAV existieren, aber von
keinem Fachbereich bewertet wurden, als 'nicht_bewertet' aufgenommen.
Codes, die bewertet wurden, aber im Export fehlen, bekommen den Hinweis
'nicht_in_nav_export'.

Aus context/verwendungen.yaml (Handbook) kommen die Spalten verwendet_in und
in_gebuchten_daten. Nach dem Ausfüllen dort einfach erneut ausführen.

Aufruf: python scripts/p1_consolidate.py
"""
from __future__ import annotations

from collections import Counter, defaultdict

import verwendungen
from common import KONSOL, MANIFEST, NAV_EXPORTS, NORMAL, append_log, iter_sheets, load_yaml, read_csv, slug, write_csv

FELDER = ["nav_tabelle", "code", "status_gesamt", "beschreibungen", "status_je_quelle",
          "uebergeordnete_codes", "fachbereiche", "hinweise", "verwendet_in", "in_gebuchten_daten", "nav_beschreibung",
          "nav_anzahl_gebucht", "nav_letzte_verwendung", "quellen"]


def main():
    manifest = load_yaml(MANIFEST, {"dateien": {}})
    tab: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    ohne_tabelle = []
    for _, b in iter_sheets(manifest):
        p = NORMAL / f"{b['blatt_id']}.csv"
        if b.get("leer") or not p.exists():
            continue
        if not b.get("nav_tabelle"):
            ohne_tabelle.append(b["blatt_id"])
            continue
        for r in read_csv(p):
            tab[b["nav_tabelle"]][r["code"]].append(r)
    if ohne_tabelle:
        raise SystemExit(f"nav_tabelle fehlt im Manifest für: {', '.join(ohne_tabelle)}")

    KONSOL.mkdir(parents=True, exist_ok=True)
    for nav, codes in tab.items():
        export = {}
        ep = NAV_EXPORTS / f"{slug(nav)}.csv"
        if ep.exists():
            export = {r["code"].strip().upper(): r for r in read_csv(ep)}
        vw = verwendungen.info(nav)
        rows = []
        for code in sorted(set(codes) | set(export)):
            rs = codes.get(code, [])
            stati = {r["status"] for r in rs}
            klare = stati - {"unklar"}
            if not rs:
                gesamt = "nicht_bewertet"
            elif len(klare) > 1:
                gesamt = "konflikt"
            elif klare:
                gesamt = klare.pop()
            else:
                gesamt = "unklar"
            hinweise = sorted({h for r in rs for h in r["hinweise"].split(", ") if h})
            if gesamt not in ("unklar", "konflikt") and "unklar" in stati:
                hinweise.append("teilweise_unklar")
            if export and rs and code not in export:
                hinweise.append("nicht_in_nav_export")
            e = export.get(code, {})
            rows.append({
                "nav_tabelle": nav, "code": code, "status_gesamt": gesamt,
                "beschreibungen": " | ".join(sorted({r["beschreibung"] for r in rs if r["beschreibung"]})),
                "status_je_quelle": " | ".join(f"{r['datensatz_id']}={r['status']}" for r in rs),
                "uebergeordnete_codes": ", ".join(sorted({r["uebergeordneter_code"] for r in rs if r["uebergeordneter_code"]})),
                "fachbereiche": ", ".join(sorted({r["fachbereich"] for r in rs if r["fachbereich"]})),
                "hinweise": ", ".join(hinweise),
                **vw,
                "nav_beschreibung": e.get("beschreibung", ""),
                "nav_anzahl_gebucht": e.get("anzahl_gebuchte_verwendungen", ""),
                "nav_letzte_verwendung": e.get("letzte_verwendung", ""),
                "quellen": " | ".join(r["quelle"] for r in rs) or ("NAV-Export" if e else ""),
            })
        write_csv(KONSOL / f"{slug(nav)}.csv", rows, FELDER)
        c = Counter(r["status_gesamt"] for r in rows)
        print(f"{nav}: {len(rows)} Codes {dict(c)}  NAV-Export: {'ja' if export else 'fehlt'}  "
              f"in gebuchten Daten: {vw['in_gebuchten_daten']}")
    append_log(f"[skript] p1_consolidate: {len(tab)} NAV-Tabellen")
    import queue_cli
    queue_cli.sync()


if __name__ == "__main__":
    main()
