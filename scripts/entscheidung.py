#!/usr/bin/env python3
"""Tagesentscheidung der DAX- bzw. US30-Notiz anlegen und bewerten.

  python3 scripts/entscheidung.py anlegen [--bericht dax|us30] --datum JJJJ-MM-TT --richtung long|short|kein --score 1-10 \
      --vola 18.4 --vola-quelle "VDAX-NEW, onvista 08:15" [--indikation 25750] --grund "..." \
      --signale '[{"name": "Vorbörse", "wert": "−0,9 %", "wirkung": "gegen"}, ...]'
  python3 scripts/entscheidung.py bilanz [--bericht dax|us30] [--daten daten/<bericht>/JJJJ-MM-TT.json]

anlegen  rechnet Spanne, Ober- und Untergrenze aus und schreibt entscheidungen/<bericht>/JJJJ-MM-TT.json.
bilanz   bewertet alle offenen Entscheidungen mit den Stundenkerzen aus der neuesten Datei in
         daten/<bericht>/, schreibt das Ergebnis in die Entscheidung und entscheidungen/<bericht>/bilanz.json.

Regeln (fest, damit die Bilanz vergleichbar bleibt):
  Handel von der Eröffnung bis zum Schluss der Heimatbörse (DAX: Xetra 9:00–17:30, Dow: NYSE 9:30–16:00 New York).
  Erwartete Tagesbewegung σ = Referenz × Vola / 100 / √252 (Referenz = Indikation, sonst letzter Schluss).
  Grenze auf der Gewinnseite (Ziel) = Eröffnung ± ZIEL_SIGMA × σ, Grenze auf der Verlustseite (Stopp, Idee widerlegt)
  = Eröffnung ∓ STOPP_SIGMA × σ. Bei Long ist das Ziel die Obergrenze, bei Short die Untergrenze.
Nur Standardbibliothek.
"""

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# index = Schlüssel der Tageskerzen in daten/…/maerkte, letzte = Beginn der letzten Stundenkerze (Börsenzeit)
BERICHTE = {
    "dax": {"index": "dax", "name": "DAX", "letzte": "17:00", "fenster": "Xetra 9:00–17:30"},
    "us30": {"index": "dow", "name": "Dow", "letzte": "15:30", "fenster": "NYSE 9:30–16:00 New York"},
}
BERICHT = "dax"
ORDNER = ROOT / "entscheidungen" / "dax"
DATEN = ROOT / "daten" / "dax"
ZIEL_SIGMA = 0.75   # etwas weniger als die eingepreiste Tagesbewegung
STOPP_SIGMA = 0.6
WIRKUNGEN = {"rueckenwind", "gegenwind", "neutral"}
AUSGANG = {"Ziel": "Gewinnmitnahme-Grenze erreicht", "Stopp": "Idee widerlegt (Grenze auf der Verlustseite erreicht)", "Schluss": "keine Grenze erreicht, Ausstieg zum Schluss"}


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
    ind = (daten.get("indikation") or {}).get("wert")
    indikation = a.indikation or ind  # ohne Angabe: Indikation aus den Marktdaten
    referenz = indikation or schluss
    if not (vola and referenz):
        sys.exit("Für die Spanne fehlen Vola oder Referenzkurs.")
    sigma = referenz * vola / 100 / math.sqrt(252)
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
        "referenz_art": "Indikation" if indikation else "Vortagesschluss",
        "vortag": {"schluss": schluss, "hoch": k.get("hoch"), "tief": k.get("tief"), "tag": k.get("letzter_handelstag")},
        "sigma_punkte": round(sigma),
        "spanne": [round(referenz - sigma), round(referenz + sigma)],
        "ziel_punkte": round(ZIEL_SIGMA * sigma) if vorz else None,
        "stopp_punkte": round(STOPP_SIGMA * sigma) if vorz else None,
        "ziel_ca": round(referenz + vorz * ZIEL_SIGMA * sigma) if vorz else None,
        "stopp_ca": round(referenz - vorz * STOPP_SIGMA * sigma) if vorz else None,
        "ergebnis": None,
    }
    ziel = Path(a.ausgabe) if a.ausgabe else ORDNER / f"{datum}.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Entscheidung gespeichert: {ziel}")
    print(f"Richtung {richtung.upper()}" + (f", Überzeugung {a.score}/10" if vorz else ""))
    print(f"Vola {de(vola, 1)} % ({vola_quelle}) → erwartete Tagesbewegung ±{de(sigma)} Punkte (ca. 68 %)")
    print(f"Erwartete Spanne um {e['referenz_art']} {de(referenz)}: {de(e['spanne'][0])} – {de(e['spanne'][1])}")
    if vorz:
        gewinn = f"Eröffnung {'+' if vorz > 0 else '−'}{de(e['ziel_punkte'])} Punkte (bei Eröffnung = Referenz ca. {de(e['ziel_ca'])}) – Gewinnmitnahme"
        verlust = f"Eröffnung {'−' if vorz > 0 else '+'}{de(e['stopp_punkte'])} Punkte (ca. {de(e['stopp_ca'])}) – Idee widerlegt"
        ober, unter = (gewinn, verlust) if vorz > 0 else (verlust, gewinn)
        print(f"Obergrenze: {ober}")
        print(f"Untergrenze: {unter}")


def bewerte(e, kerzen, tage):
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
    ziel = eroeffnung + vorz * e["ziel_punkte"]
    stopp = eroeffnung - vorz * e["stopp_punkte"]
    ausgang, punkte = "Schluss", vorz * (schluss - eroeffnung)
    for c in tag:  # Stundenkerzen der Reihe nach; trifft eine Kerze beides, zählt vorsichtshalber der Stopp
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


def bilanz(a):
    daten = lies_daten(a.daten)
    kerzen = daten.get("index_stunden") or []
    tage = {c["tag"]: c for c in (daten.get("maerkte", {}).get(BERICHTE[BERICHT]["index"], {}).get("kerzen") or [])}
    alle = []
    for p in sorted(ORDNER.glob("20*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if e.get("ergebnis") is None:
            r = bewerte(e, kerzen, tage)
            if r is None and kerzen and kerzen[0]["tag"] <= e["datum"] < kerzen[-1]["tag"] and not any(c["tag"] == e["datum"] for c in kerzen):
                r = {"ausgang": "kein Handel (Börse geschlossen)", "punkte": 0, "richtig": None}
            if r:
                e["ergebnis"] = r
                p.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
        alle.append(e)

    fertig = [e for e in alle if e.get("ergebnis") and e["richtung"] != "kein" and e["ergebnis"].get("richtig") is not None]
    def kennzahlen(liste):
        n = len(liste)
        if not n:
            return {"trades": 0}
        return {
            "trades": n,
            "richtung_richtig_pct": round(100 * sum(e["ergebnis"]["richtig"] for e in liste) / n),
            "ziel_pct": round(100 * sum(e["ergebnis"]["ausgang"] == "Ziel" for e in liste) / n),
            "stopp_pct": round(100 * sum(e["ergebnis"]["ausgang"] == "Stopp" for e in liste) / n),
            "punkte_summe": sum(e["ergebnis"]["punkte"] for e in liste),
            "punkte_schnitt": round(sum(e["ergebnis"]["punkte"] for e in liste) / n),
        }
    stufen = {"1–3": (1, 3), "4–6": (4, 6), "7–10": (7, 10)}
    mit_spanne = [e for e in alle if (e.get("ergebnis") or {}).get("in_spanne") is not None]
    spanne = {"tage": len(mit_spanne),
              "treffer_pct": round(100 * sum(e["ergebnis"]["in_spanne"] for e in mit_spanne) / len(mit_spanne)) if mit_spanne else None,
              "soll_pct": 68}
    zusammen = {
        "stand": daten.get("datum"),
        "regeln": f"{BERICHTE[BERICHT]['fenster']}; Ziel {ZIEL_SIGMA} σ, Stopp {STOPP_SIGMA} σ; Kerze mit beidem zählt als Stopp",
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
        print(f"Bilanz {e['datum']}: kein Trade. {BERICHTE[BERICHT]['name']} von Eröffnung {de(r['eroeffnung'])} bis Schluss {de(r['schluss'])}: {r['bewegung_punkte']:+d} Punkte.")
    else:
        print(f"Bilanz {e['datum']}: {e['richtung'].upper()} (Überzeugung {e['score']}/10) – "
              f"{'Richtung richtig' if r['richtig'] else 'Richtung falsch'}, {AUSGANG.get(r['ausgang'], r['ausgang'])}, {r['punkte']:+d} Punkte "
              f"(Eröffnung {de(r['eroeffnung'])}, Schluss {de(r['schluss'])}, Hoch {de(r['hoch'])}, Tief {de(r['tief'])}).")
    if "in_spanne" in r:
        print(f"Spanne ±{de(e['sigma_punkte'])} um die Eröffnung: {'getroffen' if r['in_spanne'] else 'verfehlt'} "
              f"(Bewegung {r['bewegung_punkte']:+d}); bisher {spanne['treffer_pct']} % von {spanne['tage']} Tagen getroffen (Soll ca. 68 %).")
    g = zusammen["gesamt"]
    if g["trades"]:
        print(f"Gesamt seit Start: {g['trades']} Trade{'s' if g['trades'] != 1 else ''}, Richtung richtig {g['richtung_richtig_pct']} %, Gewinnmitnahme erreicht {g['ziel_pct']} %, "
              f"Idee widerlegt {g['stopp_pct']} %, Summe {g['punkte_summe']:+d} Punkte (Schnitt {g['punkte_schnitt']:+d}).")


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
