"""Gemeinsame Pfade und Hilfsfunktionen für alle Skripte."""
from __future__ import annotations

import colorsys
import csv
import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "input" / "raw"
NAV_EXPORTS = ROOT / "input" / "nav_exports"
EXTRAKT = ROOT / "work" / "extrakt"
NORMAL = ROOT / "work" / "normalisiert"
KONSOL = ROOT / "work" / "konsolidiert"
EINORD = ROOT / "work" / "einordnung"
PROFILE = ROOT / "profile"
STATE = ROOT / "state"
OUTPUT = ROOT / "output"
MANIFEST = STATE / "manifest.yaml"
QUEUE = STATE / "queue.yaml"
LOG = STATE / "session_log.md"
FRAGEN = STATE / "offene_fragen.yaml"

# Kanonisches Status-Vokabular für Phase 1
STATUS = ["behalten", "umbenennen", "zusammenfuehren", "verwerfen", "unklar"]
# Aktionen und Zeitpunkte für Phase 2/3
AKTIONEN = ["behalten", "umbenennen", "zusammenfuehren", "sperren", "nicht_migrieren"]
ZEITPUNKTE = ["vor_migration", "migration", "nach_migration"]

CSV_DELIM = ";"  # Excel (DE) öffnet das direkt korrekt


# ---------------------------------------------------------------- YAML / IO
class _Dumper(yaml.SafeDumper):
    pass


def _str_repr(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str_repr)


def load_yaml(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return default if data is None else data


def save_yaml(path: Path, data) -> None:
    """Atomar schreiben: erst Temp-Datei, dann umbenennen. Ein Abbruch
    mittendrin hinterlässt nie eine halb geschriebene Datei."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(data, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=200)
    _atomic_write(path, text)


def _atomic_write(path: Path, text: str, encoding="utf-8") -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, text)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=CSV_DELIM, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=CSV_DELIM))


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(s: str) -> str:
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "x"


def norm(s) -> str:
    """Vergleichsform: getrimmt, kleingeschrieben, Mehrfach-Leerzeichen zusammengefasst."""
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


# ---------------------------------------------------------------- Farben
def theme_colors(wb) -> list[str] | None:
    """Liest die Theme-Farbpalette aus der Arbeitsmappe.
    Excel-Indexreihenfolge: lt1, dk1, lt2, dk2, accent1-6, hlink, folHlink
    (im XML stehen dk1/lt1 und dk2/lt2 vertauscht)."""
    xml = getattr(wb, "loaded_theme", None)
    if not xml:
        return None
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    scheme = root.find(".//a:clrScheme", ns)
    if scheme is None:
        return None
    vals = []
    for child in scheme:
        if len(child) == 0:
            vals.append("000000")
            continue
        el = child[0]
        vals.append(el.get("val") if el.tag.endswith("srgbClr") else (el.get("lastClr") or "000000"))
    if len(vals) >= 4:
        vals[0], vals[1] = vals[1], vals[0]
        vals[2], vals[3] = vals[3], vals[2]
    return vals


def _apply_tint(hexv: str, tint: float) -> str:
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    r, g, b = colorsys.hls_to_rgb(h, max(0, min(1, l)), s)
    return "".join(f"{round(x * 255):02X}" for x in (r, g, b))


def resolve_color(color, theme: list[str] | None) -> str | None:
    """Gibt '#RRGGBB' zurück, egal ob die Farbe als RGB, Theme oder Index gespeichert ist."""
    if color is None:
        return None
    try:
        typ = color.type
        if typ == "rgb":
            rgb = color.rgb
            if not isinstance(rgb, str) or rgb == "00000000":
                return None
            hexv = rgb[-6:]
        elif typ == "theme":
            if not theme or color.theme >= len(theme):
                return f"theme{color.theme}"
            hexv = theme[color.theme]
        elif typ == "indexed":
            from openpyxl.styles.colors import COLOR_INDEX
            if color.indexed >= len(COLOR_INDEX) or color.indexed == 64:
                return None
            hexv = COLOR_INDEX[color.indexed][-6:]
        else:
            return None
        tint = color.tint or 0
        if tint:
            hexv = _apply_tint(hexv, tint)
        return "#" + hexv.upper()
    except Exception:
        return None


# ---------------------------------------------------------------- Manifest
def iter_sheets(manifest: dict, nur_aktiv: bool = True):
    """Liefert (datei_eintrag, blatt_eintrag). nur_aktiv: ohne Duplikate/fehlende/unlesbare."""
    for fid, f in manifest.get("dateien", {}).items():
        if nur_aktiv and (f.get("fehlt_im_input") or f.get("duplikat_von") or not f.get("lesbar", True)):
            continue
        for b in f.get("blaetter", []):
            if nur_aktiv and b.get("duplikat_von"):
                continue
            yield f, b


def find_sheet(manifest: dict, blatt_id: str):
    for f, b in iter_sheets(manifest, nur_aktiv=False):
        if b["blatt_id"] == blatt_id:
            return f, b
    raise SystemExit(f"Blatt-ID {blatt_id} nicht im Manifest.")


def append_log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text("# Session-Log (append-only)\n\n", encoding="utf-8")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"- {now()} {line}\n")
