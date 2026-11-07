#!/usr/bin/env python3
"""Tagesentscheidung der DAX- bzw. US30-Notiz anlegen und bewerten.

  python3 scripts/entscheidung.py anlegen [--bericht dax|us30] --datum JJJJ-MM-TT --richtung long|short|kein --score 1-10 \
      --vola 18.4 --vola-quelle "VDAX-NEW, onvista 08:15" [--indikation 25750] --grund "..." \
      --signale '[{"name": "Vorbörse", "wert": "−0,9 %", "wirkung": "gegen"}, ...]'
  python3 scripts/entscheidung.py bilanz [--bericht dax|us30] [--daten daten/<bericht>/JJJJ-MM-TT.json]

anlegen  rechnet die erwartete Range aus und schreibt entscheidungen/<bericht>/JJJJ-MM-TT.json.
bilanz   bewertet alle offenen Entscheidungen mit den Stundenkerzen aus der neuesten Datei in
         daten/<bericht>/, schreibt das Ergebnis in die Entscheidung und entscheidungen/<bericht>/bilanz.json.

Regeln (fest, damit die Bilanz vergleichbar bleibt):
  Handel von der Eröffnung bis zum Schluss der Heimatbörse (DAX: Xetra 9:00–17:30, Dow: NYSE 9:30–16:00 New York).
  Erwartete Tagesbewegung σ = Referenz × Vola / 100 / √252 (Referenz = Indikation, sonst letzter Schluss).
  Bewertet wird nur: Stimmte die Richtung (Kurs zur Notiz → Schluss)? Lag der Schluss in der erwarteten Range?
  Keine Kauf-/Verkaufsmarken (seit 07.11.2026). Ältere Einträge mit Marken werden unverändert weiter gelesen.
Nur Standardbibliothek.
"""

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
# index = Schlüssel der Tageskerzen in daten/…/maerkte, letzte = Beginn der letzten Stundenkerze (Börsenzeit)
BERICHTE = {
    "dax": {"index": "dax", "name": "DAX", "letzte": "17:00", "fenster": "Xetra bis 17:30", "tz": "Europe/Berlin", "von": (9, 0), "bis": (17, 30)},
    "us30": {"index": "dow", "name": "Dow", "letzte": "15:30", "fenster": "NYSE bis 16:00 New York", "tz": "America/New_York", "von": (9, 30), "bis": (16, 0)},
}
BERICHT = "dax"
ORDNER = ROOT / "entscheidungen" / "dax"
DATEN = ROOT / "daten" / "dax"
WIRKUNGEN = {"rueckenwind", "gegenwind", "neutral"}


def lies_daten(pfad=None):
    if pfad:
        return json.loads(Path(pfad).read_text(encoding="utf-8"))
    dateien = sorted(DATEN.glob("*.json"))
    if not dateien:
        sys.exit("Keine Marktdaten gefunden – zuerst node scripts/marktdaten.mjs ausführen.")
    return json.loads(dateien[-1].read_text(encoding="utf-8"))


def de(v, dp=0):
    if v is None:
        return "n/v"
    return f"{v:,.{dp}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def anlegen(a):
    datum = date.fromisoformat(a.datum).isoformat()
    richtung = a.richtung.lower()
    if richtung not in {"long", "short", "kein"}:
        sys.exit("--richtung muss long, short oder kein sein")
    if richtung != "kein" and not 1 <= a.score <= 10:
        sys.exit("--score muss zwischen 1 und 10 liegen")
    signale = json.loads(a.signale) if a.signale else []
    for s in signale:
        s["wirkung"] = s.get("wirkung", "neutral").lower().replace("ü", "ue")
        if s["wirkung"] not in WIRKUNGEN:
            sys.exit(f"Signal {s.get('name')}: wirkung muss rueckenwind, gegenwind oder neutral sein")

    daten = lies_daten(DATEN / f"{datum}.json" if (DATEN / f"{datum}.json").exists() else None)
    k = daten.get("index_kennzahlen") or {}
    schluss = k.get("schluss")
    vola, vola_quelle = a.vola, a.vola_quelle
    vi = daten.get("vola") or {}
    if vola is None and vi.get("wert"):
        vola, vola_quelle = vi["wert"], f"{vi.get('name', '')} {vi.get('zeit', '')}, {vi.get('quelle', '')}".strip()
    if vola is None:
        vola = k.get("realisierte_vola_20t_pct")
        vola_quelle = "Ersatz: realisierte Schwankung der letzten 20 Tage (kein Volatilitätsindex gefunden)"
    # Einstieg = Kurs zum Zeitpunkt der Notiz (die Notiz entsteht nach der Eröffnung); sonst Indikation, sonst Schluss
    ein = daten.get("einstieg") or {}
    ind = (daten.get("indikation") or {}).get("wert")
    indikation = a.indikation or ind
    if a.einstieg or ein.get("kurs"):
        referenz, referenz_art = a.einstieg or ein["kurs"], "Kurs zur Notiz"
        ein_zeit = datetime.now(timezone.utc) if a.einstieg else datetime.fromisoformat(ein["zeit"].replace("Z", "+00:00"))
    else:
        referenz, referenz_art, ein_zeit = indikation or schluss, "Indikation" if indikation else "Vortagesschluss", None
    if not (vola and referenz):
        sys.exit("Für die Spanne fehlen Vola oder Referenzkurs.")
    # Range nur für die restliche Handelszeit: σ × √(Rest der Sitzung / ganze Sitzung)
    cfg = BERICHTE[BERICHT]
    tz = ZoneInfo(cfg["tz"])
    d = date.fromisoformat(datum)
    start = datetime(d.year, d.month, d.day, *cfg["von"], tzinfo=tz)
    ende = datetime(d.year, d.month, d.day, *cfg["bis"], tzinfo=tz)
    rest = 1.0
    if ein_zeit:
        rest = min(1.0, max(0.05, (ende - max(ein_zeit, start)).total_seconds() / (ende - start).total_seconds()))
    sigma = referenz * vola / 100 / math.sqrt(252) * math.sqrt(rest)
    vorz = {"long": 1, "short": -1, "kein": 0}[richtung]
    e = {
        "bericht": BERICHT,
        "datum": datum,
        "richtung": richtung,
        "score": a.score if richtung != "kein" else None,
        "grund": a.grund,
        "signale": signale,
        "vola_pct": round(vola, 2),
        "vola_quelle": vola_quelle,
        "referenz": round(referenz, 2),
        "referenz_art": referenz_art,
        "einstieg": {"kurs": round(referenz, 2), "zeit": int(ein_zeit.timestamp()), "zeit_iso": ein_zeit.isoformat(), "quelle": ein.get("quelle", "manuell")} if ein_zeit else None,
        "restzeit_anteil": round(rest, 3),
        "vortag": {"schluss": schluss, "hoch": k.get("hoch"), "tief": k.get("tief"), "tag": k.get("letzter_handelstag")},
        "sigma_punkte": round(sigma),
        "spanne": [round(referenz - sigma), round(referenz + sigma)],
        "ergebnis": None,
    }
    ziel = Path(a.ausgabe) if a.ausgabe else ORDNER / f"{datum}.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Entscheidung gespeichert: {ziel}")
    print(f"Richtung {richtung.upper()}" + (f", Überzeugung {a.score}/10" if vorz else ""))
    print(f"Vola {de(vola, 1)} % ({vola_quelle}) → erwartete Bewegung bis Schluss ±{de(sigma)} Punkte (ca. 68 %, {round(rest * 100)} % der Handelszeit übrig)")
    zeit = datetime.fromtimestamp(e["einstieg"]["zeit"], ZoneInfo(BERICHTE[BERICHT]["tz"] if BERICHT == "dax" else "Europe/Berlin")).strftime("%H:%M") if e.get("einstieg") else ""
    print(f"Kurs zur Notiz{' (' + zeit + ' Uhr)' if zeit else ''}: {de(referenz)}")
    print(f"Erwartete Range bis Schluss: {de(e['spanne'][0])} – {de(e['spanne'][1])}")


def bewerte(e, kerzen, tage, fein=None):
    if e.get("einstieg") and fein:
        return bewerte_ab_einstieg(e, fein, tage)
    tag = [c for c in kerzen if c["tag"] == e["datum"]]
    if not tag or tag[-1]["zeit"] < BERICHTE[BERICHT]["letzte"]:
        return None  # Tag noch nicht vorbei oder keine Daten
    offiziell = tage.get(e["datum"], {})  # Tageskerze: Eröffnung und Schluss aus den Auktionen
    eroeffnung, schluss = offiziell.get("o") or tag[0]["o"], offiziell.get("c") or tag[-1]["c"]
    bewegung = round(schluss - eroeffnung)
    r = {"eroeffnung": eroeffnung, "schluss": schluss, "bewegung_punkte": bewegung,
         "hoch": max(c["h"] for c in tag), "tief": min(c["l"] for c in tag),
         # Trifft die Spanne? Schluss innerhalb ±1 σ um die Eröffnung (Ziel: etwa 68 % der Tage)
         "in_spanne": abs(schluss - eroeffnung) <= e["sigma_punkte"]}
    if e["richtung"] == "kein":
        r.update(ausgang="kein Trade", punkte=0, richtig=None)
        return r
    vorz = 1 if e["richtung"] == "long" else -1
    ausgang, punkte = "Schluss", vorz * (schluss - eroeffnung)
    ziel = eroeffnung + vorz * (e.get("ziel_punkte") or 1e9)
    stopp = eroeffnung - vorz * (e.get("stopp_punkte") or 1e9)
    for c in (tag if e.get("ziel_punkte") else []):  # Stundenkerzen der Reihe nach; trifft eine Kerze beides, zählt vorsichtshalber der Stopp
        stopp_hit = c["l"] <= stopp if vorz > 0 else c["h"] >= stopp
        ziel_hit = c["h"] >= ziel if vorz > 0 else c["l"] <= ziel
        if stopp_hit:
            ausgang, punkte = "Stopp", -e["stopp_punkte"]
            break
        if ziel_hit:
            ausgang, punkte = "Ziel", e["ziel_punkte"]
            break
    r.update(ausgang=ausgang, punkte=round(punkte), richtig=vorz * (schluss - eroeffnung) > 0,
             punkte_ohne_marken=round(vorz * (schluss - eroeffnung)))
    return r


def bewerte_ab_einstieg(e, fein, tage):
    """Bewertung ab dem Kurs zur Zeit der Notiz bis zum Schluss (5-Minuten-Kerzen ab dieser Zeit)."""
    ein = e["einstieg"]
    tag = [c for c in fein if c["tag"] == e["datum"]]
    if not tag or tag[-1]["zeit"] < ("17:25" if BERICHT == "dax" else "15:55"):
        return None
    danach = [c for c in tag if c["t"] >= ein["zeit"] - 300]
    schluss = tage.get(e["datum"], {}).get("c") or tag[-1]["c"]
    kurs = ein["kurs"]
    r = {"einstieg": kurs, "schluss": schluss, "bewegung_punkte": round(schluss - kurs),
         "eroeffnung": tage.get(e["datum"], {}).get("o") or tag[0]["o"],
         "hoch": max(c["h"] for c in danach), "tief": min(c["l"] for c in danach),
         "in_spanne": abs(schluss - kurs) <= e["sigma_punkte"]}
    if e["richtung"] == "kein":
        r.update(ausgang="kein Trade", punkte=0, richtig=None)
        return r
    vorz = 1 if e["richtung"] == "long" else -1
    ausgang, punkte = "Schluss", vorz * (schluss - kurs)
    ziel, stopp = kurs + vorz * (e.get("ziel_punkte") or 1e9), kurs - vorz * (e.get("stopp_punkte") or 1e9)
    for c in (danach if e.get("ziel_punkte") else []):
        if (c["l"] <= stopp) if vorz > 0 else (c["h"] >= stopp):
            ausgang, punkte = "Stopp", -e["stopp_punkte"]
            break
        if (c["h"] >= ziel) if vorz > 0 else (c["l"] <= ziel):
            ausgang, punkte = "Ziel", e["ziel_punkte"]
            break
    r.update(ausgang=ausgang, punkte=round(punkte), richtig=vorz * (schluss - kurs) > 0, punkte_ohne_marken=round(vorz * (schluss - kurs)))
    return r


def bilanz(a):
    daten = lies_daten(a.daten)
    kerzen = daten.get("index_stunden") or []
    fein = daten.get("index_5min") or []
    tage = {c["tag"]: c for c in (daten.get("maerkte", {}).get(BERICHTE[BERICHT]["index"], {}).get("kerzen") or [])}
    alle = []
    for p in sorted(ORDNER.glob("20*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if e.get("ergebnis") is None:
            r = bewerte(e, kerzen, tage, fein)
            if r is None and kerzen and kerzen[0]["tag"] <= e["datum"] < kerzen[-1]["tag"] and not any(c["tag"] == e["datum"] for c in kerzen):
                r = {"ausgang": "kein Handel (Börse geschlossen)", "punkte": 0, "richtig": None}
            if r:
                e["ergebnis"] = r
                p.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
        alle.append(e)

    fertig = [e for e in alle if e.get("ergebnis") and e["richtung"] != "kein" and e["ergebnis"].get("richtig") is not None]
    def bis_schluss(e):  # Punkte vom Kurs zur Notiz bis Schluss, in Richtung der Einschätzung
        r = e["ergebnis"]
        return r.get("punkte_ohne_marken", r.get("punkte", 0))

    def kennzahlen(liste):
        n = len(liste)
        if not n:
            return {"trades": 0}
        return {
            "trades": n,
            "richtung_richtig_pct": round(100 * sum(e["ergebnis"]["richtig"] for e in liste) / n),
            "punkte_summe": sum(bis_schluss(e) for e in liste),
            "punkte_schnitt": round(sum(bis_schluss(e) for e in liste) / n),
        }
    stufen = {"1–3": (1, 3), "4–6": (4, 6), "7–10": (7, 10)}
    mit_spanne = [e for e in alle if (e.get("ergebnis") or {}).get("in_spanne") is not None]
    spanne = {"tage": len(mit_spanne),
              "treffer_pct": round(100 * sum(e["ergebnis"]["in_spanne"] for e in mit_spanne) / len(mit_spanne)) if mit_spanne else None,
              "soll_pct": 68}
    zusammen = {
        "stand": daten.get("datum"),
        "regeln": f"{BERICHTE[BERICHT]['fenster']}; Richtung vom Kurs zur Notiz bis Schluss; Range ±1 σ",
        "gesamt": kennzahlen(fertig),
        "nach_score": {s: kennzahlen([e for e in fertig if lo <= e["score"] <= hi]) for s, (lo, hi) in stufen.items()},
        "spanne": spanne,
        "kein_trade_tage": sum(1 for e in alle if e["richtung"] == "kein" and e.get("ergebnis")),
        "letzte": [{"datum": e["datum"], "richtung": e["richtung"], "score": e["score"], **(e["ergebnis"] or {})} for e in alle[-20:]],
    }
    ORDNER.mkdir(parents=True, exist_ok=True)
    (ORDNER / "bilanz.json").write_text(json.dumps(zusammen, ensure_ascii=False, indent=1), encoding="utf-8")

    bewertet = [e for e in alle if e.get("ergebnis")]
    if not bewertet:
        print("Bilanz: noch keine bewertete Entscheidung (erste Ausgabe im neuen Format).")
        return
    e = bewertet[-1]
    r = e["ergebnis"]
    if "eroeffnung" not in r:
        print(f"Bilanz {e['datum']}: {r['ausgang']}.")
    elif e["richtung"] == "kein":
        print(f"Bilanz {e['datum']}: keine Richtung. {BERICHTE[BERICHT]['name']} von Eröffnung {de(r['eroeffnung'])} bis Schluss {de(r['schluss'])}: {r['bewegung_punkte']:+d} Punkte.")
    else:
        bs = r.get("punkte_ohne_marken", r.get("punkte", 0))
        print(f"Bilanz {e['datum']}: {e['richtung'].upper()} (Überzeugung {e['score']}/10) – "
              f"{'Richtung richtig' if r['richtig'] else 'Richtung falsch'}, {bs:+d} Punkte in Richtung der Einschätzung "
              f"({'Kurs zur Notiz ' + de(r['einstieg']) if 'einstieg' in r else 'Eröffnung ' + de(r['eroeffnung'])}, Schluss {de(r['schluss'])}, Hoch {de(r['hoch'])}, Tief {de(r['tief'])}).")
    if "in_spanne" in r:
        print(f"Range ±{de(e['sigma_punkte'])} um {'den Kurs zur Notiz' if 'einstieg' in r else 'die Eröffnung'}: {'getroffen' if r['in_spanne'] else 'verfehlt'} "
              f"(Bewegung {r['bewegung_punkte']:+d}); bisher {spanne['treffer_pct']} % von {spanne['tage']} Tagen getroffen (Soll ca. 68 %).")
    g = zusammen["gesamt"]
    if g["trades"]:
        print(f"Gesamt seit Start: {g['trades']} Einschätzung{'en' if g['trades'] != 1 else ''}, Richtung richtig {g['richtung_richtig_pct']} %, "
              f"Summe {g['punkte_summe']:+d} Punkte bis Schluss (Schnitt {g['punkte_schnitt']:+d}).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="befehl", required=True)
    an = sub.add_parser("anlegen")
    an.add_argument("--bericht", default="dax", choices=list(BERICHTE))
    an.add_argument("--datum", required=True)
    an.add_argument("--richtung", required=True)
    an.add_argument("--score", type=int, default=0)
    an.add_argument("--vola", type=float)
    an.add_argument("--vola-quelle", default="")
    an.add_argument("--indikation", type=float)
    an.add_argument("--einstieg", type=float, help="Kurs zur Notiz, nur wenn die Daten keinen haben")
    an.add_argument("--grund", default="")
    an.add_argument("--signale", default="")
    an.add_argument("--ausgabe", help="andere Zieldatei (Sonderausgabe: zählt nicht in der Bilanz)")
    bi = sub.add_parser("bilanz")
    bi.add_argument("--bericht", default="dax", choices=list(BERICHTE))
    bi.add_argument("--daten")
    a = ap.parse_args()
    global BERICHT, ORDNER, DATEN
    BERICHT = a.bericht
    ORDNER = ROOT / "entscheidungen" / BERICHT
    DATEN = ROOT / "daten" / BERICHT
    anlegen(a) if a.befehl == "anlegen" else bilanz(a)


if __name__ == "__main__":
    main()
