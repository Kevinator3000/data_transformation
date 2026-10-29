"""Offene Fragen an Fachbereiche – mit Herkunft der Antwort (Prüfpfad).

  python scripts/fragen.py neu --frage "…" --bezug <datensatz_id|blatt_id> [...] \
        --an "Fachbereich/Person" --einheit <QUEUE-ID> [--hypothese "…"]
     Bezug: Datensatz-ID '<blatt_id>:<zelle>' oder ganze Blatt-ID
  python scripts/fragen.py liste [--alle]
  python scripts/fragen.py antwort F-003 --von "Name, Rolle" "Antworttext"
  python scripts/fragen.py export          → output/offene_fragen.csv (für Excel/Mail)
"""
from __future__ import annotations

import argparse

from common import FRAGEN, OUTPUT, append_log, load_yaml, now, save_yaml, write_csv


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("neu")
    n.add_argument("--frage", required=True)
    n.add_argument("--bezug", nargs="+", required=True)
    n.add_argument("--an", default="")
    n.add_argument("--einheit", default="")
    n.add_argument("--hypothese", default="")
    l = sub.add_parser("liste")
    l.add_argument("--alle", action="store_true")
    a = sub.add_parser("antwort")
    a.add_argument("id")
    a.add_argument("text")
    a.add_argument("--von", required=True)
    sub.add_parser("export")
    args = ap.parse_args()

    data = load_yaml(FRAGEN, {"fragen": []})
    fr = data["fragen"]
    if args.cmd == "neu":
        nr = max([int(f["id"][2:]) for f in fr] or [0]) + 1
        f = {"id": f"F-{nr:03d}", "status": "offen", "erstellt": now(), "einheit": args.einheit,
             "an": args.an, "bezug": args.bezug, "frage": args.frage}
        if args.hypothese:
            f["hypothese"] = args.hypothese
        fr.append(f)
        save_yaml(FRAGEN, data)
        append_log(f"[frage] {f['id']} angelegt ({args.einheit}): {args.frage[:80]}")
        print(f["id"])
    elif args.cmd == "liste":
        for f in fr:
            if args.alle or f["status"] == "offen":
                print(f"{f['id']} [{f['status']}] an {f.get('an') or '?'}: {f['frage']}")
                print(f"    Bezug: {', '.join(f['bezug'][:6])}")
    elif args.cmd == "antwort":
        f = next((x for x in fr if x["id"] == args.id), None)
        if not f:
            raise SystemExit(f"{args.id} nicht gefunden")
        f.update(status="beantwortet", antwort=args.text, beantwortet_von=args.von, beantwortet_am=now())
        save_yaml(FRAGEN, data)
        append_log(f"[frage] {args.id} beantwortet von {args.von}")
    elif args.cmd == "export":
        rows = [{**f, "bezug": ", ".join(f["bezug"])} for f in fr]
        felder = ["id", "status", "an", "frage", "hypothese", "bezug", "antwort", "beantwortet_von", "beantwortet_am"]
        write_csv(OUTPUT / "offene_fragen.csv", rows, felder)
        print(f"{len(rows)} Fragen → output/offene_fragen.csv")


if __name__ == "__main__":
    main()
