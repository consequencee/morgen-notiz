// Beweglicher DAX-Chart für die Notizen (TradingView Lightweight Charts, Apache 2.0, liegt in vendor/).
// Sucht <div class="chart-live" data-src="…json">, lädt die Bibliothek nur dann und ersetzt das feste Bild.
(function () {
  const ziele = document.querySelectorAll(".chart-live[data-src]");
  if (!ziele.length) return;
  const basis = document.currentScript.src.replace(/chart\.js(\?.*)?$/, "");
  const s = document.createElement("script");
  s.src = basis + "vendor/lightweight-charts.standalone.production.js";
  s.onload = () => ziele.forEach(baue);
  document.head.appendChild(s);

  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const BERLIN = "Europe/Berlin";
  const fmt = (opt) => new Intl.DateTimeFormat("de-DE", { timeZone: BERLIN, ...opt });
  const uhr = fmt({ hour: "2-digit", minute: "2-digit" });
  const tagKurz = fmt({ weekday: "short", day: "2-digit", month: "2-digit" });
  const tagLang = fmt({ weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const alsDatum = (t) => (typeof t === "number" ? new Date(t * 1000) : new Date(`${t.year ?? t.slice(0, 4)}-${String(t.month ?? t.slice(5, 7)).padStart(2, "0")}-${String(t.day ?? t.slice(8, 10)).padStart(2, "0")}T12:00:00Z`));
  const zahl = (v) => v.toLocaleString("de-DE", { maximumFractionDigits: 0 });

  function schnitt(tage, n) {
    const out = [];
    for (let i = n - 1; i < tage.length; i++) {
      let sum = 0;
      for (let j = i - n + 1; j <= i; j++) sum += tage[j].close;
      out.push({ time: tage[i].time, value: sum / n });
    }
    return out;
  }

  async function baue(el) {
    let d;
    try {
      d = await (await fetch(el.dataset.src)).json();
    } catch (e) {
      return; // Bild bleibt stehen
    }
    const LW = window.LightweightCharts;
    const farbe = {
      text: css("--text"), leise: css("--leise"), plus: css("--plus"), minus: css("--minus"),
      blau: "#2f6fd6", band: "#7fa7e0", linie: css("--linie"), flaeche: css("--flaeche"),
    };
    const stil = { durchgezogen: LW.LineStyle.Solid, gestrichelt: LW.LineStyle.Dashed, gepunktet: LW.LineStyle.Dotted };

    el.innerHTML = "";
    const knoepfe = document.createElement("div");
    knoepfe.className = "chart-knoepfe";
    knoepfe.innerHTML = '<button type="button" data-modus="stunden" class="an">Stunden · 1 Monat</button><button type="button" data-modus="tage">Tage · 1 Jahr</button>';
    const flaeche = document.createElement("div");
    flaeche.className = "chart-flaeche";
    el.append(knoepfe, flaeche);
    if (d.trend && Object.keys(d.trend).length) {
      const leg = document.createElement("p");
      leg.className = "chart-legende";
      leg.textContent = "Hintergrund: großer Trend (3 Monate, täglich entschieden) – grün = Bull, rot = Bear.";
      el.append(leg);
    }
    el.closest("section")?.classList.add("live-an");

    const chart = LW.createChart(flaeche, {
      autoSize: true,
      layout: { background: { color: farbe.flaeche }, textColor: farbe.leise, fontSize: 11 },
      grid: { vertLines: { color: farbe.linie }, horzLines: { color: farbe.linie } },
      rightPriceScale: { borderColor: farbe.linie },
      timeScale: { borderColor: farbe.linie, rightOffset: 2 },
      crosshair: { mode: LW.CrosshairMode.Normal },
      localization: {
        locale: "de-DE",
        priceFormatter: (p) => zahl(p),
        timeFormatter: (t) => (typeof t === "number" ? tagLang.format(alsDatum(t)) : tagKurz.format(alsDatum(t))),
      },
    });
    // Hintergrund: großer Trend (Bull grün, Bear rot), Tag für Tag so, wie er an dem Tag galt
    const trend = d.trend || {};
    const hatTrend = Object.keys(trend).length > 0;
    const tagIn = new Intl.DateTimeFormat("en-CA", { timeZone: d.zeitzone || BERLIN, year: "numeric", month: "2-digit", day: "2-digit" });
    const tagVon = (t) => (typeof t === "number" ? tagIn.format(new Date(t * 1000)) : t);
    const TF = { bull: "rgba(26, 127, 55, 0.10)", bear: "rgba(207, 34, 46, 0.10)" };
    const hinter = hatTrend ? chart.addSeries(LW.HistogramSeries, { priceScaleId: "trend", priceLineVisible: false, lastValueVisible: false, base: 0 }) : null;
    if (hinter) chart.priceScale("trend").applyOptions({ scaleMargins: { top: 0, bottom: 0 }, visible: false });
    const band = (zeiten) => zeiten.map((t) => { const st = trend[tagVon(t)]; return st ? { time: t, value: 1, color: TF[st] } : { time: t }; });
    const kerzen = chart.addSeries(LW.CandlestickSeries, {
      upColor: farbe.plus, downColor: farbe.minus, borderVisible: false,
      wickUpColor: farbe.plus, wickDownColor: farbe.minus, priceLineVisible: false, lastValueVisible: false,
      // Kursbereich immer so wählen, dass alle Linien (Grenzen, Spanne) sichtbar sind
      autoscaleInfoProvider: (original) => {
        const r = original();
        const preise = d.linien.map((l) => l.preis);
        if (!r || !preise.length) return r;
        return { ...r, priceRange: { minValue: Math.min(r.priceRange.minValue, ...preise), maxValue: Math.max(r.priceRange.maxValue, ...preise) } };
      },
    });
    for (const l of d.linien) {
      kerzen.createPriceLine({
        price: l.preis, color: farbe[l.farbe] || farbe.leise, lineWidth: l.dick ? 2 : 1,
        lineStyle: stil[l.stil] ?? LW.LineStyle.Dashed, axisLabelVisible: true, title: l.name,
      });
    }
    const schnitte = [[21, "#b8860b"], [50, "#8a63d2"], [200, "#2f6fd6"]].map(([n, c]) => ({
      n, s: chart.addSeries(LW.LineSeries, { color: c, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: `${n} T`, visible: false }),
    }));

    function zeige(modus) {
      knoepfe.querySelectorAll("button").forEach((b) => b.classList.toggle("an", b.dataset.modus === modus));
      if (modus === "stunden") {
        const leer = d.heute_slots.map((t) => ({ time: t })); // Platz für heute (noch keine Kerzen)
        kerzen.setData([...d.stunden, ...leer]);
        if (hinter) hinter.setData(band([...d.stunden.map((c) => c.time), ...d.heute_slots]));
        schnitte.forEach(({ s }) => s.applyOptions({ visible: false }));
        chart.applyOptions({
          timeScale: {
            timeVisible: true,
            tickMarkFormatter: (t, typ) => (typ <= 2 ? tagKurz.format(alsDatum(t)) : uhr.format(alsDatum(t))),
          },
        });
        const n = d.stunden.length + leer.length;
        chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 9 * 6), to: n + 1 });
      } else {
        kerzen.setData(d.tage);
        if (hinter) hinter.setData(band(d.tage.map((c) => c.time)));
        for (const { n, s } of schnitte) {
          s.setData(schnitt(d.tage, n));
          s.applyOptions({ visible: true });
        }
        chart.applyOptions({ timeScale: { timeVisible: false, tickMarkFormatter: (t) => tagKurz.format(alsDatum(t)) } });
        chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, d.tage.length - 90), to: d.tage.length + 2 });
      }
    }
    knoepfe.addEventListener("click", (ev) => ev.target.dataset.modus && zeige(ev.target.dataset.modus));
    zeige(location.hash === "#tage" ? "tage" : "stunden");
  }
})();
