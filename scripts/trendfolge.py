"""Großer Trend für die Notiz: Absolute Momentum mit 3 Monaten Rückschau (nach Antonacci 2014, dort 12 Monate).

Regel: Am letzten Handelstag jedes Monats
    r = Schluss / Schluss am Monatsende vor 3 Monaten − 1
    z = Mittel des Jahreszinses an den 3 Monatsenden × 3/12   (DAX: EZB-Einlagensatz, Dow: 13-Wochen-T-Bill ^IRX)
    r > z → Bull (investiert), sonst Bear (Cash). Gewechselt wird zur Eröffnung nach dem Monatsschluss.
Ein Monatsende zählt erst, wenn der neue Monat begonnen hat; die laufende Tageskerze geht nie in eine Entscheidung ein.
Forschung und Rückrechnung dazu: t1/wissen/momentum_3m.py (nicht im Repo).

Aufruf:  python3 scripts/trendfolge.py [--bericht dax|us30] [--datum JJJJ-MM-TT]
Schreibt den Block "trendfolge" in daten/<bericht>/<datum>.json (falls vorhanden) und gibt eine Zusammenfassung aus.
Nur Standardbibliothek.
"""

import argparse
import bisect
import csv
import datetime as dt
import io
import json
import os
import urllib.request

MONATE = 3
UA = {"User-Agent": "Mozilla/5.0"}
BERICHTE = {
    "dax": {"name": "DAX", "symbol": "^GDAXI", "zins": "EZB-Einlagensatz"},
    "us30": {"name": "Dow", "symbol": "^DJI", "zins": "US-T-Bill 13 Wochen (^IRX)"},
}
# Ersatz, falls die EZB-Datenbank nicht erreichbar ist (Beschlüsse, gültig ab; geprüft am 06.11.2026)
EZB_ERSATZ = [("2024-06-12", 3.75), ("2024-09-18", 3.50), ("2024-10-23", 3.25), ("2024-12-18", 3.00),
              ("2025-02-05", 2.75), ("2025-03-12", 2.50), ("2025-04-23", 2.25), ("2025-06-11", 2.00),
              ("2026-06-17", 2.25), ("2026-09-16", 2.50)]
HINWEIS = ("3 Monate Rückschau sind eine eigene Wahl, das Paper nutzt 12. Kürzere Rückschau bringt mehr Fehlsignale, "
           "wenn der Markt schnell dreht. Monatssignal, kein Tagessignal. Keine Anlageberatung.")


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def tageskurse(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(symbol)}?range=2y&interval=1d"
    res = json.loads(hole(url))["chart"]["result"][0]
    off = res["meta"].get("gmtoffset", 0)
    rows = []
    for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
        if c is None or c <= 0:
            continue
        d = dt.datetime.fromtimestamp(t + off, dt.timezone.utc).date().isoformat()
        if rows and rows[-1]["d"] == d:
            rows.pop()
        rows.append({"d": d, "c": c})
    return rows


def zinsreihe(bericht):
    """Liste (Datum, Jahreszins %) und Quelle."""
    if bericht == "us30":
        return [(x["d"], x["c"]) for x in tageskurse("^IRX")], "Yahoo ^IRX"
    try:
        url = ("https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV"
               "?format=csvdata&startPeriod=2023-01-01")
        reihe = [(r["TIME_PERIOD"], float(r["OBS_VALUE"])) for r in csv.DictReader(io.StringIO(hole(url).decode()))
                 if r.get("OBS_VALUE")]
        if reihe:
            return reihe, "EZB-Datenbank"
    except Exception:
        pass
    return EZB_ERSATZ, "hinterlegte Tabelle (EZB-Datenbank nicht erreichbar)"


def monatsenden(daily):
    return [i for i in range(len(daily) - 1) if daily[i + 1]["d"][:7] != daily[i]["d"][:7]]


def handelstag(bericht, d):
    fest = {"dax": {"01-01", "05-01", "12-24", "12-25", "12-26", "12-31"}, "us30": {"01-01", "06-19", "07-04", "12-25"}}
    if d.weekday() >= 5 or d.strftime("%m-%d") in fest[bericht]:
        return False
    j = d.year
    a, b, c = j % 19, j // 100, j % 100
    h = (19 * a + b - b // 4 - (b - (b + 8) // 25 + 1) // 3 + 15) % 30
    l = (32 + 2 * (b % 4) + 2 * (c // 4) - h - c % 4) % 7
    m = (a + 11 * h + 22 * l) // 451
    ostern = dt.date(j, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)
    if d == ostern - dt.timedelta(days=2) or (bericht == "dax" and d == ostern + dt.timedelta(days=1)):
        return False
    if bericht == "us30" and d.month == 5 and d.weekday() == 0 and d.day > 24:  # Memorial Day
        return False
    return True


def letzter_handelstag(bericht, jahr, monat):
    d = dt.date(jahr + monat // 12, monat % 12 + 1, 1) - dt.timedelta(days=1)
    while not handelstag(bericht, d):
        d -= dt.timedelta(days=1)
    return d


def berechne(bericht, heute=None):
    cfg = BERICHTE[bericht]
    daily = tageskurse(cfg["symbol"])
    if heute:
        daily = [x for x in daily if x["d"] <= heute]
    reihe, zquelle = zinsreihe(bericht)
    tage = [d for d, _ in reihe]
    zins = lambda d: reihe[max(0, bisect.bisect_right(tage, d) - 1)][1]
    me = monatsenden(daily)
    k = len(me) - 1
    i, j = me[k], me[k - MONATE]
    r = daily[i]["c"] / daily[j]["c"] - 1
    z = sum(zins(daily[me[x]]["d"]) for x in range(k - MONATE + 1, k + 1)) / MONATE / 100 * MONATE / 12
    inv = r > z
    # vorige Entscheidung: gab es zuletzt einen Wechsel?
    i0, j0 = me[k - 1], me[k - 1 - MONATE]
    r0 = daily[i0]["c"] / daily[j0]["c"] - 1
    z0 = sum(zins(daily[me[x]]["d"]) for x in range(k - MONATE, k)) / MONATE / 100 * MONATE / 12
    jetzt = daily[-1]
    t = dt.date.fromisoformat(jetzt["d"])
    naechste = letzter_handelstag(bericht, t.year, t.month)
    # Am nächsten Monatsende ist me[k-2] das Monatsende vor 3 Monaten; Zins: die zwei letzten Monatsenden plus heute
    ref = daily[me[k - MONATE + 1]]
    z_next = (sum(zins(daily[me[x]]["d"]) for x in range(k - MONATE + 2, k + 1)) + zins(jetzt["d"])) / 100 / 12
    kipp = ref["c"] * (1 + z_next)
    return {
        "regel": "Absolute Momentum, 3 Monate (Antonacci 2014: 12 Monate)",
        "index": cfg["name"], "stand": "bull" if inv else "bear",  # bull = investiert, bear = Cash
        "letzte_entscheidung": {"datum": daily[i]["d"], "r": round(r, 5), "z": round(z, 5), "seit": daily[j]["d"],
                                "kurs": round(daily[i]["c"], 2), "wechsel": inv != (r0 > z0)},
        "naechste_entscheidung": naechste.isoformat(),
        "kipp_kurs": round(kipp, 0), "kipp_richtung": "unter" if inv else "über",
        "kipp_basis": {"datum": ref["d"], "kurs": round(ref["c"], 2), "z": round(z_next, 5)},
        "kurs_jetzt": round(jetzt["c"], 2), "kurs_tag": jetzt["d"], "abstand": round(jetzt["c"] / kipp - 1, 5),
        "wuerde_jetzt": "bull" if jetzt["c"] > kipp else "bear",
        "zins": cfg["zins"], "zins_jetzt": zins(jetzt["d"]), "zins_quelle": zquelle,
        "quelle": "Yahoo Finance Tagesschlusskurse", "hinweis": HINWEIS,
    }


def text(s):
    de = lambda x, n=0: f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    pct = lambda x: ("+" if x >= 0 else "−") + de(abs(x) * 100, 2) + " %"
    dat = lambda d: f"{d[8:10]}.{d[5:7]}.{d[:4]}"
    L = s["letzte_entscheidung"]
    return "\n".join([
        f"Großer Trend (3-Monats-Momentum) {s['index']}: {s['stand'].upper()}"
        + (" (Wechsel am letzten Monatsende)" if L["wechsel"] else ""),
        f"  Entscheidung {dat(L['datum'])}: r = {pct(L['r'])} seit {dat(L['seit'])} gegen z = {pct(L['z'])} ({s['zins']})",
        f"  Nächste Entscheidung {dat(s['naechste_entscheidung'])} zum Schluss. Dreht bei Schluss {s['kipp_richtung']} "
        f"{de(s['kipp_kurs'])} (jetzt {de(s['kurs_jetzt'])}, Abstand {pct(s['abstand'])}; stünde der Monat jetzt, wäre es {s['wuerde_jetzt']}).",
        f"  Zins jetzt {de(s['zins_jetzt'], 2)} % ({s['zins_quelle']}). {s['hinweis']}",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bericht", default="dax", choices=BERICHTE)
    ap.add_argument("--datum", default=None)
    a = ap.parse_args()
    basis = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    try:
        s = berechne(a.bericht, a.datum)
    except Exception as e:
        print(f"Großer Trend: n/v ({type(e).__name__}: {e})")
        return
    print(text(s))
    datum = a.datum or dt.date.today().isoformat()
    pfad = os.path.join(basis, "daten", a.bericht, f"{datum}.json")
    if os.path.exists(pfad):
        with open(pfad) as f:
            d = json.load(f)
        d["trendfolge"] = s
        with open(pfad, "w") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
