#!/usr/bin/env python3
"""Zeichnet den Index-Chart der DAX- bzw. US30-Notiz als PNG (nur Standardbibliothek, läuft überall).

  python3 scripts/chart.py [--bericht dax|us30] --datum JJJJ-MM-TT

Liest daten/<bericht>/JJJJ-MM-TT.json (Stundenkerzen) und entscheidungen/<bericht>/JJJJ-MM-TT.json (Spanne, Grenzen)
und schreibt notizen/<bericht>/charts/JJJJ-MM-TT.png (+ .json für den beweglichen Chart): die letzten 5 Handelstage in Stundenkerzen, Vortageshoch,
-tief und -schluss, rechts der heutige Tag mit erwarteter Spanne, Referenzkurs, Ober- und Untergrenze.
"""

import argparse
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import struct
import zlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# index = Schlüssel der Tageskerzen, tz/stunden = Börsenzeitzone und Beginn der Stundenkerzen einer Sitzung
BERICHTE = {
    "dax": {"index": "dax", "name": "DAX", "tz": "Europe/Berlin", "stunden": [(h, 0) for h in range(9, 18)]},
    "us30": {"index": "dow", "name": "DOW JONES", "tz": "America/New_York", "stunden": [(h, 30) for h in range(9, 16)]},
}

# 5×7-Pixelschrift (Großbuchstaben, Ziffern, wenige Zeichen)
SCHRIFT = {
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    ".": "00000 00000 00000 00000 00000 01100 01100", ",": "00000 00000 00000 00000 01100 00100 01000",
    ":": "00000 01100 01100 00000 01100 01100 00000", "-": "00000 00000 00000 11111 00000 00000 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000", "%": "11000 11001 00010 00100 01000 10011 00011",
    "/": "00000 00001 00010 00100 01000 10000 00000", "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000", "±": "00100 00100 11111 00100 00100 00000 11111",
    "=": "00000 00000 11111 00000 11111 00000 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
}
UMLAUT = str.maketrans({"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS", "−": "-", "–": "-", "·": "-"})

WEISS, TEXT, GITTER, LEISE = (255, 255, 255), (40, 40, 38), (232, 232, 228), (140, 140, 135)
GRUEN, ROT, BAND, GOLD, BLAU = (26, 127, 55), (207, 34, 46), (222, 235, 250), (184, 134, 11), (40, 90, 170)


class Bild:
    def __init__(self, b, h, s=2):
        self.b, self.h, self.s = b, h, s
        self.px = bytearray(WEISS * (b * s * h * s))

    def punkt(self, x, y, f):
        if 0 <= x < self.b * self.s and 0 <= y < self.h * self.s:
            i = (y * self.b * self.s + x) * 3
            self.px[i:i + 3] = bytes(f)

    def rechteck(self, x0, y0, x1, y1, f):
        s = self.s
        xa, xb = sorted((round(x0 * s), round(x1 * s)))
        ya, yb = sorted((round(y0 * s), round(y1 * s)))
        for y in range(max(ya, 0), min(max(yb, ya + 1), self.h * s)):
            for x in range(max(xa, 0), min(max(xb, xa + 1), self.b * s)):
                i = (y * self.b * s + x) * 3
                self.px[i:i + 3] = bytes(f)

    def waagerecht(self, x0, x1, y, f, strich=0, dicke=1):
        if not strich:
            return self.rechteck(x0, y, x1, y + dicke, f)
        x = x0
        while x < x1:
            self.rechteck(x, y, min(x + strich, x1), y + dicke, f)
            x += 2 * strich

    def text(self, x, y, t, f, groesse=1, rechts=False):
        t = str(t).upper().translate(UMLAUT)
        breite = len(t) * 6 * groesse
        x = x - breite if rechts else x
        for i, z in enumerate(t):
            zeilen = SCHRIFT.get(z, SCHRIFT[" "]).split()
            for r, zeile in enumerate(zeilen):
                for c, bit in enumerate(zeile):
                    if bit == "1":
                        self.rechteck(x + (i * 6 + c) * groesse, y + r * groesse,
                                      x + (i * 6 + c + 1) * groesse, y + (r + 1) * groesse, f)

    def png(self, pfad):
        b, h = self.b * self.s, self.h * self.s
        roh = b"".join(b"\x00" + bytes(self.px[y * b * 3:(y + 1) * b * 3]) for y in range(h))
        def chunk(art, daten):
            return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
        Path(pfad).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", b, h, 8, 2, 0, 0, 0))
                              + chunk(b"IDAT", zlib.compress(roh, 9)) + chunk(b"IEND", b""))


def zahl(v):
    return f"{v:,.0f}".replace(",", ".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bericht", default="dax", choices=list(BERICHTE))
    ap.add_argument("--datum", required=True)
    ap.add_argument("--entscheidung", help="andere Entscheidungsdatei (Sonderausgabe)")
    ap.add_argument("--name", help="Dateiname ohne .png, Standard = Datum (Sonderausgabe: JJJJ-MM-TT-HHMM)")
    a = ap.parse_args()
    d = date.fromisoformat(a.datum).isoformat()
    cfg = BERICHTE[a.bericht]
    daten = json.loads((ROOT / "daten" / a.bericht / f"{d}.json").read_text(encoding="utf-8"))
    e_pfad = Path(a.entscheidung) if a.entscheidung else ROOT / "entscheidungen" / a.bericht / f"{d}.json"
    e = json.loads(e_pfad.read_text(encoding="utf-8")) if e_pfad.exists() else {}

    kerzen = [c for c in daten.get("index_stunden", []) if c["tag"] < d]
    tage = sorted({c["tag"] for c in kerzen})[-5:]
    kerzen = [c for c in kerzen if c["tag"] in tage]
    if not kerzen:
        raise SystemExit("Keine Stundenkerzen für den Chart.")
    vortag = [c for c in kerzen if c["tag"] == tage[-1]]
    vh, vt, vs = max(c["h"] for c in vortag), min(c["l"] for c in vortag), vortag[-1]["c"]
    k = daten.get("index_kennzahlen") or {}
    if k.get("letzter_handelstag") == tage[-1]:
        vh, vt, vs = k.get("hoch") or vh, k.get("tief") or vt, k.get("schluss") or vs

    B, H = 1000, 460
    L, R, O, U = 20, 870, 52, 400          # Zeichenfläche
    heute_slots = len(cfg["stunden"])
    slots = len(kerzen) + heute_slots + 1
    schritt = (R - L) / slots
    werte = [c["h"] for c in kerzen] + [c["l"] for c in kerzen]
    for key in ("spanne",):
        werte += e.get(key) or []
    for key in ("ziel_ca", "stopp_ca", "referenz"):
        if e.get(key):
            werte.append(e[key])
    lo, hi = min(werte), max(werte)
    rand = (hi - lo) * 0.06 or 50
    lo, hi = lo - rand, hi + rand
    y = lambda v: U - (v - lo) / (hi - lo) * (U - O)

    bild = Bild(B, H)
    # Gitter mit Kursen
    stufe = next(s for s in (25, 50, 100, 200, 250, 500, 1000) if (hi - lo) / s <= 8)
    v = (int(lo // stufe) + 1) * stufe
    while v < hi:
        bild.waagerecht(L, R, y(v), GITTER)
        bild.text(R + 6, y(v) - 3, zahl(v), LEISE)
        v += stufe
    # Tagestrenner und Beschriftung
    wt = ["MO", "DI", "MI", "DO", "FR", "SA", "SO"]
    x = L
    for t in tage:
        n = sum(1 for c in kerzen if c["tag"] == t)
        bild.rechteck(x, O, x + 1, U, GITTER)
        dt = date.fromisoformat(t)
        bild.text(x + 4, U + 8, f"{wt[dt.weekday()]} {dt:%d.%m.}", LEISE)
        x += n * schritt
    x_heute = L + (len(kerzen) + 1) * schritt
    bild.rechteck(x_heute - schritt / 2, O, x_heute - schritt / 2 + 1, U, LEISE)
    dt = date.fromisoformat(d)
    bild.text(x_heute + 4, U + 8, f"HEUTE {wt[dt.weekday()]} {dt:%d.%m.}", TEXT)
    # Erwartete Spanne heute
    if e.get("spanne"):
        bild.rechteck(x_heute, y(e["spanne"][1]), R, y(e["spanne"][0]), BAND)
    # Kerzen
    for i, c in enumerate(kerzen):
        xm = L + (i + 0.5) * schritt
        f = GRUEN if c["c"] >= c["o"] else ROT
        bild.rechteck(xm - 0.6, y(c["h"]), xm + 0.6, y(c["l"]), f)
        bild.rechteck(xm - schritt * 0.32, y(max(c["o"], c["c"])), xm + schritt * 0.32, y(min(c["o"], c["c"])) + 1, f)
    # Vortagesmarken über die ganze Breite
    bild.waagerecht(L, R, y(vh), LEISE, strich=4)
    bild.waagerecht(L, R, y(vt), LEISE, strich=4)
    bild.waagerecht(L, R, y(vs), TEXT, strich=2)
    marken = [(vh, f"VORTAGESHOCH {zahl(vh)}", LEISE), (vt, f"VORTAGESTIEF {zahl(vt)}", LEISE), (vs, f"SCHLUSS {zahl(vs)}", TEXT)]
    # Heute: Referenz, Ziel, Stopp
    if e.get("referenz"):
        bild.waagerecht(x_heute, R, y(e["referenz"]), BLAU, dicke=2)
        if e.get("referenz_art") != "Indikation" and abs(e["referenz"] - vs) < 1:
            marken = [m for m in marken if not m[1].startswith("SCHLUSS")]
            marken.append((vs, f"SCHLUSS {zahl(vs)} = REF.", BLAU))
        else:
                marken.append((e["referenz"], f"{'INDIKATION' if e.get('referenz_art') == 'Indikation' else 'REFERENZ'} {zahl(e['referenz'])}", BLAU))
    if e.get("ziel_ca"):
        bild.waagerecht(x_heute, R, y(e["ziel_ca"]), GRUEN, strich=5, dicke=2)
        grenze = "OBERGRENZE" if e["ziel_ca"] > (e.get("referenz") or 0) else "UNTERGRENZE"
        marken.append((e["ziel_ca"], f"{grenze} CA. {zahl(e['ziel_ca'])}", GRUEN))
    if e.get("stopp_ca"):
        bild.waagerecht(x_heute, R, y(e["stopp_ca"]), ROT, strich=5, dicke=2)
        grenze = "OBERGRENZE" if e["stopp_ca"] > (e.get("referenz") or 0) else "UNTERGRENZE"
        marken.append((e["stopp_ca"], f"{grenze} CA. {zahl(e['stopp_ca'])}", ROT))
    # Beschriftungen links im Heute-Bereich, ohne Überlappung
    belegt = []
    for wert, label, farbe in sorted(marken, key=lambda m: -m[0]):
        ty = y(wert) - 10
        while any(abs(ty - b) < 10 for b in belegt):
            ty += 10
        belegt.append(ty)
        bild.rechteck(x_heute + 2, ty - 2, x_heute + 6 + len(label) * 6, ty + 9, WEISS)  # Hintergrund, damit keine Linie durch den Text läuft
        bild.text(x_heute + 4, ty, label, farbe)
    # Titel
    richtung = (e.get("richtung") or "").upper()
    kopf = f"{cfg['name']} - 60 MIN - LETZTE 5 TAGE"
    if richtung:
        kopf += f" - HEUTE {richtung}" + (f" {e['score']}/10" if e.get("score") else "")
    bild.text(L, 14, kopf, TEXT, groesse=2)
    if e.get("spanne"):
        bild.text(L, 36, f"ERWARTETE SPANNE {zahl(e['spanne'][0])} - {zahl(e['spanne'][1])} (VOLA {e['vola_pct']:.1f} %)".replace(f"{e['vola_pct']:.1f}", f"{e['vola_pct']:.1f}".replace(".", ",")), LEISE)
    bild.text(B - 10, H - 14, "QUELLE: YAHOO FINANCE, EIGENE BERECHNUNG", LEISE, rechts=True)

    ziel = ROOT / "notizen" / a.bericht / "charts" / f"{a.name or d}.png"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bild.png(ziel)
    print(f"Chart: {ziel.relative_to(ROOT)}")

    # Daten für den beweglichen Chart auf der Webseite (docs/chart.js)
    boerse = ZoneInfo(cfg["tz"])
    heute_slots = [int(datetime(dt.year, dt.month, dt.day, h, m, tzinfo=boerse).astimezone(timezone.utc).timestamp()) for h, m in cfg["stunden"]]
    linien = [
        {"name": "Vortageshoch", "preis": vh, "farbe": "leise", "stil": "gestrichelt"},
        {"name": "Vortagestief", "preis": vt, "farbe": "leise", "stil": "gestrichelt"},
        {"name": "Vortagesschluss", "preis": vs, "farbe": "text", "stil": "gepunktet"},
    ]
    if e.get("referenz_art") != "Indikation" and e.get("referenz") and abs(e["referenz"] - vs) < 1:
        linien[-1] = {"name": "Vortagesschluss = Referenz", "preis": vs, "farbe": "blau", "stil": "durchgezogen"}
    if e.get("referenz") and not (e.get("referenz_art") != "Indikation" and abs(e["referenz"] - vs) < 1):
        linien.append({"name": "Indikation" if e.get("referenz_art") == "Indikation" else "Referenz", "preis": e["referenz"], "farbe": "blau", "stil": "durchgezogen"})
    for key, seite in (("ziel_ca", "Gewinnmitnahme"), ("stopp_ca", "Idee widerlegt")):
        if e.get(key):
            grenze = "Obergrenze" if e[key] > (e.get("referenz") or vs) else "Untergrenze"
            linien.append({"name": f"{grenze} · {seite}", "preis": e[key], "farbe": "plus" if key == "ziel_ca" else "minus", "stil": "gestrichelt", "dick": True})
    if e.get("spanne"):
        linien += [{"name": "Spanne oben", "preis": e["spanne"][1], "farbe": "band", "stil": "gepunktet"},
                   {"name": "Spanne unten", "preis": e["spanne"][0], "farbe": "band", "stil": "gepunktet"}]
    tage_alle = [c for c in (daten.get("maerkte", {}).get(cfg["index"], {}).get("kerzen") or []) if c["tag"] < d]
    live = {
        "datum": d,
        "zeitzone": cfg["tz"],
        "richtung": e.get("richtung"),
        "score": e.get("score"),
        "stunden": [{"time": c["t"], "open": c["o"], "high": c["h"], "low": c["l"], "close": c["c"]}
                    for c in daten.get("index_stunden", []) if c["tag"] < d],
        "tage": [{"time": c["tag"], "open": c["o"], "high": c["h"], "low": c["l"], "close": c["c"]} for c in tage_alle],
        "heute_slots": heute_slots,
        "linien": [l for l in linien if l["preis"]],
    }
    (ziel.with_suffix(".json")).write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    print(f"Daten für beweglichen Chart: {ziel.with_suffix('.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
