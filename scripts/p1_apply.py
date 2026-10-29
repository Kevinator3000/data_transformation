"""Phase 1 – Profil auf Blatt anwenden (deterministisch).

Liest work/extrakt/<blatt_id>.jsonl und profile/<profil>.yaml und schreibt
  work/normalisiert/<blatt_id>.csv          ein Datensatz je Code-Vorkommen
  work/normalisiert/<blatt_id>.bericht.json Statistik, Hinweise, nicht zugeordnete
                                            Notizen und NICHT ABGEDECKTE ZELLEN

Abdeckungsregel: Jede belegte Zelle muss vom Profil verbraucht werden
(Code, Beschreibung, Bewertung, Nutzung, Notiz, Kopfzeile) oder explizit mit
Grund unter `ignorieren` stehen. Sonst ist das Blatt nicht fertig.

Aufruf:
  python scripts/p1_apply.py <blatt_id> [...]
  python scripts/p1_apply.py --profil <profil_id>
  python scripts/p1_apply.py --alle
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from openpyxl.utils import column_index_from_string as ci
from openpyxl.utils import get_column_letter as cl

from common import (EXTRAKT, MANIFEST, NORMAL, PROFILE, STATUS, iter_sheets, load_yaml,
                    norm, now, sha256_file, write_csv, write_text)

FELDER = ["datensatz_id", "blatt_id", "quelle", "zeile", "nav_tabelle", "fachbereich",
          "code", "code_roh", "beschreibung", "uebergeordneter_code", "bewertung_original",
          "nutzung", "farbe", "status", "status_quelle", "notizen", "hinweise"]

JA = {"ja", "x", "yes", "1", "j", "wahr"}
NEIN = {"nein", "no", "0", "n", "falsch", "-"}
FILTERZEICHEN = re.compile(r"[&|()<>=*@?'\"]|\.\.")


def _regel_treffer(wert: str, regeln: list[dict]):
    n = norm(wert)
    for r in regeln:
        if "wert" in r and n == norm(r["wert"]):
            return r
        if "regex" in r and re.search(r["regex"], wert, re.I):
            return r
        if "enthaelt" in r and norm(r["enthaelt"]) in n:
            return r
    return None


def code_hinweise(cell: dict, code: str) -> list[str]:
    h = []
    roh = cell["wert"]
    if cell["typ"] == "zahl":
        h.append("code_als_zahl_in_excel")  # führende Nullen evtl. verloren
    if roh != roh.strip():
        h.append("code_leerzeichen_rand")
    if " " in code:
        h.append("code_mit_leerzeichen")
    if len(code) > 20:
        h.append("code_laenger_20")
    if FILTERZEICHEN.search(code):
        h.append("code_mit_filterzeichen")
    if cell.get("durchgestrichen"):
        h.append("durchgestrichen")
    if cell.get("versteckt"):
        h.append("versteckt")
    return h


class Ergebnis:
    def __init__(self, blatt, datei, profil):
        self.blatt, self.datei, self.profil = blatt, datei, profil
        self.verbraucht: set[str] = set()
        self.records: list[dict] = []
        self.notizen_offen: list[dict] = []

    def rec(self, code_cell, **kw) -> dict:
        code = code_cell["wert"].strip().upper()
        r = {f: "" for f in FELDER}
        r.update(
            datensatz_id=f"{self.blatt['blatt_id']}:{code_cell['zelle']}",
            blatt_id=self.blatt["blatt_id"],
            quelle=f"{self.datei['pfade'][0]} / {self.blatt['name']} / {code_cell['zelle']}",
            zeile=code_cell["zeile"],
            nav_tabelle=self.blatt.get("nav_tabelle") or self.profil.get("nav_tabelle") or "",
            fachbereich=self.blatt.get("fachbereich") or self.datei.get("fachbereich") or "",
            code=code, code_roh=code_cell["wert"], farbe=code_cell.get("fuellung", ""),
        )
        r["_hinweise"] = code_hinweise(code_cell, code)
        r["_notizen"] = []
        if code_cell.get("kommentar"):
            r["_notizen"].append(f"Kommentar {code_cell['zelle']}: {code_cell['kommentar']}")
        r.update(kw)
        self.records.append(r)
        return r


def status_aus_farbe(profil, farbe):
    regel = (profil.get("farben") or {}).get(farbe) if farbe else None
    return regel


def apply_liste(e: Ergebnis, grid: dict, maxrow: int):
    p = e.profil
    sp = p["spalten"]
    kz = p.get("kopfzeile", 1)
    von = p.get("datenzeilen", {}).get("von", kz + 1)
    bis = p.get("datenzeilen", {}).get("bis") or maxrow
    code_col = sp["code"]
    besch_col = sp.get("beschreibung")
    bew_cols = sp.get("bewertung", []) or []
    nutz = sp.get("nutzung", {}) or {}
    genutzt = [code_col] + ([besch_col] if besch_col else []) + bew_cols + list(nutz)

    for s in genutzt:
        if (kz, s) in grid:
            e.verbraucht.add(grid[(kz, s)]["zelle"])

    for r in range(von, bis + 1):
        cc = grid.get((r, code_col))
        if not cc:
            continue
        e.verbraucht.add(cc["zelle"])
        rec = e.rec(cc)
        if besch_col:
            bc = grid.get((r, besch_col))
            if bc:
                e.verbraucht.add(bc["zelle"])
                rec["beschreibung"] = bc["wert"].strip()
                if bc.get("kommentar"):
                    rec["_notizen"].append(f"Kommentar {bc['zelle']}: {bc['kommentar']}")
            if not rec["beschreibung"]:
                rec["_hinweise"].append("leere_beschreibung")

        # Bewertung → Status
        bew_werte, stati, annahmen = [], set(), []
        for s in bew_cols:
            c = grid.get((r, s))
            if not c:
                continue
            e.verbraucht.add(c["zelle"])
            bew_werte.append(c["wert"].strip())
            if c.get("kommentar"):
                rec["_notizen"].append(f"Kommentar {c['zelle']}: {c['kommentar']}")
            regel = _regel_treffer(c["wert"], p.get("status_regeln", []))
            if regel:
                stati.add(regel["status"])
                if regel.get("annahme"):
                    annahmen.append(regel["annahme"])
            else:
                rec["_hinweise"].append(f"bewertung_unbekannt:{c['zelle']}")
        rec["bewertung_original"] = " | ".join(bew_werte)
        if len(stati) == 1:
            rec["status"] = stati.pop()
            rec["status_quelle"] = "regel_mit_annahme" if annahmen else "explizit"
        elif len(stati) > 1:
            rec["status"], rec["status_quelle"] = "unklar", "widerspruechliche_bewertung"
            rec["_hinweise"].append("widerspruechliche_bewertung")
        elif not bew_werte:
            rec["_hinweise"].append("keine_bewertung")

        # Farbe als Bestätigung bzw. als Quelle, wenn keine Bewertung da ist
        fr = status_aus_farbe(p, rec["farbe"])
        if fr and fr.get("status"):
            if not rec["status"]:
                rec["status"] = fr["status"]
                rec["status_quelle"] = f"farbe_{fr.get('sicherheit', 'abgeleitet')}"
            elif rec["status"] != fr["status"] and rec["status"] != "unklar":
                rec["_hinweise"].append("farbe_widerspricht_bewertung")

        # Nutzung je Bereich
        if nutz:
            teile, ja, nein = [], 0, 0
            for s, label in nutz.items():
                c = grid.get((r, s))
                if not c:
                    continue
                e.verbraucht.add(c["zelle"])
                teile.append(f"{label}={c['wert'].strip()}")
                ja += norm(c["wert"]) in JA
                nein += norm(c["wert"]) in NEIN
            rec["nutzung"] = "; ".join(teile)
            if rec["status"] == "behalten" and teile and ja == 0:
                rec["_hinweise"].append("behalten_ohne_nutzung")
            if rec["status"] == "verwerfen" and ja > 0:
                rec["_hinweise"].append("verwerfen_trotz_nutzung")

    zaehl = Counter(x["code"] for x in e.records)
    for x in e.records:
        if zaehl[x["code"]] > 1:
            x["_hinweise"].append("doppelt_im_blatt")


def apply_matrix(e: Ergebnis, grid: dict, maxrow: int):
    p = e.profil
    kz = p.get("kopfzeile", 1)
    von = ci(p["spalten_bereich"]["von"])
    bis = ci(p["spalten_bereich"]["bis"])
    for col in range(von, bis + 1):
        s = cl(col)
        parent = grid.get((kz, s))
        if not parent:
            continue
        e.verbraucht.add(parent["zelle"])
        pcode = parent["wert"].strip().upper()
        gesehen = Counter()
        for r in range(kz + 1, maxrow + 1):
            c = grid.get((r, s))
            if not c or c["typ"] == "leer":
                continue
            e.verbraucht.add(c["zelle"])
            rec = e.rec(c, uebergeordneter_code=pcode)
            gesehen[rec["code"]] += 1
            fr = status_aus_farbe(p, rec["farbe"])
            if fr and fr.get("status"):
                rec["status"] = fr["status"]
                rec["status_quelle"] = f"farbe_{fr.get('sicherheit', 'abgeleitet')}"
            elif rec["farbe"]:
                rec["_hinweise"].append("farbe_ohne_bedeutung")
        for x in e.records:
            if x["uebergeordneter_code"] == pcode and gesehen[x["code"]] > 1:
                x["_hinweise"].append("doppelt_unter_selbem_obercode")


def apply_notizen(e: Ergebnis, grid: dict):
    p = e.profil
    spalten = p.get("lose_notizen", []) or []
    manuell = p.get("notiz_zuordnung", {}) or {}
    codes = {}
    for x in e.records:
        codes.setdefault(norm(x["code"]), x)
    for (r, s), c in sorted(grid.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if s not in spalten or c["typ"] == "leer":
            continue
        e.verbraucht.add(c["zelle"])
        text = c["wert"].strip()
        ziel, art = None, None
        if c["zelle"] in manuell:
            m = manuell[c["zelle"]]
            ziel = codes.get(norm(m["code"]))
            art = f"manuell zugeordnet ({m.get('begruendung', 'ohne Begründung')})"
        else:
            token = re.split(r"\s+[–\-:]\s+|\s+", text, maxsplit=1)[0]
            ziel = codes.get(norm(token))
            art = "über Code am Textanfang"
        if not ziel:
            e.notizen_offen.append({"zelle": c["zelle"], "text": text})
            continue
        ziel["_notizen"].append(f"Notiz {c['zelle']} ({art}): {text}")
        if c["zelle"] in manuell:
            ziel["_hinweise"].append("notiz_manuell_zugeordnet")
        regel = _regel_treffer(text, p.get("notiz_regeln", []))
        if regel:
            if regel.get("hinweis"):
                ziel["_hinweise"].append(regel["hinweis"])
            st = regel.get("status")
            if st:
                if not ziel["status"] or ziel["status"] == "unklar":
                    ziel["status"], ziel["status_quelle"] = st, "notiz"
                elif ziel["status"] != st:
                    ziel["_hinweise"].append("notiz_widerspricht_status")


def apply_blatt(manifest, blatt_id: str) -> dict:
    datei = blatt = None
    for f, b in iter_sheets(manifest):
        if b["blatt_id"] == blatt_id:
            datei, blatt = f, b
    if not blatt:
        raise SystemExit(f"{blatt_id}: nicht im Manifest oder Duplikat.")
    pfad = PROFILE / f"{blatt['profil']}.yaml"
    if not pfad.exists():
        raise SystemExit(f"{blatt_id}: Profil {pfad.name} fehlt.")
    profil = load_yaml(pfad, {})
    cells = [json.loads(line) for line in open(EXTRAKT / f"{blatt_id}.jsonl", encoding="utf-8")]
    grid = {(c["zeile"], c["spalte"]): c for c in cells}
    maxrow = max((c["zeile"] for c in cells), default=0)

    e = Ergebnis(blatt, datei, profil)
    typ = profil.get("typ")
    if typ == "liste":
        apply_liste(e, grid, maxrow)
    elif typ == "matrix":
        apply_matrix(e, grid, maxrow)
    else:
        raise SystemExit(f"Profil {pfad.name}: unbekannter typ '{typ}'")
    apply_notizen(e, grid)

    ign = {}
    for i in profil.get("ignorieren", []) or []:
        for z in _zellen_aus(i["zellen"], grid):
            ign[z] = i.get("grund", "")
    e.verbraucht |= set(ign)

    nicht = [{"zelle": c["zelle"], "wert": c["wert"]} for c in cells
             if c["typ"] != "leer" and c["zelle"] not in e.verbraucht]

    for x in e.records:
        if not x["status"]:
            x["status"], x["status_quelle"] = "unklar", x["status_quelle"] or "keine_aussage"
        assert x["status"] in STATUS, x["status"]
        x["hinweise"] = ", ".join(dict.fromkeys(x.pop("_hinweise")))
        x["notizen"] = " || ".join(x.pop("_notizen"))

    write_csv(NORMAL / f"{blatt_id}.csv", e.records, FELDER)
    bericht = {
        "blatt_id": blatt_id, "profil": blatt["profil"], "erzeugt": now(),
        "inhalt_hash": blatt["inhalt_hash"], "profil_hash": sha256_file(pfad)[:16],
        "datensaetze": len(e.records),
        "status": dict(Counter(x["status"] for x in e.records)),
        "status_quelle": dict(Counter(x["status_quelle"] for x in e.records)),
        "hinweise": dict(Counter(h for x in e.records for h in x["hinweise"].split(", ") if h)),
        "notizen_ohne_zuordnung": e.notizen_offen,
        "ignoriert": ign,
        "nicht_abgedeckt": nicht,
    }
    write_text(NORMAL / f"{blatt_id}.bericht.json", json.dumps(bericht, ensure_ascii=False, indent=1))
    return bericht


def _zellen_aus(spec, grid) -> list[str]:
    """'G1', 'F2:F20', 'Spalte:H', 'Zeile:1'"""
    out = []
    for s in ([spec] if isinstance(spec, str) else spec):
        if s.startswith("Spalte:"):
            out += [c["zelle"] for (r, sp), c in grid.items() if sp == s[7:]]
        elif s.startswith("Zeile:"):
            out += [c["zelle"] for (r, sp), c in grid.items() if r == int(s[6:])]
        elif ":" in s:
            a, b = s.split(":")
            ma, mb = re.match(r"([A-Z]+)(\d+)", a), re.match(r"([A-Z]+)(\d+)", b)
            for col in range(ci(ma[1]), ci(mb[1]) + 1):
                for r in range(int(ma[2]), int(mb[2]) + 1):
                    if (r, cl(col)) in grid:
                        out.append(grid[(r, cl(col))]["zelle"])
        else:
            out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("blatt_ids", nargs="*")
    ap.add_argument("--profil")
    ap.add_argument("--alle", action="store_true")
    a = ap.parse_args()
    manifest = load_yaml(MANIFEST, {"dateien": {}})
    ids = list(a.blatt_ids)
    if a.profil or a.alle:
        ids += [b["blatt_id"] for _, b in iter_sheets(manifest)
                if not b.get("leer") and (a.alle or b["profil"] == a.profil)
                and (PROFILE / f"{b['profil']}.yaml").exists()]
    if not ids:
        raise SystemExit("Keine Blätter angegeben.")
    for bid in ids:
        b = apply_blatt(manifest, bid)
        flag = "OK" if not b["nicht_abgedeckt"] else f"{len(b['nicht_abgedeckt'])} NICHT ABGEDECKT"
        print(f"{bid}: {b['datensaetze']} Datensätze, Status {b['status']}, "
              f"offene Notizen {len(b['notizen_ohne_zuordnung'])}, {flag}")


if __name__ == "__main__":
    main()
