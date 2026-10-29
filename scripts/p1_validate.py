"""Prüft Phase-1-Ergebnisse. Exit-Code 1 bei Fehlern.

  python scripts/p1_validate.py [<blatt_id> ...]    (ohne Argument: alle)

Fehler (blockieren `done`):
  * Profil fehlt / Ergebnis fehlt / Ergebnis älter als Profil oder Quelle
  * nicht abgedeckte Zellen
  * unbekannter Status
  * nicht zugeordnete Notizen, für die keine offene Frage existiert
  * Datensätze mit Status 'unklar' ohne offene Frage (Bezug: Datensatz oder ganzes Blatt)
Warnungen:
  * NAV-Tabelle im Manifest nicht gesetzt
"""
from __future__ import annotations

import json
import sys

from common import (FRAGEN, MANIFEST, NORMAL, PROFILE, QUEUE, STATUS, iter_sheets,
                    load_yaml, read_csv, sha256_file)


def pruefe(blatt, fragen_bezuege: set[str]) -> tuple[list[str], list[str]]:
    bid = blatt["blatt_id"]
    fehler, warn = [], []
    prof = PROFILE / f"{blatt['profil']}.yaml"
    csv_p, ber_p = NORMAL / f"{bid}.csv", NORMAL / f"{bid}.bericht.json"
    if not prof.exists():
        return [f"Profil {prof.name} fehlt"], warn
    if not csv_p.exists() or not ber_p.exists():
        return ["Ergebnis fehlt – p1_apply.py ausführen"], warn
    ber = json.loads(ber_p.read_text(encoding="utf-8"))
    if ber.get("inhalt_hash") != blatt["inhalt_hash"]:
        fehler.append("Quelle hat sich seit der Anwendung geändert – neu anwenden")
    if ber.get("profil_hash") != sha256_file(prof)[:16]:
        fehler.append("Profil wurde nach der Anwendung geändert – neu anwenden")
    if ber["nicht_abgedeckt"]:
        z = ", ".join(f"{x['zelle']}={x['wert'][:20]!r}" for x in ber["nicht_abgedeckt"][:8])
        fehler.append(f"{len(ber['nicht_abgedeckt'])} Zellen nicht abgedeckt: {z}")
    for n in ber["notizen_ohne_zuordnung"]:
        if f"{bid}:{n['zelle']}" not in fragen_bezuege:
            fehler.append(f"Notiz {n['zelle']} ohne Zuordnung und ohne offene Frage: {n['text'][:40]!r}")
    rows = read_csv(csv_p)
    for r in rows:
        if r["status"] not in STATUS:
            fehler.append(f"{r['datensatz_id']}: unbekannter Status {r['status']!r}")
    if not blatt.get("nav_tabelle"):
        warn.append("nav_tabelle im Manifest nicht gesetzt")
    unklar = [r["datensatz_id"] for r in rows if r["status"] == "unklar"
              and r["datensatz_id"] not in fragen_bezuege and bid not in fragen_bezuege]
    if unklar:
        fehler.append(f"{len(unklar)} Datensätze 'unklar' ohne Frage (z. B. {unklar[0]})")
    return fehler, warn


def main():
    manifest = load_yaml(MANIFEST, {"dateien": {}})
    fragen = load_yaml(FRAGEN, {"fragen": []})["fragen"]
    bezuege = {z for f in fragen for z in (f.get("bezug") or [])}
    queue = {u["id"]: u for u in load_yaml(QUEUE, {"einheiten": []})["einheiten"]}
    ziel = set(sys.argv[1:])
    gesamt_fehler = 0
    for _, b in iter_sheets(manifest):
        if b.get("leer") or (ziel and b["blatt_id"] not in ziel):
            continue
        uid = f"P1-PRUEFUNG-{b['blatt_id']}"
        if not ziel and queue.get(uid, {}).get("status") not in ("done", "review", "in_progress") \
                and not (NORMAL / f"{b['blatt_id']}.csv").exists():
            continue  # noch nicht bearbeitet – kein Fehler
        fehler, warn = pruefe(b, bezuege)
        status = "FEHLER" if fehler else ("WARNUNG" if warn else "OK")
        print(f"{b['blatt_id']} ({b['name']}): {status}")
        for x in fehler:
            print(f"   ✗ {x}")
        for x in warn:
            print(f"   ! {x}")
        if fehler and queue.get(uid, {}).get("status") == "done":
            print(f"   ✗ {uid} steht auf done, ist aber fehlerhaft")
        gesamt_fehler += bool(fehler)
    sys.exit(1 if gesamt_fehler else 0)


if __name__ == "__main__":
    main()
