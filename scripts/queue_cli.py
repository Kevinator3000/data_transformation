"""Arbeitswarteschlange – die einzige Stelle, an der Fortschritt steht.

  python scripts/queue_cli.py status              Überblick + nächste Einheit
  python scripts/queue_cli.py next                nächste startbare Einheit
  python scripts/queue_cli.py show  <ID>          Details einer Einheit
  python scripts/queue_cli.py start <ID> --agent claude|codex
  python scripts/queue_cli.py submit <ID> -m "…"  fertig, wartet auf Review (Vier-Augen)
  python scripts/queue_cli.py done  <ID> -m "…"   abgeschlossen (bzw. Review bestanden)
  python scripts/queue_cli.py block <ID> -m "…"   blockiert (Grund angeben!)
  python scripts/queue_cli.py reopen <ID> -m "…"  zurück auf todo
  python scripts/queue_cli.py sync                Einheiten aus Manifest/Zwischenständen ableiten

Jede Statusänderung schreibt automatisch eine Zeile ins state/session_log.md.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict

from common import (FRAGEN, KONSOL, MANIFEST, QUEUE, append_log, iter_sheets,
                    load_yaml, now, save_yaml)

STATI = ["todo", "in_progress", "review", "done", "blocked"]

ANLEITUNG = {
    "P1-PROFIL": "AGENTS.md → 'P1-PROFIL': Vorschau(en) lesen, profile/<id>.yaml schreiben, anwenden, validieren.",
    "P1-PRUEFUNG": "AGENTS.md → 'P1-PRUEFUNG': Bericht + Hinweise prüfen, NAV-Tabelle/Fachbereich im Manifest setzen, offene Fragen erfassen.",
    "P1-KONSOLIDIERUNG": "AGENTS.md → 'P1-KONSOLIDIERUNG': p1_consolidate.py ausführen, Konflikte je NAV-Tabelle prüfen.",
    "P1-VERWENDUNGEN": "AGENTS.md → 'P1-VERWENDUNGEN': Verwendungsorte je Code-Tabelle aus dem Handbook nach context/verwendungen.yaml übertragen.",
    "P2-EINORDNUNG": "AGENTS.md → 'P2-EINORDNUNG': je Code Aktion + Zeitpunkt nach Handbook und Migrationsgrundsätzen festlegen.",
    "P3-CROSSWALK": "AGENTS.md → 'P3-CROSSWALK': p3_build_crosswalk.py ausführen, Lücken schließen.",
    "P3-KONZEPT": "AGENTS.md → 'P3-KONZEPT': output/konzept.md aus Crosswalk und Einordnung schreiben.",
}


def typ_von(uid: str) -> str:
    for k in ANLEITUNG:
        if uid == k or uid.startswith(k + "-"):
            return k
    return uid


def load() -> dict:
    q = load_yaml(QUEUE, {"einheiten": []})
    q.setdefault("einheiten", [])
    return q


def save(q: dict) -> None:
    q["stand"] = now()
    save_yaml(QUEUE, q)


def _ensure(q: dict, idx: dict, uid: str, titel: str, deps: list[str], ziele=None, stand=None) -> dict:
    u = idx.get(uid)
    if u is None:
        u = {"id": uid, "titel": titel, "status": "todo", "abhaengig_von": deps}
        if ziele:
            u["ziele"] = ziele
        if stand:
            u["stand"] = stand
        q["einheiten"].append(u)
        idx[uid] = u
        return u
    u["titel"] = titel
    u["abhaengig_von"] = deps
    if ziele is not None:
        u["ziele"] = ziele
    # Quelle hat sich geändert, nachdem die Einheit abgeschlossen wurde → wieder öffnen
    if stand and u.get("stand") and u["stand"] != stand and u["status"] in ("done", "review"):
        u["status"] = "todo"
        u["wiedereroeffnet"] = f"{now()} Quelle geändert"
        append_log(f"[sync] {uid} wieder geöffnet – Quelldaten geändert")
    if stand:
        u["stand"] = stand
    return u


def sync(verbose: bool = False) -> dict:
    q = load()
    idx = {u["id"]: u for u in q["einheiten"]}
    manifest = load_yaml(MANIFEST, {"dateien": {}})

    gruppen: dict[str, list] = defaultdict(list)
    for f, b in iter_sheets(manifest):
        if b.get("leer"):
            continue
        gruppen[b["profil"]].append(b)

    pruef_ids = []
    for prof, blaetter in sorted(gruppen.items()):
        pid = f"P1-PROFIL-{prof}"
        _ensure(q, idx, pid, f"Profil '{prof}' für {len(blaetter)} Blatt/Blätter schreiben "
                f"(z. B. {blaetter[0]['name']})", [], ziele=[b["blatt_id"] for b in blaetter])
        for b in blaetter:
            uid = f"P1-PRUEFUNG-{b['blatt_id']}"
            _ensure(q, idx, uid, f"Ergebnis prüfen: Blatt '{b['name']}'", [pid],
                    ziele=[b["blatt_id"]], stand=b["inhalt_hash"])
            pruef_ids.append(uid)

    if pruef_ids:
        _ensure(q, idx, "P1-KONSOLIDIERUNG", "Alle Blätter je NAV-Tabelle zusammenführen, Konflikte prüfen", pruef_ids)

    if pruef_ids:
        _ensure(q, idx, "P1-VERWENDUNGEN", "Verwendungsorte je Code-Tabelle aus dem Handbook erfassen",
                ["P1-KONSOLIDIERUNG"])

    einord = []
    if KONSOL.exists():
        for p in sorted(KONSOL.glob("*.csv")):
            uid = f"P2-EINORDNUNG-{p.stem}"
            _ensure(q, idx, uid, f"Aktion und Zeitpunkt je Code festlegen: {p.stem}", ["P1-KONSOLIDIERUNG", "P1-VERWENDUNGEN"], ziele=[p.name])
            einord.append(uid)
    if einord:
        _ensure(q, idx, "P3-CROSSWALK", "Crosswalk alt→neu erzeugen und Lücken schließen", einord)
        _ensure(q, idx, "P3-KONZEPT", "Migrationskonzept schreiben", ["P3-CROSSWALK"])

    # Einheiten, deren Ziel nicht mehr existiert, nicht löschen, sondern markieren
    gueltig = set(pruef_ids) | {f"P1-PROFIL-{p}" for p in gruppen} | set(einord) | \
        {"P1-KONSOLIDIERUNG", "P1-VERWENDUNGEN", "P3-CROSSWALK", "P3-KONZEPT"}
    for u in q["einheiten"]:
        if u["id"] not in gueltig and u["status"] != "done":
            u["status"] = "blocked"
            u["ergebnis"] = "verwaist – Ziel nicht mehr im Manifest"

    save(q)
    if verbose:
        print(f"Queue synchronisiert: {len(q['einheiten'])} Einheiten.")
    return q


def startbar(q: dict) -> list[dict]:
    st = {u["id"]: u["status"] for u in q["einheiten"]}
    return [u for u in q["einheiten"] if u["status"] == "todo"
            and all(st.get(d) == "done" for d in u.get("abhaengig_von", []))]


def _get(q: dict, uid: str) -> dict:
    for u in q["einheiten"]:
        if u["id"] == uid:
            return u
    sys.exit(f"Einheit {uid} nicht gefunden.")


def _print_unit(u: dict) -> None:
    print(f"{u['id']}  [{u['status']}]  {u['titel']}")
    if u.get("ziele"):
        print(f"  Ziele: {', '.join(u['ziele'][:10])}{' …' if len(u['ziele']) > 10 else ''}")
    if typ_von(u["id"]) in ("P1-PROFIL", "P1-PRUEFUNG"):
        for bid in u.get("ziele", [])[:5]:
            print(f"  Vorschau: work/extrakt/{bid}.vorschau.md")
    if u.get("agent"):
        print(f"  Agent: {u['agent']}  gestartet: {u.get('gestartet')}")
    if u.get("ergebnis"):
        print(f"  Ergebnis: {u['ergebnis']}")
    print(f"  Anleitung: {ANLEITUNG.get(typ_von(u['id']), '-')}")


def cmd_status(q: dict) -> None:
    c = Counter(u["status"] for u in q["einheiten"])
    print("Fortschritt: " + "  ".join(f"{s}={c.get(s, 0)}" for s in STATI))
    per_typ = defaultdict(Counter)
    for u in q["einheiten"]:
        per_typ[typ_von(u["id"])][u["status"]] += 1
    for t, cc in per_typ.items():
        print(f"  {t:<18} " + "  ".join(f"{s}={cc[s]}" for s in STATI if cc[s]))
    fragen = load_yaml(FRAGEN, {"fragen": []})["fragen"]
    offen = [f for f in fragen if f.get("status") == "offen"]
    print(f"Offene Fragen: {len(offen)} von {len(fragen)}")
    laufend = [u for u in q["einheiten"] if u["status"] == "in_progress"]
    if laufend:
        print("\n!! Unterbrochene Einheiten (in_progress) – zuerst neu bearbeiten:")
        for u in laufend:
            _print_unit(u)
    rev = [u for u in q["einheiten"] if u["status"] == "review"]
    if rev:
        print(f"\nWarten auf Review: {', '.join(u['id'] for u in rev[:10])}")
    nxt = startbar(q)
    print("\nNächste startbare Einheit:")
    _print_unit(nxt[0]) if nxt else print("  keine")


def _gate(u: dict) -> None:
    """Phase-1-Einheiten dürfen nur abgeschlossen werden, wenn die Validierung grün ist."""
    import p1_validate
    from common import find_sheet
    manifest = load_yaml(MANIFEST, {"dateien": {}})
    fragen = load_yaml(FRAGEN, {"fragen": []})["fragen"]
    bezuege = {z for f in fragen for z in (f.get("bezug") or [])}
    probleme = []
    for bid in u.get("ziele", []):
        _, b = find_sheet(manifest, bid)
        fehler, _ = p1_validate.pruefe(b, bezuege)
        probleme += [f"{bid}: {x}" for x in fehler]
    if probleme:
        sys.exit("Abschluss verweigert – Validierung schlägt fehl:\n  " + "\n  ".join(probleme))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "next", "show", "start", "submit", "done", "block", "reopen", "sync"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("-m", "--msg", default="")
    ap.add_argument("--agent", default="unbekannt")
    a = ap.parse_args()

    if a.cmd == "sync":
        sync(verbose=True)
        return
    q = load()
    if a.cmd == "status":
        cmd_status(q)
        return
    if a.cmd == "next":
        nxt = startbar(q)
        _print_unit(nxt[0]) if nxt else print("Keine startbare Einheit.")
        return
    if not a.id:
        sys.exit("ID fehlt.")
    u = _get(q, a.id)
    if a.cmd == "show":
        _print_unit(u)
        return
    if a.cmd == "start":
        offen = [d for d in u.get("abhaengig_von", []) if _get(q, d)["status"] != "done"]
        if offen:
            sys.exit(f"Abhängigkeiten nicht erledigt: {offen}")
        if u["status"] == "in_progress":
            print(f"Hinweis: war bereits in_progress ({u.get('agent')}) – wird neu begonnen.")
        u.update(status="in_progress", agent=a.agent, gestartet=now())
    elif a.cmd in ("submit", "done", "block", "reopen"):
        if a.cmd in ("submit", "done", "block") and not a.msg:
            sys.exit("Bitte mit -m kurz festhalten, was getan wurde bzw. warum blockiert.")
        if a.cmd in ("submit", "done") and typ_von(a.id) in ("P1-PROFIL", "P1-PRUEFUNG"):
            _gate(u)
        if a.cmd in ("submit", "done") and a.id == "P1-VERWENDUNGEN":
            import verwendungen
            f = verwendungen.check()
            if f:
                sys.exit("Abschluss verweigert:\n  " + "\n  ".join(f))
        neu = {"submit": "review", "done": "done", "block": "blocked", "reopen": "todo"}[a.cmd]
        if a.cmd == "done" and u["status"] == "review":
            u["reviewer"] = a.agent
        u["status"] = neu
        u["ergebnis"] = a.msg
        u["beendet" if neu in ("done", "review") else "geaendert"] = now()
    save(q)
    append_log(f"[{a.agent}] {a.cmd} {a.id}: {a.msg}".rstrip(": "))
    print(f"{a.id} → {u['status']}")


if __name__ == "__main__":
    main()
