#!/usr/bin/env python3
"""Zeichnet den Index-Chart der DAX- bzw. US30-Notiz als PNG (nur Standardbibliothek, läuft überall).

  python3 scripts/chart.py [--bericht dax|us30] --datum JJJJ-MM-TT

Liest daten/<bericht>/JJJJ-MM-TT.json (Stundenkerzen) und entscheidungen/<bericht>/JJJJ-MM-TT.json (Spanne, Grenzen)
und schreibt notizen/<bericht>/charts/JJJJ-MM-TT.png (+ .json für den beweglichen Chart): die letzten 5 Handelstage in Stundenkerzen, Vortageshoch,
-tief und -schluss, rechts der heutige Tag mit erwarteter Range (oben/unten) und Referenzkurs.
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
TREND = {"bull": (234, 246, 236), "bear": (251, 234, 234)}
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
        """Palette-PNG (wenige Farben): viel kleiner als RGB, wichtig für das eingebettete Bild in der Mail."""
        b, h = self.b * self.s, self.h * self.s
        farben, idx = [], {}
        zeilen = []
        for y in range(h):
            zeile = bytearray(b"\x00")
            for x in range(b):
                i = (y * b + x) * 3
                f = bytes(self.px[i:i + 3])
                if f not in idx:
                    idx[f] = len(farben)
                    farben.append(f)
                zeile.append(idx[f])
            zeilen.append(bytes(zeile))
        if len(farben) > 256:
            raise SystemExit("Zu viele Farben für ein Palette-PNG.")
        def chunk(art, daten):
            return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
        Path(pfad).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", b, h, 8, 3, 0, 0, 0))
                              + chunk(b"PLTE", b"".join(farben)) + chunk(b"IDAT", zlib.compress(b"".join(zeilen), 9))
                              + chunk(b"IEND", b""))


def zahl(v):
    return f"{v:,.0f}".replace(",", ".")


def mail_html(kerzen, tage, trend, e, d, vh, vt, vs, cfg):
    """Chart für die Mail als reines HTML (keine Bilddatei): Bilder müssten als Base64 abgetippt werden und kommen dann
    kaputt an. Kerzen = gestapelte div-Kästchen, Hintergrund = großer Trend je Tag, rechts die erwartete Range heute."""
    H = 220
    werte = [c["h"] for c in kerzen] + [c["l"] for c in kerzen] + list(e.get("spanne") or []) + ([e["referenz"]] if e.get("referenz") else [])
    lo, hi = min(werte), max(werte)
    rand = (hi - lo) * 0.04 or 20
    lo, hi = lo - rand, hi + rand
    y = lambda v: round((hi - v) / (hi - lo) * H)
    farbe = {"bull": "#e6f4e8", "bear": "#fae6e6"}
    zellen = []
    for t in tage:  # je Tag eine Zelle mit Trend-Hintergrund, darin die Stundenkerzen
        innen = []
        for c in (k for k in kerzen if k["tag"] == t):
            f = "#183" if c["c"] >= c["o"] else "#c23"
            o, u = max(c["o"], c["c"]), min(c["o"], c["c"])
            hoehen = [(y(c["h"]), 0), (y(o) - y(c["h"]), 1), (max(1, y(u) - y(o)), 7), (y(c["l"]) - y(u), 1)]
            innen.append('<td valign="top" width="9">' + "".join(
                f'<div style="height:{h}px' + (f';width:{w}px;margin:auto;background:{f}' if w else "") + '"></div>'
                for h, w in hoehen if h > 0) + "</td>")
        zellen.append(f'<td valign="top" style="border-left:1px solid #bbb;background:{farbe.get(trend.get(t), "#fff")}">'
                      f'<table cellpadding="0" cellspacing="0"><tr style="height:{H}px">{"".join(innen)}</tr></table></td>')
    # Heute-Spalte Zeile für Zeile malen (Range-Band, Linien für Vortageshoch/-schluss/-tief und Kurs), dann zusammenfassen
    zeilen = [None] * H
    if e.get("spanne"):
        for i in range(max(0, y(e["spanne"][1])), min(H, y(e["spanne"][0]) + 1)):
            zeilen[i] = "#deebfa"
    linien = [(vh, "#999"), (vt, "#999"), (vs, "#333")] + ([(e["referenz"], "#285aaa")] if e.get("referenz") else [])
    if e.get("spanne"):
        linien += [(e["spanne"][1], "#285aaa"), (e["spanne"][0], "#285aaa")]
    for wert, f in linien:
        for i in (y(wert), y(wert) + 1 if f == "#285aaa" else -1):
            if 0 <= i < H:
                zeilen[i] = f
    blöcke, i = [], 0
    while i < H:
        j = i
        while j < H and zeilen[j] == zeilen[i]:
            j += 1
        blöcke.append(f'<div style="height:{j - i}px' + (f';background:{zeilen[i]}' if zeilen[i] else "") + '"></div>')
        i = j
    zellen.append(f'<td style="border-left:2px solid #888;width:60px;vertical-align:top;background:{farbe.get(trend.get(d), "#fff")}">{"".join(blöcke)}</td>')
    # Preisachse: Marken mit Namen, dazwischen runde Kurse; Beschriftungen ohne Überlappung
    marken = [(vh, f"Hoch {zahl(vh)}", "#777"), (vs, f"Schluss {zahl(vs)}", "#333"), (vt, f"Tief {zahl(vt)}", "#777")]
    if e.get("referenz"):
        marken.append((e["referenz"], f"Kurs {zahl(e['referenz'])}", "#285aaa"))
    if e.get("spanne"):
        marken += [(e["spanne"][1], f"Range {zahl(e['spanne'][1])}", "#285aaa"), (e["spanne"][0], f"Range {zahl(e['spanne'][0])}", "#285aaa")]
    stufe = next(x for x in (25, 50, 100, 200, 250, 500, 1000, 2000) if (hi - lo) / x <= 6)
    gitter, v = [], (int(lo // stufe) + 1) * stufe
    while v < hi:
        gitter.append((v, zahl(v), "#aaa"))
        v += stufe
    L_H = 12
    belegt = []
    for wert, text, f in sorted(marken, key=lambda m: -m[0]):
        ty = max(0, y(wert) - L_H // 2)
        while any(abs(ty - b) < L_H for b, _, _ in belegt):
            ty += 1
        belegt.append((ty, text, f))
    for wert, text, f in gitter:
        ty = y(wert) - L_H // 2
        if 0 <= ty <= H - L_H and not any(abs(ty - b) < L_H + 2 for b, _, _ in belegt):
            belegt.append((ty, text, f))
    teile, pos = [], 0
    for ty, text, f in sorted(belegt):
        if ty > pos:
            teile.append(f'<div style="height:{ty - pos}px"></div>')
        teile.append(f'<div style="height:{L_H}px;line-height:{L_H}px;color:{f}">– {text}</div>')
        pos = max(pos, ty) + L_H
    achse = (f'<td style="padding:0 0 0 2px;vertical-align:top;font:10px Arial;white-space:nowrap">{"".join(teile)}</td>')
    wt = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    kopf = "".join(f'<td style="font:11px Arial;color:#666;padding:2px 4px">'
                   f'{wt[date.fromisoformat(t).weekday()]} {date.fromisoformat(t):%d.%m.}</td>' for t in tage)
    kopf += f'<td style="font:bold 11px Arial;padding:2px 4px">Heute</td><td></td>'
    st = trend.get(d)
    legende = ("Hintergrund: großer Trend, grün = Bull, rot = Bear" + (f" (heute {st.capitalize()})" if st else "")) if trend else ""
    return (f'<table style="border-collapse:collapse;border:1px solid #ddd" cellpadding="0" cellspacing="0">'
            f'<tr style="height:{H}px">{"".join(zellen)}{achse}</tr><tr>{kopf}</tr></table>'
            f'<p style="font:12px Arial;color:#555;margin:4px 0">{cfg["name"]}, 60-Minuten-Kerzen der letzten 5 Tage. '
            f'Rechts heute: Vortageshoch, Schluss und Vortagestief (graue/schwarze Linien), Kurs zur Notiz (blaue Linie), '
            f'erwartete Range bis Schluss (blaues Feld). {legende}.</p>')


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

    trend = {v["tag"]: v["stand"] for v in (daten.get("trendfolge") or {}).get("verlauf", [])}
    B, H = 1000, 460
    L, R, O, U = 20, 870, 52, 400          # Zeichenfläche
    heute_slots = len(cfg["stunden"])
    slots = len(kerzen) + heute_slots + 1
    schritt = (R - L) / slots
    werte = [c["h"] for c in kerzen] + [c["l"] for c in kerzen]
    for key in ("spanne",):
        werte += e.get(key) or []
    for key in ("referenz",):
        if e.get(key):
            werte.append(e[key])
    lo, hi = min(werte), max(werte)
    rand = (hi - lo) * 0.06 or 50
    lo, hi = lo - rand, hi + rand
    y = lambda v: U - (v - lo) / (hi - lo) * (U - O)

    def zeichne(s):
        bild = Bild(B, H, s)
        # Hintergrund: großer Trend (Bull/Bear) Tag für Tag, so wie er an dem Tag galt
        x = L
        for t in tage:
            n = sum(1 for c in kerzen if c["tag"] == t)
            f = TREND.get(trend.get(t))
            if f:
                bild.rechteck(x, O, x + n * schritt, U, f)
            x += n * schritt
        if TREND.get(trend.get(d)):
            bild.rechteck(x, O, R, U, TREND[trend[d]])
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
        # Heute: Kurs zur Notiz und Range
        if e.get("referenz"):
            bild.waagerecht(x_heute, R, y(e["referenz"]), BLAU, dicke=2)
            if e.get("referenz_art") != "Indikation" and abs(e["referenz"] - vs) < 1:
                marken = [m for m in marken if not m[1].startswith("SCHLUSS")]
                marken.append((vs, f"SCHLUSS {zahl(vs)} = REF.", BLAU))
            else:
                    marken.append((e["referenz"], f"{ {'Indikation': 'INDIKATION', 'Einstieg': 'KURS', 'Kurs zur Notiz': 'KURS'}.get(e.get('referenz_art'), 'REFERENZ') } {zahl(e['referenz'])}", BLAU))
        if e.get("spanne"):
            marken.append((e["spanne"][1], f"RANGE OBEN {zahl(e['spanne'][1])}", BLAU))
            marken.append((e["spanne"][0], f"RANGE UNTEN {zahl(e['spanne'][0])}", BLAU))
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
            bild.text(L, 36, f"ERWARTETE RANGE {zahl(e['spanne'][0])} - {zahl(e['spanne'][1])} (VOLA {e['vola_pct']:.1f} %)".replace(f"{e['vola_pct']:.1f}", f"{e['vola_pct']:.1f}".replace(".", ",")), LEISE)
        bild.text(B - 10, H - 14, "QUELLE: YAHOO FINANCE, EIGENE BERECHNUNG", LEISE, rechts=True)
        if trend:
            legende = "HINTERGRUND: GROSSER TREND (3 MONATE, TAEGLICH)  GRUEN = BULL  ROT = BEAR"
            bild.text(L, H - 14, legende, LEISE)
        return bild

    ziel = ROOT / "notizen" / a.bericht / "charts" / f"{a.name or d}.png"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    zeichne(2).png(ziel)
    print(f"Chart: {ziel.relative_to(ROOT)}")
    # Chart für die Mail als HTML (kein Bild): wird unverändert in den htmlBody übernommen
    mail = ziel.with_name(ziel.stem + "-mail.html")
    mail.write_text(mail_html(kerzen, tage, trend, e, d, vh, vt, vs, cfg), encoding="utf-8")
    print(f"Chart für die Mail (HTML): {mail.relative_to(ROOT)} ({mail.stat().st_size} Zeichen)")

    # Daten für den beweglichen Chart auf der Webseite (docs/chart.js)
    boerse = ZoneInfo(cfg["tz"])
    dt = date.fromisoformat(d)
    heute_slots = [int(datetime(dt.year, dt.month, dt.day, h, m, tzinfo=boerse).astimezone(timezone.utc).timestamp()) for h, m in cfg["stunden"]]
    linien = [
        {"name": "Vortageshoch", "preis": vh, "farbe": "leise", "stil": "gestrichelt"},
        {"name": "Vortagestief", "preis": vt, "farbe": "leise", "stil": "gestrichelt"},
        {"name": "Vortagesschluss", "preis": vs, "farbe": "text", "stil": "gepunktet"},
    ]
    if e.get("referenz_art") != "Indikation" and e.get("referenz") and abs(e["referenz"] - vs) < 1:
        linien[-1] = {"name": "Vortagesschluss = Referenz", "preis": vs, "farbe": "blau", "stil": "durchgezogen"}
    if e.get("referenz") and not (e.get("referenz_art") != "Indikation" and abs(e["referenz"] - vs) < 1):
        linien.append({"name": {"Indikation": "Indikation", "Einstieg": "Kurs zur Notiz", "Kurs zur Notiz": "Kurs zur Notiz"}.get(e.get("referenz_art"), "Referenz"), "preis": e["referenz"], "farbe": "blau", "stil": "durchgezogen"})
    if e.get("spanne"):
        linien += [{"name": "Erwartete Range oben", "preis": e["spanne"][1], "farbe": "band", "stil": "gestrichelt", "dick": True},
                   {"name": "Erwartete Range unten", "preis": e["spanne"][0], "farbe": "band", "stil": "gestrichelt", "dick": True}]
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
        "trend": trend,
    }
    (ziel.with_suffix(".json")).write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    print(f"Daten für beweglichen Chart: {ziel.with_suffix('.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
