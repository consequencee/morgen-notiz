# Bericht: dax – Morgen Notiz DAX

Geplanter Lauf: Mo–Fr **nach der Xetra-Eröffnung**: Start kurz nach 9:00 Uhr, fertig etwa 9:20 Uhr. Die Notiz kennt also schon die Eröffnung und die ersten Minuten.
Diese Datei hat einen **eigenen Ablauf und Aufbau**. Sie ersetzt die Abschnitte 2 und 3 der ANLEITUNG (Recherche, Notiz schreiben); Abschnitt 1 (Datum, Modus), 4 (Webseite) und 5 (E-Mail) der ANLEITUNG gelten weiter, mit den Ergänzungen unten.

Zweck: **Trading zuerst.** Ganz oben steht eine Tagesentscheidung für den DAX-Index **vom Einstieg (Kurs zum Zeitpunkt der Notiz) bis zum Xetra-Schluss (17:30)**, darunter die Begründung und der Marktüberblick. Kompakt, in etwa 2 Minuten lesbar.

## A. Daten holen (vor jeder Recherche)

```bash
node scripts/marktdaten.mjs              # alle Zahlen, schreibt daten/dax/JJJJ-MM-TT.json
python3 scripts/entscheidung.py bilanz   # bewertet die Entscheidungen der Vortage
python3 scripts/trendfolge.py           # großer Trend (3-Monats-Momentum, täglich), Block "trendfolge"
```

- **Alle Zahlen** für Marktlage, Anleihen & Zinsen, Kalender, Positionierung und US-Datenüberraschungen kommen aus der Ausgabe von `marktdaten.mjs`. Gib Zahlen mit der Genauigkeit der Quelle an, keine Spannen „ca. X–Y“, wenn die Daten einen Wert liefern.
- Steht dort `n/v` oder ein Fehler, darfst du den Wert per Websuche ergänzen (Quelle nennen), sonst `n/v`.
- **Ersatzquellen in den Daten:** CNBC (Bund- und US-Live-Kurve) blockt Anfragen aus Rechenzentren. Fehlt die Bund-Kurve, nimm „Bund laut Bundesbank“ (Vortagesschluss); fehlt die US-Live-Kurve, nimm „US-Treasury 10J (Yahoo)“ aus den Märkten bzw. die offizielle Treasury-Kurve vom Vortag. FRED (Kreditaufschläge) blockt ebenfalls oft; fehlt `kredit`, beurteile Kreditstress über die Veränderung der Anleihe-ETFs HYG (Hochzins) und LQD (Investment Grade) aus den Märkten. Nenne jeweils die Quelle.
- Schlägt das Skript ganz fehl (z. B. kein `node` oder gesperrte Domains), gib den Fehler in der Abschlusszeile aus und hole die Zahlen wie früher per Websuche. Die Notiz erscheint trotzdem.
- Achte auf den **Handelstag** jeder Zeile: China und Japan sind um 8:30 Uhr meist schon geschlossen (dann ist „Stand“ der Schluss von heute), die US-Werte sind der Schluss von gestern, die US-Futures laufen.

## B. Recherche (WebSearch / WebFetch) – nur, was die Daten nicht liefern

1. **Spanne:** kommt automatisch aus den Daten, bevorzugt aus der **DAX-Tagesoption (Eurex ODAP)**, die heute zur Xetra-Schlussauktion verfällt (Abschnitt „Tagesoption“ der Datenausgabe). Fehlt sie, nimmt `entscheidung.py` den **VDAX** (onvista), danach die realisierte Schwankung, und sagt das. Nichts davon per Websuche ersetzen.
2. **Einstieg und Eröffnung:** kommen aus den Daten (Abschnitt „Einstieg (jetzt)“): aktueller DAX-Stand (Median der Echtzeit-Indikationen L&S, J.P. Morgan, UBS über onvista, mit Uhrzeit), Eröffnung heute, Lücke zum Vortagesschluss, Bewegung seit Eröffnung. Nur wenn der Einstieg fehlt, den aktuellen Stand per Websuche mit Uhrzeit ergänzen und als `--einstieg` übergeben.
3. **Nachrichten zu DAX-Unternehmen** seit gestern Abend: Zahlen, Ad-hoc-Meldungen, Prognosen, Übernahmen, Managementwechsel, Analysten. Besonders die Schwergewichte (SAP, Siemens, Allianz, Deutsche Telekom, Airbus, Rheinmetall, Siemens Energy, Münchener Rück, Deutsche Bank, Mercedes-Benz).
4. **Grund der China-Sitzung** (1 Satz) und **Konjunkturdaten von heute früh** (Destatis 8:00 Uhr), falls im Kalender noch kein Ist-Wert steht.
5. **Profi-Sicht:** Öffne die neuesten Artikel von ING THINK aus der Datenausgabe (FX Daily, Rates Spark, The Commodities Feed, Analysen zu EZB/Fed/Deutschland) und fasse ihre Einschätzung in 1–2 Sätzen zusammen. ING schreibt zu Zinsen, Devisen und Rohstoffen, nicht zu Aktien.

Es gelten die Regeln der ANLEITUNG: nichts erfinden, Quellen nennen, eigene Einschätzungen kennzeichnen.

## C. Signale bewerten

Bewerte **jedes** Signal dieser Liste mit Wert, Wirkung auf den DAX heute (`rueckenwind`, `gegenwind`, `neutral`) und einer kurzen Begründung:

| # | Signal | Woraus |
|---|---|---|
| 1 | Vorgaben USA | S&P 500 / Nasdaq 100 Schluss gestern, US-Futures jetzt |
| 2 | Eröffnung & erste Minuten | Lücke zum Vortagesschluss, Bewegung seit Eröffnung, Hoch/Tief bisher |
| 3 | Asien & China | Nikkei, Shanghai, CSI 300, Hang Seng |
| 4 | Datenüberraschungen | Ist gegen Prognose: US-Daten gestern Nachmittag, deutsche/europäische Daten heute früh |
| 5 | Zinserwartung | Fed-Pfad (Wahrscheinlichkeit der nächsten Zinsänderung), EZB |
| 6 | Renditen | Bund 10J und US 10J, Veränderung zum Vortag |
| 7 | Kreditstress | Risikoaufschläge Euro- und US-Hochzins, Veränderung 1 Woche |
| 8 | Öl & Dollar | Brent, EUR/USD |
| 9 | Trend | DAX gegen 21-, 50- und 200-Tage-Schnitt; dazu der große Trend aus `trendfolge.py` (Bull/Bear, täglich aus dem letzten Schluss; Rückenwind, wenn er zur Richtung passt, sonst Gegenwind) |
| 10 | Positionierung | CFTC COT (wöchentlich): Extreme oder deutliche Veränderungen bei S&P-Future, Euro, Treasuries |
| 11 | Unternehmensnachrichten | Schwergewichte mit eigenen Nachrichten |
| 12 | Profi-Sicht | ING THINK |
| 13 | Termine bis 17:30 | Ereignisrisiko (EZB, US-Arbeitsmarkt, US-Inflation …) |

## D. Tagesentscheidung treffen

- **Richtung:** `long` oder `short` nach dem Saldo der Signale, gewichtet nach ihrer Bedeutung für **heute**. Sei mutig: Es gibt keine Tendenz „neutral“; ist das Bild knapp, entscheide trotzdem und gib einen niedrigen Score.
- **Kein Trade** (`kein`) nur, wenn **beides** zutrifft: Im Fenster bis 17:30 liegt ein großer Termin (EZB-Zinsentscheid, US-Arbeitsmarktbericht, US-Verbraucherpreise oder ein vergleichbares Ereignis) **und** die Signale widersprechen sich. Außerdem `kein`, wenn Xetra geschlossen ist.
- **Überzeugung 1–10:**
  - 1–2: Saldo knapp, Signale widersprüchlich
  - 3–4: leichtes Übergewicht in eine Richtung
  - 5–6: klares Übergewicht, mindestens drei gewichtige Signale gleichgerichtet, keine starke Gegenkraft
  - 7–8: starkes Übergewicht plus konkreter Katalysator (z. B. deutliche Vorbörse in Richtung, klare Datenüberraschung)
  - 9–10: nur in außergewöhnlicher Lage, fast alle Signale gleichgerichtet
- Entscheidung speichern und Marken berechnen lassen (geplanter Modus):

```bash
python3 scripts/entscheidung.py anlegen --datum JJJJ-MM-TT --richtung long|short|kein --score N \
  [--einstieg <nur wenn die Daten keinen Einstieg haben>] \
  --grund "<1 Satz>" --signale '<JSON-Liste: [{"name": "...", "wert": "...", "wirkung": "rueckenwind|gegenwind|neutral", "grund": "..."}]>'
python3 scripts/chart.py --datum JJJJ-MM-TT
```

  Die Ausgabe nennt **erwartete Range** (±1 σ für die restliche Handelszeit), **Obergrenze** und **Untergrenze**, alle ab dem **Einstieg**. Die Grenze auf der Gewinnseite liegt 0,75 σ in Handelsrichtung (Gewinnmitnahme), die auf der Verlustseite 0,6 σ dagegen (Idee widerlegt). Bei Long ist die Obergrenze die Gewinnseite, bei Short die Untergrenze. Übernimm die Zahlen unverändert.
- **Manueller Modus (Sonderausgabe):** Die Entscheidung zählt nicht in der Bilanz. Nutze `--ausgabe /tmp/entscheidung-sonder.json` beim Anlegen und `python3 scripts/chart.py --datum JJJJ-MM-TT --entscheidung /tmp/entscheidung-sonder.json --name JJJJ-MM-TT-HHMM`.

## E. Aufbau der Notiz (HTML-Fragment)

Kopf wie in der ANLEITUNG; `tendenz:` ist **Bullish** bei long, **Bearish** bei short, **Neutral** bei kein Trade. Der `titel` ist die Kernaussage des Tages (z. B. „Short: Apple-Schock und Iran-Angriff überwiegen“).

Danach genau diese Abschnitte, nur diese Tags und Klassen, keine Inline-Styles (das `data-src`-Attribut beim beweglichen Chart ist erlaubt):

```html
<section class="entscheidung">
  <h2>Tagesentscheidung ab HH:MM bis 17:30 Uhr</h2>   <!-- HH:MM = Uhrzeit des Einstiegs -->
  <div class="entscheid-kopf">
    <span class="richtung gross short">Short</span>   <!-- Klassen: long | short | kein; Text: Long | Short | Kein Trade -->
    <span class="score">6/10 <small>Überzeugung</small></span>
  </div>
  <p>2–3 Sätze: welche Signale den Ausschlag geben und welches das wichtigste Gegenargument ist.</p>
  <dl class="marken">
    <div><dt>Einstieg (HH:MM)</dt><dd>25.906</dd></div>
    <div><dt>Erwartete Range</dt><dd>25.590 – 26.222</dd></div>
    <div class="stopp"><dt>Obergrenze · Idee widerlegt</dt><dd>26.096 (+190)</dd></div>
    <div class="ziel"><dt>Untergrenze · Gewinnmitnahme</dt><dd>25.668 (−238)</dd></div>
    <!-- Reihenfolge immer Obergrenze vor Untergrenze; Klasse ziel (grün) für die Gewinnseite, stopp (rot) für die Verlustseite -->
    <div><dt>Eingepreist (Tagesoption)</dt><dd>±1,04 %</dd></div>   <!-- Quelle laut Ausgabe; bei Ersatz „VDAX 19,5 %“ -->
  </dl>
  <p class="risiko">Einstieg zum Kurs um HH:MM, Ausstieg spätestens zum Xetra-Schluss. Range = ±1 σ für die restliche Handelszeit aus der DAX-Tagesoption (ca. 68 %). Keine Anlageberatung.</p>
</section>

<section class="chart">
  <h2>Chart</h2>
  <div class="chart-live" data-src="{{BASIS}}dax/charts/JJJJ-MM-TT.json"></div>   <!-- beweglicher Chart; ersetzt auf der Webseite das Bild -->
  <figure class="chart">
    <img src="{{BASIS}}dax/charts/JJJJ-MM-TT.png" alt="DAX Stundenkerzen der letzten 5 Tage mit Marken für heute">
    <figcaption>Ziehen zum Verschieben, Mausrad oder zwei Finger zum Zoomen. Rechts: heute mit erwarteter Range und Indikation. Hintergrund: großer Trend (grün = Bull, rot = Bear).</figcaption>
  </figure>
</section>

<section class="signale">
  <h2>Signale</h2>
  <div class="tabelle">
    <table class="signale">
      <thead><tr><th>Signal</th><th>Wirkung</th><th>Stand und Einordnung</th></tr></thead>
      <tbody>
        <tr><td>Vorgaben USA</td><td class="gegenwind">Gegenwind</td><td>Nasdaq 100 −1,4 %, Futures −0,3 %: Chipwerte unter Druck.</td></tr>
        <!-- alle 13 Signale; Klassen rueckenwind | gegenwind | neutral -->
      </tbody>
    </table>
  </div>
</section>

<section class="trend">
  <h2>Großer Trend (3-Monats-Momentum)</h2>
  <dl class="marken">
    <div class="ziel"><dt>Stand</dt><dd>Bull</dd></div>   <!-- Bull (r > z) mit Klasse ziel, Bear mit Klasse stopp -->
    <div><dt>Seit</dt><dd>22.10. (5 Wechsel in 3 Monaten)</dd></div>   <!-- stand_seit und wechsel_3m -->
    <div><dt>Schluss 05.11.</dt><dd>+0,74 % vs. Zins +0,60 %</dd></div>   <!-- r gegen z aus dem letzten fertigen Schluss -->
    <div><dt>Heute dreht es bei Schluss unter</dt><dd>26.422 (jetzt −2,3 %)</dd></div>   <!-- bei Bear: „über“ -->
  </dl>
  <p class="risiko">1 Satz Einordnung (z. B. „Stünde der Monat heute, wäre das Signal Bear.“). Bull = Rendite der letzten 3 Monate über dem Geldmarktzins, Bear = darunter. Regel: Rendite der letzten 63 Handelstage (≈ 3 Monate) gegen den EZB-Einlagensatz, jeden Tag zum Schluss neu entschieden, Zeitrahmen Tageskerzen (nach Antonacci 2014, dort monatlich über 12 Monate; täglich entschieden dreht es öfter falsch). Keine Anlageberatung.</p>
</section>   <!-- fehlt der Block trendfolge in den Daten: Abschnitt weglassen -->

<section class="bilanz">
  <h2>Bilanz von gestern</h2>
  <p>Ergebnis der letzten Entscheidung (Gewinnseite erreicht, Verlustseite erreicht oder Schluss), ob die Spanne getroffen wurde, und Gesamtbilanz – direkt aus der Ausgabe von <code>entscheidung.py bilanz</code>.</p>
</section>

<section class="markt">
  <h2>Marktlage</h2>
  <!-- Tabelle wie bisher: Markt | Stand | Veränderung; Klassen plus / minus -->
  <!-- Zeilen: DAX (Schluss gestern), DAX (Eröffnung heute), DAX (jetzt, Einstieg), S&P 500, Nasdaq 100, Dow Jones, US-Futures (S&P/Nasdaq), Nikkei 225,
       Shanghai Composite, CSI 300, Hang Seng (je „Eröffnung X → Schluss/aktuell Y“), EUR/USD, Brent, Gold, VIX -->
  <p class="risiko">1 Satz zur China-Sitzung (Grund), Feiertage klar nennen.</p>
</section>

<section class="zinsen">
  <h2>Anleihen &amp; Zinsen</h2>
  <!-- Tabelle: Bund 2J / 10J, US-Treasury 2J / 10J (mit Veränderung in Bp.), Fed nächste Sitzung (Erwartung + Wahrscheinlichkeit),
       EZB-Einlagensatz, Risikoaufschlag Euro-Hochzins und US-Hochzins (mit Veränderung 1 Woche).
       Farbe nach Wirkung auf Aktien: steigende Renditen/Aufschläge = Klasse minus, fallende = plus -->
</section>

<section class="termine">
  <h2>Termine heute</h2>
  <ul>
    <li><span class="zeit">10:00</span> Eurozone: Einkaufsmanager Dienste – Prognose 51,7 · zuvor 53,0</li>
    <!-- schon veröffentlichte Werte mit „Ist X vs. Prognose Y“; dazu Quartalszahlen von DAX-Werten -->
  </ul>
</section>

<section class="news">
  <h2>Nachrichten zu DAX-Werten</h2>
  <ul><li><strong>Unternehmen:</strong> Was ist passiert. <em>Einschätzung für heute.</em></li></ul>   <!-- höchstens 5 -->
</section>

<section class="profi">
  <h2>Profi-Sicht &amp; Positionierung</h2>
  <ul>
    <li><strong>ING THINK:</strong> Einschätzung in 1–2 Sätzen (Artikel verlinken).</li>
    <li><strong>Positionierung (COT, Stand Datum):</strong> was auffällt.</li>
  </ul>
</section>

<section class="quellen">
  <h2>Quellen</h2>
  <ol><li><a href="https://…">Titel</a></li></ol>   <!-- Datenquellen der Skripte (Amber Terminal/Yahoo/Nasdaq/CNBC/FRED/CFTC/ING) einmal zusammengefasst nennen -->
</section>
```

## F. Ergänzungen zu Webseite und E-Mail

- **Commit:** zusätzlich die neuen Dateien aufnehmen: `git add notizen docs daten entscheidungen`.
- **E-Mail:** Ganz oben ein Kasten (Tabelle mit Rahmen) mit Richtung, Überzeugung, erwarteter Range, Obergrenze und Untergrenze (jeweils mit Zusatz Gewinnmitnahme bzw. Idee widerlegt) sowie einer Zeile „Großer Trend (3 Monate, täglich): Bull/Bear seit TT.MM.“. Darunter der Chart als **HTML** (Inhalt von `notizen/dax/charts/JJJJ-MM-TT-mail.html`, bei Sonderausgaben `JJJJ-MM-TT-HHMM-mail.html`, unverändert einfügen – siehe ANLEITUNG Abschnitt 5), darunter der Link „Beweglicher Chart auf der Webseite“ zur Berichtsseite (`https://consequencee.github.io/morgen-notiz/dax/`), dann die komplette Notiz. Signale als Tabelle, Rückenwind grün, Gegenwind rot (Inline-Styles).

## Tabellenzeilen (Marktlage)

DAX (Schluss gestern), DAX (Eröffnung heute), DAX (jetzt, Einstieg), S&P 500, Nasdaq 100, Dow Jones, US-Futures (S&P / Nasdaq), Nikkei 225, Shanghai Composite (Eröffnung → Schluss), CSI 300 (Eröffnung → Schluss), Hang Seng (Eröffnung → aktuell), EUR/USD, Brent, Gold, VIX

## Überschrift Nachrichten

`Nachrichten zu DAX-Werten`

## E-Mail-Betreff

`Morgen Notiz – DAX – TT.MM.JJJJ – Long 6/10` (bzw. `Short N/10` oder `Kein Trade`)
