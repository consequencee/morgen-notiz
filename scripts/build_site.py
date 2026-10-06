#!/usr/bin/env python3
"""Baut die Webseite in docs/ aus den Notiz-Fragmenten in notizen/<bericht>/.

- docs/index.html                       -> Übersicht aller Berichte (neueste Ausgabe je Bericht)
- docs/<bericht>/index.html             -> neueste Notiz des Berichts
- docs/<bericht>/archiv/<slug>.html     -> jede Notiz einzeln
- docs/<bericht>/archiv/index.html      -> Archiv des Berichts

Dateinamen: JJJJ-MM-TT.html (geplant) oder JJJJ-MM-TT-HHMM.html (Sonderausgabe).
Nur Standardbibliothek, damit es in jeder Umgebung ohne Installation läuft.
"""

import html
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTIZEN = ROOT / "notizen"
DOCS = ROOT / "docs"
VORLAGE = (ROOT / "vorlage" / "seite.html").read_text(encoding="utf-8")

# Reihenfolge = Reihenfolge auf der Übersichtsseite
BERICHTE = {
    "dax": {"name": "DAX", "marke": "Morgen Notiz · DAX", "plan": "Mo–Fr vor 9:00 Uhr"},
    "us30": {"name": "US30", "marke": "US30 Notiz · Dow Jones", "plan": "Mo–Fr vor 15:00 Uhr"},
}

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
TENDENZEN = {"bullish": "Bullish", "neutral": "Neutral", "bearish": "Bearish"}
KOPF = re.compile(r"^\s*<!--(.*?)-->", re.S)
SLUG = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-(\d{2})(\d{2}))?")


def lies_notiz(pfad):
    treffer = SLUG.fullmatch(pfad.stem)
    if not treffer:
        return None
    text = pfad.read_text(encoding="utf-8")
    meta = {}
    kopf = KOPF.match(text)
    if kopf:
        for zeile in kopf.group(1).splitlines():
            if ":" in zeile:
                schluessel, wert = zeile.split(":", 1)
                meta[schluessel.strip().lower()] = wert.strip()
        text = text[kopf.end():]
    tendenz_roh = meta.get("tendenz", "").split()
    sonder = f"{treffer.group(2)}:{treffer.group(3)}" if treffer.group(2) else ""
    return {
        "datum": date.fromisoformat(treffer.group(1)),
        "sortierung": pfad.stem if sonder else pfad.stem + "-0000",
        "slug": pfad.stem,
        "sonder": sonder,
        "titel": meta.get("titel", "Notiz"),
        "tendenz": TENDENZEN.get(tendenz_roh[0].lower(), "") if tendenz_roh else "",
        "erstellt": meta.get("erstellt", ""),
        "inhalt": text.strip(),
    }


def datum_lang(notiz):
    text = f"{WOCHENTAGE[notiz['datum'].weekday()]}, {notiz['datum'].strftime('%d.%m.%Y')}"
    if notiz["sonder"]:
        text += f" · Sonderausgabe {notiz['sonder']}"
    return text


def kurz(notiz):
    text = notiz["datum"].strftime("%d.%m.")
    return f"{text} {notiz['sonder']}" if notiz["sonder"] else text


def badge(tendenz):
    return f'<span class="badge {tendenz.lower()}">{tendenz}</span>' if tendenz else ""


def seite(*, titel, basis, marke, kopf, inhalt, nav):
    ersetzungen = {
        "{{TITEL}}": html.escape(titel),
        "{{BASIS}}": basis,
        "{{MARKE}}": html.escape(marke),
        "{{KOPF}}": kopf,
        "{{INHALT}}": inhalt,
        "{{NAV}}": nav,
    }
    out = VORLAGE
    for platzhalter, wert in ersetzungen.items():
        out = out.replace(platzhalter, wert)
    return out


def notiz_seite(notiz, bericht, ebene, vorher=None, nachher=None):
    """ebene: 'start' für docs/<bericht>/index.html, 'archiv' für docs/<bericht>/archiv/<slug>.html"""
    info = BERICHTE[bericht]
    basis = "../" if ebene == "start" else "../../"
    zum_bericht = "" if ebene == "start" else "../"
    zum_archiv = "archiv/" if ebene == "start" else "./"
    stand = f'<p class="stand">Stand {html.escape(notiz["erstellt"])} Uhr</p>' if notiz["erstellt"] else ""
    kopf = (
        f'<p class="datum">{datum_lang(notiz)}</p>'
        f'<h1>{html.escape(notiz["titel"])}</h1>'
        f'<div class="meta">{badge(notiz["tendenz"])}{stand}</div>'
    )
    links = []
    if vorher:
        links.append(f'<a href="{zum_archiv}{vorher["slug"]}.html">← {kurz(vorher)}</a>')
    links.append(f'<a href="{zum_archiv}">Archiv</a>')
    if ebene == "archiv":
        links.append(f'<a href="{zum_bericht}">Aktuell</a>')
    links.append(f'<a href="{basis}">Übersicht</a>')
    if nachher:
        links.append(f'<a href="{zum_archiv}{nachher["slug"]}.html">{kurz(nachher)} →</a>')
    return seite(
        titel=f'{info["name"]} Notiz – {kurz(notiz)}{notiz["datum"].year}',
        basis=basis,
        marke=info["marke"],
        kopf=kopf,
        inhalt=notiz["inhalt"],
        nav=" · ".join(links),
    )


def archiv_seite(notizen, bericht):
    info = BERICHTE[bericht]
    if notizen:
        zeilen = "\n".join(
            f'<li><a href="{n["slug"]}.html"><span class="a-datum">{datum_lang(n)}</span>'
            f'<span class="a-titel">{html.escape(n["titel"])}</span></a>{badge(n["tendenz"])}</li>'
            for n in notizen
        )
        inhalt = f'<ul class="archiv-liste">\n{zeilen}\n</ul>'
    else:
        inhalt = "<p>Noch keine Notizen vorhanden.</p>"
    return seite(
        titel=f'{info["name"]} Notiz – Archiv',
        basis="../../",
        marke=info["marke"],
        kopf='<p class="datum">Alle bisherigen Ausgaben</p><h1>Archiv</h1>',
        inhalt=inhalt,
        nav='<a href="../">Aktuell</a> · <a href="../../">Übersicht</a>',
    )


def leere_seite(bericht):
    info = BERICHTE[bericht]
    return seite(
        titel=f'{info["name"]} Notiz',
        basis="../",
        marke=info["marke"],
        kopf='<p class="datum">Noch keine Ausgabe</p><h1>Bald verfügbar</h1>',
        inhalt=f'<p>Die erste Notiz erscheint {info["plan"]}.</p>',
        nav='<a href="../">Übersicht</a>',
    )


def uebersicht(neueste):
    karten = []
    for bericht, info in BERICHTE.items():
        notiz = neueste.get(bericht)
        if notiz:
            stand = f'Stand {html.escape(notiz["erstellt"])} Uhr' if notiz["erstellt"] else datum_lang(notiz)
            inhalt = (
                f'<p class="datum">{datum_lang(notiz)}</p>'
                f'<p class="karte-titel">{html.escape(notiz["titel"])}</p>'
                f'<div class="meta">{badge(notiz["tendenz"])}<p class="stand">{stand}</p></div>'
            )
        else:
            inhalt = '<p class="datum">Noch keine Ausgabe</p>'
        karten.append(
            f'<section class="karte">\n'
            f'  <h2>{html.escape(info["name"])} <span class="plan">{info["plan"]}</span></h2>\n'
            f'  <a class="karte-link" href="{bericht}/">{inhalt}</a>\n'
            f'  <p class="karte-nav"><a href="{bericht}/">Zum Bericht →</a> · <a href="{bericht}/archiv/">Archiv</a></p>\n'
            f'</section>'
        )
    return seite(
        titel="Markt Notizen",
        basis="",
        marke="Markt Notizen",
        kopf='<p class="datum">KI-generierte Marktberichte</p><h1>Übersicht</h1>',
        inhalt="\n".join(karten),
        nav="",
    )


def main():
    neueste = {}
    for bericht in BERICHTE:
        ziel = DOCS / bericht
        archiv = ziel / "archiv"
        if archiv.exists():
            shutil.rmtree(archiv)  # verwaiste Seiten entfernen
        archiv.mkdir(parents=True, exist_ok=True)

        notizen = sorted(
            filter(None, (lies_notiz(p) for p in (NOTIZEN / bericht).glob("*.html"))),
            key=lambda n: n["sortierung"],
            reverse=True,
        )
        for i, notiz in enumerate(notizen):
            nachher = notizen[i - 1] if i > 0 else None
            vorher = notizen[i + 1] if i + 1 < len(notizen) else None
            (archiv / f'{notiz["slug"]}.html').write_text(
                notiz_seite(notiz, bericht, "archiv", vorher, nachher), encoding="utf-8"
            )
        (archiv / "index.html").write_text(archiv_seite(notizen, bericht), encoding="utf-8")

        if notizen:
            neueste[bericht] = notizen[0]
            vorher = notizen[1] if len(notizen) > 1 else None
            start = notiz_seite(notizen[0], bericht, "start", vorher)
        else:
            start = leere_seite(bericht)
        (ziel / "index.html").write_text(start, encoding="utf-8")
        print(f"{bericht}: {len(notizen)} Notiz(en)")

    (DOCS / "index.html").write_text(uebersicht(neueste), encoding="utf-8")
    print(f"Übersicht gebaut -> {DOCS}")


if __name__ == "__main__":
    main()
