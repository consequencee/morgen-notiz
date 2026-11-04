#!/usr/bin/env node
// Holt alle Zahlen für die DAX- bzw. US30-Notiz über den Datenteil des Amber Terminals (amber/, MIT-Lizenz)
// und schreibt sie nach daten/<bericht>/JJJJ-MM-TT.json. Auf stdout kommt eine lesbare Zusammenfassung,
// aus der die Notiz ihre Zahlen nimmt. Jeder Block ist einzeln abgesichert: fällt eine Quelle aus,
// steht ihr Fehler unter "fehler" und der Rest läuft weiter.
//
// Aufruf: node scripts/marktdaten.mjs [--bericht dax|us30] [--datum JJJJ-MM-TT]

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
process.env.QT_DATA_DIR ||= fs.mkdtempSync(path.join(os.tmpdir(), "amber-"));
const lade = (p) => import(pathToFileURL(path.join(ROOT, "amber", p)).href);
const prov = await lade("lib/providers.js");
const fn = async (name, q = {}) => (await lade(`lib/fn/${name}.js`)).default(q);

const arg = (name) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
};
const tagIn = (tz, ms = Date.now()) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(new Date(ms));
const zeitIn = (tz, ms) =>
  new Intl.DateTimeFormat("de-DE", { timeZone: tz, hour: "2-digit", minute: "2-digit" }).format(new Date(ms));
const HEUTE = arg("datum") || tagIn("Europe/Berlin");
const BERICHT = arg("bericht") || "dax";
// Je Bericht: Index (Yahoo), Börsenzeitzone, Handelsfenster in Börsenzeit, Volatilitätsindex
const BERICHTE = {
  dax: { index: "dax", symbol: "^GDAXI", tz: "Europe/Berlin", von: "09:00", bis: "17:30", vola: "vdax" },
  us30: { index: "dow", symbol: "^DJI", tz: "America/New_York", von: "09:30", bis: "16:00", vola: "vxd" },
};
const CFG = BERICHTE[BERICHT];
if (!CFG) throw new Error(`Unbekannter Bericht ${BERICHT}`);
const fin = (v) => typeof v === "number" && Number.isFinite(v);
const rund = (v, dp = 2) => (fin(v) ? Number(v.toFixed(dp)) : null);
const pct = (a, b) => (fin(a) && fin(b) && b ? rund((a / b - 1) * 100, 2) : null);

const z_vorab = []; // Zeilen, die vor der Zusammenfassung feststehen
const out = { datum: HEUTE, erstellt: new Date().toISOString(), quelle: "Amber Terminal (amber/), öffentliche Daten", fehler: {} };
async function block(name, f) {
  try {
    out[name] = await f();
  } catch (e) {
    out.fehler[name] = String(e?.message || e);
  }
}

// ---------- Märkte: Tageskerzen je Börse ----------
const MAERKTE = [
  ["dax", "^GDAXI", "DAX", "Europe/Berlin"],
  ["estx50", "^STOXX50E", "Euro Stoxx 50", "Europe/Berlin"],
  ["spx", "^GSPC", "S&P 500", "America/New_York"],
  ["ndx", "^NDX", "Nasdaq 100", "America/New_York"],
  ["dow", "^DJI", "Dow Jones", "America/New_York"],
  ["nikkei", "^N225", "Nikkei 225", "Asia/Tokyo"],
  ["shanghai", "000001.SS", "Shanghai Composite", "Asia/Shanghai"],
  ["csi300", "000300.SS", "CSI 300", "Asia/Shanghai"],
  ["hangseng", "^HSI", "Hang Seng", "Asia/Hong_Kong"],
  ["eurusd", "EURUSD=X", "EUR/USD", "Europe/London"],
  ["brent", "BZ=F", "Brent (USD/Barrel)", "America/New_York"],
  ["wti", "CL=F", "WTI (USD/Barrel)", "America/New_York"],
  ["gold", "GC=F", "Gold (USD/Unze)", "America/New_York"],
  ["vix", "^VIX", "VIX", "America/New_York"],
  ["vxd", "^VXD", "VXD (Dow-Volatilität)", "America/New_York"],
  ["us10y", "^TNX", "US-Treasury 10J (Rendite in %, Yahoo)", "America/New_York"],
  // Ersatz für die Kreditaufschläge, falls FRED nicht antwortet: Kurse der großen Anleihe-ETFs
  ["hyg", "HYG", "US-Hochzins-Anleihen-ETF (HYG)", "America/New_York"],
  ["lqd", "LQD", "US-Unternehmensanleihen-ETF Investment Grade (LQD)", "America/New_York"],
  ["es", "ES=F", "S&P-500-Future", "America/New_York"],
  ["nq", "NQ=F", "Nasdaq-100-Future", "America/New_York"],
  ["ym", "YM=F", "Dow-Future", "America/New_York"],
];

// Kerzen direkt von Yahoo (wie Amber selbst), damit Zeitstempel der echten Sitzung entsprechen und die
// laufende Kerze (Schluss noch leer) mit dem aktuellen Kurs erhalten bleibt.
async function yahoo(sym, interval, range) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=${interval}&range=${range}`;
  const res = await fetch(url, { headers: prov.YAHOO_UA });
  if (!res.ok) throw new Error(`Yahoo HTTP ${res.status}`);
  const r = (await res.json())?.chart?.result?.[0];
  if (!r?.timestamp) throw new Error("Yahoo ohne Kerzen");
  const q = r.indicators.quote[0];
  const bars = r.timestamp.map((t, i) => ({ t, o: q.open[i], h: q.high[i], l: q.low[i], c: q.close[i] }));
  const letzte = bars.at(-1);
  if (letzte && !fin(letzte.c) && fin(r.meta.regularMarketPrice)) letzte.c = r.meta.regularMarketPrice;
  return { meta: r.meta, bars: bars.filter((b) => fin(b.c) && fin(b.o)) };
}

async function tageskerzen(sym, tz) {
  const { meta, bars: k } = await yahoo(sym, "1d", "1y");
  if (!k.length) throw new Error("keine Kerzen");
  const letzte = k.at(-1);
  const vor = k.at(-2);
  const vorSchluss = vor?.c ?? meta.chartPreviousClose ?? null;
  const tag = tagIn(tz, letzte.t * 1000);
  return {
    tag, // Handelstag der letzten Kerze (Börsenzeit)
    heute: tag === tagIn(tz),
    stand_zeit: meta.regularMarketTime ? new Date(meta.regularMarketTime * 1000).toISOString() : null,
    eroeffnung: rund(letzte.o, 4),
    stand: rund(letzte.c, 4),
    hoch: rund(letzte.h, 4),
    tief: rund(letzte.l, 4),
    vortag: vor ? tagIn(tz, vor.t * 1000) : null,
    vortag_schluss: rund(vorSchluss, 4),
    veraenderung_pct: pct(letzte.c, vorSchluss),
    eroeffnung_pct: pct(letzte.o, vorSchluss),
    kerzen: k.map((c) => ({ tag: tagIn(tz, c.t * 1000), o: rund(c.o), h: rund(c.h), l: rund(c.l), c: rund(c.c, 4) })),
  };
}

await block("maerkte", async () => {
  const m = {};
  await Promise.all(
    MAERKTE.map(async ([key, sym, name, tz]) => {
      try {
        const t = await tageskerzen(sym, tz);
        const { kerzen, ...rest } = t;
        m[key] = { name, symbol: sym, ...rest, ...(key === CFG.index ? { kerzen } : {}) };
      } catch (e) {
        m[key] = { name, symbol: sym, fehler: String(e?.message || e) };
      }
    }),
  );
  return m;
});

// ---------- Index: Stundenkerzen (Chart, Bilanz) und Kennzahlen ----------
// "zeit" ist Börsenzeit (DAX: Berlin, Dow: New York), "tag" der Handelstag in Börsenzeit.
await block("index_stunden", async () => {
  const { bars } = await yahoo(CFG.symbol, "60m", "1mo");
  return bars
    .map((c) => ({ t: c.t, tag: tagIn(CFG.tz, c.t * 1000), zeit: zeitIn(CFG.tz, c.t * 1000), o: rund(c.o), h: rund(c.h), l: rund(c.l), c: rund(c.c) }))
    .filter((c) => c.zeit >= CFG.von && c.zeit < CFG.bis && !(c.o === c.h && c.h === c.l && c.l === c.c));
});

// 5-Minuten-Kerzen der letzten Tage (Sitzung): Bewertung ab dem genauen Einstiegszeitpunkt
await block("index_5min", async () => {
  const { bars } = await yahoo(CFG.symbol, "5m", "5d");
  return bars
    .map((c) => ({ t: c.t, tag: tagIn(CFG.tz, c.t * 1000), zeit: zeitIn(CFG.tz, c.t * 1000), o: rund(c.o), h: rund(c.h), l: rund(c.l), c: rund(c.c) }))
    .filter((c) => c.zeit >= CFG.von && c.zeit < CFG.bis);
});

await block("index_kennzahlen", async () => {
  const k = (out.maerkte?.[CFG.index]?.kerzen || []).filter((c) => c.tag < HEUTE);
  if (k.length < 22) throw new Error("zu wenige Tageskerzen");
  const r = k.slice(-21).map((c, i, a) => (i ? Math.log(c.c / a[i - 1].c) : null)).slice(1);
  const mw = r.reduce((s, x) => s + x, 0) / r.length;
  const sd = Math.sqrt(r.reduce((s, x) => s + (x - mw) ** 2, 0) / (r.length - 1));
  const v = k.at(-1);
  const ma = (n) => rund(k.slice(-n).reduce((s, c) => s + c.c, 0) / Math.min(n, k.length));
  return {
    letzter_handelstag: v.tag,
    schluss: v.c,
    hoch: v.h,
    tief: v.l,
    eroeffnung: v.o,
    realisierte_vola_20t_pct: rund(sd * Math.sqrt(252) * 100, 1), // annualisiert, Ersatz für VDAX/VXD
    schnitt_21: ma(21),
    schnitt_50: k.length >= 50 ? ma(50) : null,
    schnitt_200: k.length >= 200 ? ma(200) : null,
    hinweis: "Gleitende Durchschnitte aus Tagesschlusskursen bis zum letzten Handelstag",
  };
});

// ---------- VDAX (früher VDAX-NEW): eingepreiste 30-Tage-Schwankung des DAX, von onvista ----------
async function vdax() {
  const res = await fetch("https://www.onvista.de/index/VDAX-NEW-Index-12105789", { headers: { "User-Agent": "Mozilla/5.0 (Macintosh)" } });
  if (!res.ok) throw new Error(`onvista HTTP ${res.status}`);
  const h = await res.text();
  const wert = Number((h.match(/"last":\s*([\d.]+)/) || [])[1]);
  const vorher = Number((h.match(/"previousLast":\s*([\d.]+)/) || [])[1]);
  const zeit = (h.match(/"datetimeLast":\s*"([^"]+)"/) || [])[1];
  if (!(wert > 5 && wert < 90)) throw new Error("kein plausibler VDAX-Wert auf der Seite");
  return { name: "VDAX", wert: rund(wert), vorher: fin(vorher) ? rund(vorher) : null, zeit, quelle: "onvista.de (VDAX, berechnet 9:15–17:30 Uhr)" };
}
async function vxd() {
  const m = out.maerkte?.vxd;
  if (!m || m.fehler) throw new Error(m?.fehler || "VXD fehlt");
  return { name: "VXD", wert: rund(m.stand), vorher: rund(m.vortag_schluss), zeit: m.stand_zeit, quelle: "Yahoo Finance (^VXD, Cboe DJIA Volatility Index)" };
}
await block("vola", CFG.vola === "vdax" ? vdax : vxd);

// ---------- nur DAX: vorbörsliche Indikation (L&S, J.P. Morgan, UBS) von onvista ----------
// Median der Indikationen, die höchstens 60 Minuten alt sind; Veränderung gegen den Xetra-Schluss.
if (BERICHT === "dax") {
  await block("indikation", async () => {
    const res = await fetch("https://www.onvista.de/index/DAX-Index-20735", { headers: { "User-Agent": "Mozilla/5.0 (Macintosh)" } });
    if (!res.ok) throw new Error(`onvista HTTP ${res.status}`);
    const h = await res.text();
    const json = JSON.parse((h.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/) || [])[1] || "{}");
    const suche = (o) => { if (o && typeof o === "object") { if (o.quoteList) return o.quoteList; for (const v of Object.values(o)) { const r = suche(v); if (r) return r; } } return null; };
    const liste = suche(json)?.list || [];
    const jetzt = Date.now();
    const quellen = liste.filter((q) => /Indikation/i.test(q.market?.name || "")).map((q) => ({ quelle: q.market.name, kurs: rund(q.last), zeit: q.datetimeLast, alter_min: Math.round((jetzt - Date.parse(q.datetimeLast)) / 60000) }));
    const frisch = quellen.filter((q) => fin(q.kurs) && q.alter_min <= 60).map((q) => q.kurs).sort((a, b) => a - b);
    if (!frisch.length) throw new Error(`keine frische Indikation (${quellen.map((q) => `${q.quelle} ${q.alter_min} min alt`).join(", ") || "keine Quellen"})`);
    const wert = frisch.length % 2 ? frisch[(frisch.length - 1) / 2] : (frisch[frisch.length / 2 - 1] + frisch[frisch.length / 2]) / 2;
    const schluss = out.index_kennzahlen?.schluss;
    return { wert: rund(wert, 0), veraenderung_pct: pct(wert, schluss), gegen_schluss: schluss, quellen, quelle: "onvista.de: Median der außerbörslichen DAX-Indikationen (höchstens 60 Minuten alt)" };
  });
}

// ---------- Einstieg: Kurs zum Zeitpunkt der Notiz (die Notiz entsteht nach der Eröffnung) ----------
// DAX: Echtzeit-Indikationen (onvista, folgen während des Handels dem DAX; Yahoo ist 15 Minuten verzögert).
// Dow: Yahoo ^DJI mit Zeitstempel. Dazu die heutige Eröffnung und die Lücke zum Vortagesschluss.
await block("einstieg", async () => {
  const heute = (out.index_5min || []).filter((c) => c.tag === HEUTE);
  const schluss = out.index_kennzahlen?.schluss;
  let kurs, zeit, quelle;
  if (BERICHT === "dax" && out.indikation?.wert) {
    kurs = out.indikation.wert; zeit = new Date().toISOString(); quelle = "Median der Echtzeit-Indikationen L&S, J.P. Morgan, UBS (onvista)";
  } else {
    const { meta } = await yahoo(CFG.symbol, "1m", "1d");
    kurs = meta.regularMarketPrice; zeit = new Date(meta.regularMarketTime * 1000).toISOString(); quelle = `Yahoo Finance ${CFG.symbol}`;
  }
  if (!fin(kurs)) throw new Error("kein aktueller Kurs");
  const offen = heute[0]?.o ?? (out.maerkte?.[CFG.index]?.heute ? out.maerkte[CFG.index].eroeffnung : null);
  return {
    kurs: rund(kurs, 0), zeit, alter_min: Math.round((Date.now() - Date.parse(zeit)) / 60000), quelle,
    eroeffnung_heute: rund(offen, 0), luecke_pct: pct(offen, schluss), seit_eroeffnung_pct: pct(kurs, offen),
    hoch_heute: heute.length ? rund(Math.max(...heute.map((c) => c.h)), 0) : null, tief_heute: heute.length ? rund(Math.min(...heute.map((c) => c.l)), 0) : null,
  };
});
if (out.einstieg) z_vorab.push(`\n## Einstieg (jetzt)\n- ${out.einstieg.kurs} um ${out.einstieg.zeit} (${out.einstieg.alter_min} min alt, ${out.einstieg.quelle}) · Eröffnung heute ${out.einstieg.eroeffnung_heute ?? "n/v"} (Lücke ${out.einstieg.luecke_pct ?? "n/v"} % zum Vortagesschluss) · seit Eröffnung ${out.einstieg.seit_eroeffnung_pct ?? "n/v"} % · Hoch/Tief heute ${out.einstieg.hoch_heute ?? "n/v"}/${out.einstieg.tief_heute ?? "n/v"} (Yahoo, bis 15 min verzögert)`);

// ---------- Tagesoption: eingepreiste Bewegung bis zum heutigen Schluss ----------
// Straddle (Call + Put am Geld) ≈ 0,8 × σ × Kurs × √Tage  →  σ je Tag ≈ Straddle / 0,798 / √Tage.
// DAX: Eurex-Tagesoption ODAP (verfällt zur Xetra-Schlussauktion), Abrechnungspreise vom letzten veröffentlichten Handelstag.
// US30: S&P-500-Tagesoption (Cboe, verzögert), mit VXD/VIX auf den Dow umgerechnet.
const werktage = (von, bis) => { let n = 0; for (let t = Date.parse(von + "T12:00:00Z") + 864e5; t <= Date.parse(bis + "T12:00:00Z"); t += 864e5) { const w = new Date(t).getUTCDay(); if (w && w < 6) n++; } return n; };
async function odap() {
  const basis = "https://www.eurex.com/api/v1/overallstatistics/3734540";
  const kopf = { "User-Agent": "Mozilla/5.0 (Macintosh)" };
  const ue = await (await fetch(`${basis}?filtertype=overview`, { headers: kopf })).json();
  const verfall = HEUTE.replaceAll("-", "");
  const zeile = (ue.dataRows || []).find((r) => r.date === verfall);
  if (!zeile) throw new Error(`keine ODAP-Serie mit Verfall ${HEUTE}`);
  const tage = (ue.header?.tradingDates || []).map((d) => `${d.slice(6, 10)}-${d.slice(3, 5)}-${d.slice(0, 2)}`).filter((d) => d < HEUTE).sort();
  const bus = tage.at(-1);
  if (!bus) throw new Error("kein veröffentlichter Handelstag");
  const det = await (await fetch(`${basis}?filtertype=detail&productdate=${verfall}&busdate=${bus.replaceAll("-", "")}&contracttype=${zeile.contractType}`, { headers: kopf })).json();
  const schluss = (out.maerkte?.dax?.kerzen || []).find((c) => c.tag === bus)?.c;
  if (!fin(schluss)) throw new Error(`kein DAX-Schluss für ${bus}`);
  const c = Object.fromEntries((det.dataRowsCall || []).map((r) => [r.strike, r.dSettle]));
  const p = Object.fromEntries((det.dataRowsPut || []).map((r) => [r.strike, r.dSettle]));
  const k = Object.keys(c).map(Number).filter((x) => fin(p[x])).sort((a, b) => Math.abs(a - schluss) - Math.abs(b - schluss))[0];
  const straddle = c[k] + p[k];
  const n = Math.max(1, werktage(bus, HEUTE));
  const sigmaPct = straddle / 0.798 / Math.sqrt(n) / schluss * 100;
  return { name: "DAX-Tagesoption (Eurex ODAP)", verfall: HEUTE, preise_vom: bus, handelstage: n, basispreis: k, call: c[k], put: p[k], straddle: rund(straddle, 1), sigma_tag_pct: rund(sigmaPct, 3), sigma_tag_punkte: rund(schluss * sigmaPct / 100, 0), quelle: "Eurex, tägliche Abrechnungspreise (dSettle) der DAX-Tagesoptionen ODAP" };
}
async function spx0dte() {
  const omon = (await lade("lib/fn/omon.js")).default;
  const tagNY = tagIn("America/New_York");
  // erst der S&P-500-Index über Cboe; antwortet Cboe nicht (in der Cloud schon vorgekommen), der SPY-ETF über Nasdaq
  let r, fehler = [];
  for (const symbol of ["^GSPC", "SPY"]) {
    try {
      r = await omon({ symbol, expiry: HEUTE });
      if (r.expiry?.date === HEUTE && fin(r.move?.pct)) break;
      fehler.push(`${symbol}: keine Serie mit Verfall ${HEUTE} (nächste ${r.expiry?.date})`);
      r = null;
    } catch (e) {
      fehler.push(`${symbol}: ${e?.message || e}`);
    }
  }
  if (!r) throw new Error(fehler.join(" | "));
  const pct = r.move?.pct;
  if (!fin(pct)) throw new Error("keine eingepreiste Bewegung");
  const vxd = out.maerkte?.vxd?.stand, vix = out.maerkte?.vix?.stand;
  const faktor = fin(vxd) && fin(vix) && vix > 0 ? vxd / vix : 1;
  const sigmaPct = (pct / 0.798) * faktor;
  const schluss = out.index_kennzahlen?.schluss;
  return { name: `S&P-500-Tagesoption (${r.symbol}), auf den Dow umgerechnet`, verfall: HEUTE, stand: r.priceTime, ny_tag: tagNY, basispreis: r.move.strike, straddle_pct: rund(pct, 3), faktor_vxd_vix: rund(faktor, 3), sigma_tag_pct: rund(sigmaPct, 3), sigma_tag_punkte: fin(schluss) ? rund(schluss * sigmaPct / 100, 0) : null, quelle: r.source };
}
await block("tagesoption", BERICHT === "dax" ? odap : spx0dte);
// Spanne bevorzugt aus der Tagesoption; VDAX/VXD bleiben unter "vola_index" erhalten und dienen als Ersatz
if (out.tagesoption?.sigma_tag_pct) {
  out.vola_index = out.vola;
  out.vola = { name: out.tagesoption.name, wert: rund(out.tagesoption.sigma_tag_pct * Math.sqrt(252), 2), zeit: out.tagesoption.preise_vom || out.tagesoption.stand, quelle: `${out.tagesoption.quelle}; als Jahresvola ausgedrückt (σ Tag × √252)` };
}

// ---------- Anleihen, Zinsen, Kredit ----------
const kurve = (d) => {
  const n = d.curves?.find((c) => c.key === "now") || d.curves?.[0];
  const p = d.curves?.find((c) => c.key === "prev" || c.key === "1W");
  return { name: d.name, stand: n?.date, werte: n?.values, vergleich: p ? { label: p.label, werte: p.values } : null, spread_2s10s_bp: d.spread?.bp, quelle: d.source };
};
await block("bund", async () => kurve(await fn("gc", { country: "DE" })));
// Ersatz für die Bund-Kurve von CNBC (blockt Cloud-Rechenzentren): Bundesbank, Zinsstruktur-Renditen, Tageswerte
await block("bund_bundesbank", async () => {
  const reihe = async (lz) => {
    const url = `https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.${lz}.R.A.A._Z._Z.A?lastNObservations=2&format=csv`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Bundesbank HTTP ${res.status}`);
    const z = (await res.text()).split(/\r?\n/).filter((l) => /^\d{4}-\d{2}-\d{2};/.test(l)).map((l) => l.split(";"));
    return z.map(([tag, wert]) => ({ tag, wert: Number(wert.replace(",", ".")) })).filter((x) => fin(x.wert));
  };
  const [j2, j10] = await Promise.all([reihe("R02XX"), reihe("R10XX")]);
  const letzte = (r) => ({ tag: r.at(-1)?.tag, wert: r.at(-1)?.wert, veraenderung_bp: r.length > 1 ? rund((r.at(-1).wert - r.at(-2).wert) * 100, 1) : null });
  return { "2J": letzte(j2), "10J": letzte(j10), quelle: "Deutsche Bundesbank, aus der Zinsstruktur abgeleitete Renditen (Vortag)" };
});
await block("us_treasury", async () => kurve(await fn("gc", { country: "US" })));
await block("us_treasury_live", async () => kurve(await fn("gc", { country: "USLIVE" })));
await block("fed_pfad", async () => {
  const d = await fn("wirp", {});
  return { effr: d.effr, sitzungen: (d.meetings || []).slice(0, 4).map((m) => ({ datum: m.date, nach: rund(m.after), schritt_bp: rund(m.stepBp, 1), wahrscheinlichkeit_25bp: rund(Math.abs(m.stepMoves) * 100, 0), richtung: m.stepBp >= 0 ? "Erhöhung" : "Senkung" })), quelle: d.source };
});
await block("leitzinsen", async () => {
  const d = await fn("cbrt", {});
  return { zeilen: (d.rows || []).filter((r) => ["US", "XM", "GB", "JP", "CH", "CN"].includes(r.area)).map((r) => ({ bank: r.bank, satz: r.rate, letzte_aenderung: r.changed, um_bp: r.changeBp, zielband: r.target ? `${r.target.from}–${r.target.to}` : null })), quelle: d.source };
});
await block("kredit", async () => {
  const d = await fn("cred", {});
  return { zeilen: (d.rows || []).map(({ history, ...r }) => r), quelle: d.source };
});

// ---------- Kalender, Überraschungen, Positionierung ----------
const LAENDER = new Set(["Germany", "Euro Zone", "Eurozone", "European Union", "United States", "China", "France", "United Kingdom", "Japan"]);
await block("kalender", async () => {
  const d = await fn("eco", {});
  const gestern = new Date(Date.parse(HEUTE + "T12:00:00Z") - 86400e3).toISOString().slice(0, 10);
  // Tag nach Berlin-Zeit; heute alles mit Prognose/Ist oder Reden/Entscheiden, gestern nur Veröffentlichtes ab 14:00
  const zeilen = (d.rows || [])
    .filter((r) => LAENDER.has(r.country) && r.time)
    .map((r) => ({ tag: tagIn("Europe/Berlin", Date.parse(r.time)), zeit_berlin: zeitIn("Europe/Berlin", Date.parse(r.time)), land: r.country, termin: r.event, ist: r.actual, prognose: r.consensus, vorher: r.previous }))
    .filter((r) => r.prognose != null || r.ist != null || /speaks|decision|rate|press conference|minutes|statement/i.test(r.termin))
    .filter((r) => r.tag === HEUTE || (r.tag === gestern && r.ist != null && r.zeit_berlin >= "14:00"));
  return { zeilen, quelle: d.source };
});
await block("us_ueberraschungen", async () => {
  const d = await fn("surp", {});
  return { zeilen: (d.rows || []).slice(0, 12).map((r) => ({ tag: r.day, termin: r.name, ist: r.actual, prognose: r.consensus, ueberraschung: r.surprise, spx_pct: r.spx, us10y_bp: r.us10y })), quelle: d.source };
});
await block("positionierung", async () => {
  const d = await fn("cot", {});
  const z = [];
  for (const s of d.sections || [])
    for (const r of s.rows || [])
      z.push({ markt: r.name, stand: r.date, gruppen: Object.fromEntries((r.groups || []).map((g) => [g.key, { netto: g.net, veraenderung: g.chg }])) });
  return { zeilen: z, legende: "lev = Hebel-/Hedgefonds, am = Vermögensverwalter, dealer = Händler, mm = Managed Money, pm = Produzenten, swap = Swap-Händler", quelle: d.source };
});

// ---------- nur US30: Dow-Werte vorbörslich mit Indexbeitrag, Quartalszahlen ----------
// Zusammensetzung des Dow Jones (Stand der Liste: Nov. 2024; bei Indexänderungen hier anpassen)
const DOW = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT"];
if (BERICHT === "us30") {
  // Indikation für den Dow: Schluss × Veränderung des Dow-Futures (YM) seit dessen Vortagesschluss
  await block("indikation", async () => {
    const ym = out.maerkte?.ym;
    const schluss = out.index_kennzahlen?.schluss;
    if (!ym || ym.fehler || !fin(ym.veraenderung_pct) || !fin(schluss)) throw new Error("Dow-Future oder Dow-Schluss fehlt");
    return { wert: rund(schluss * (1 + ym.veraenderung_pct / 100), 0), ym_pct: ym.veraenderung_pct, stand: ym.stand_zeit, quelle: "Dow-Schluss × Veränderung YM=F (Yahoo)" };
  });
  await block("dow_werte", async () => {
    const bq = (await lade("lib/fn/bq.js")).default;
    const z = [];
    for (let i = 0; i < DOW.length; i += 6)
      z.push(...(await Promise.all(DOW.slice(i, i + 6).map(async (t) => {
        try {
          const q = await bq({ symbol: t });
          const offen = q.state === "REGULAR" || !q.pre;  // nach der Eröffnung zählt der laufende Kurs
          const jetzt = offen ? q.last?.price : q.pre.price;
          return { ticker: t, name: q.name, vortag: q.prevClose, jetzt, quelle: offen ? "laufend" : "vorbörslich", aenderung_pct: pct(jetzt, q.prevClose) };
        } catch (e) {
          return { ticker: t, fehler: String(e?.message || e) };
        }
      }))));
    // Dow = Summe der Kurse / Divisor → Divisor aus Vortagesschlüssen und Dow-Schluss; Beitrag in Indexpunkten
    const ok = z.filter((r) => fin(r.vortag) && fin(r.jetzt));
    const dowSchluss = out.index_kennzahlen?.schluss;
    const divisor = ok.length === DOW.length && dowSchluss ? ok.reduce((s, r) => s + r.vortag, 0) / dowSchluss : null;
    for (const r of ok) r.beitrag_punkte = divisor ? rund((r.jetzt - r.vortag) / divisor, 0) : null;
    z.sort((a, b) => Math.abs(b.beitrag_punkte ?? 0) - Math.abs(a.beitrag_punkte ?? 0));
    return { divisor: rund(divisor, 5), summe_beitrag: divisor ? rund(ok.reduce((s, r) => s + r.beitrag_punkte, 0), 0) : null, werte: z, hinweis: "Liste Stand Nov. 2024 – bei Indexänderungen anpassen" };
  });
  await block("dow_zahlen", async () => {
    const info = await lade("lib/market-info.js");
    const e = await info.earnings(3);
    return (Array.isArray(e) ? e : e?.rows || []).filter((r) => DOW.includes(r.ticker)).map((r) => ({ tag: r.date, ticker: r.ticker, name: r.name, wann: r.when, eps_prognose: r.epsForecast }));
  });
}

// ---------- Profi-Sicht: ING Think ----------
await block("ing_think", async () => {
  let res;
  for (let versuch = 1; versuch <= 3; versuch++) {  // ING antwortet gelegentlich mit 503 – kurz warten und neu versuchen
    res = await fetch("https://think.ing.com/rss/", { headers: { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36", Accept: "application/rss+xml, application/xml, text/xml, */*" } });
    if (res.ok) break;
    await new Promise((r) => setTimeout(r, 3000 * versuch));
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const xml = await res.text();
  const feld = (it, tag) => (it.match(new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?</${tag}>`)) || [])[1]?.trim();
  return {
    artikel: [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].slice(0, 15).map(([, it]) => ({
      zeit: feld(it, "dc:date") || feld(it, "pubDate"),
      titel: feld(it, "title"),
      link: feld(it, "link"),
      text: (feld(it, "description") || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").slice(0, 400),
    })),
    quelle: "ING THINK RSS (think.ing.com)",
  };
});

// ---------- speichern + Zusammenfassung ----------
const ziel = path.join(ROOT, "daten", BERICHT, `${HEUTE}.json`);
fs.mkdirSync(path.dirname(ziel), { recursive: true });
fs.writeFileSync(ziel, JSON.stringify(out, null, 1));

const z = [];
const de = (v, dp = 2) => (fin(v) ? v.toLocaleString("de-DE", { minimumFractionDigits: dp, maximumFractionDigits: dp }) : "n/v");
const vz = (v, dp = 2) => (fin(v) ? `${v > 0 ? "+" : v < 0 ? "−" : "±"}${de(Math.abs(v), dp)}` : "n/v");
z.push(...[]);
z.push(`# Marktdaten ${BERICHT.toUpperCase()} ${HEUTE} (Abruf ${new Date().toLocaleString("de-DE", { timeZone: "Europe/Berlin" })} Berlin) → ${path.relative(ROOT, ziel)}`);
z.push(...z_vorab);
z.push("\n## Märkte (letzte Tageskerze je Börse)");
for (const [key] of MAERKTE) {
  const m = out.maerkte?.[key];
  if (!m) continue;
  if (m.fehler) { z.push(`- ${m.name}: n/v (${m.fehler})`); continue; }
  const dp = key === "eurusd" ? 4 : 2;
  z.push(`- ${m.name}: ${de(m.stand, dp)} (${vz(m.veraenderung_pct)} % vs. ${m.vortag ?? "Vortag"}) · Handelstag ${m.tag}${m.heute ? " (heute)" : ""} · Eröffnung ${de(m.eroeffnung, dp)} (${vz(m.eroeffnung_pct)} % vs. Vortagesschluss)`);
}
const k = out.index_kennzahlen;
if (k) if (out.tagesoption) { const t = out.tagesoption; z.push(`\n## Tagesoption (Spanne für heute)\n- ${t.name}: Straddle ${t.straddle ?? t.straddle_pct + " %"} am Basispreis ${t.basispreis} → erwartete Tagesbewegung ±${de(t.sigma_tag_pct, 2)} % ≈ ±${de(t.sigma_tag_punkte, 0)} Punkte${t.preise_vom ? ` (Preise vom ${t.preise_vom}, ${t.handelstage} Handelstag(e) bis Verfall)` : ""}${t.faktor_vxd_vix ? ` (Faktor VXD/VIX ${de(t.faktor_vxd_vix, 3)})` : ""}`); }
const vi = out.vola_index || out.vola;
if (vi) z.push(`\n## ${vi.name}\n- ${de(vi.wert)} % (Vortag ${de(vi.vorher)} %), Stand ${vi.zeit}, ${vi.quelle}${out.vola_index ? " – nur Vergleich/Ersatz, die Spanne kommt aus der Tagesoption" : ""}`);
z.push(`\n## ${CFG.index === "dax" ? "DAX" : "Dow"}-Kennzahlen\n- Letzter Handelstag ${k.letzter_handelstag}: Eröffnung ${de(k.eroeffnung)}, Hoch ${de(k.hoch)}, Tief ${de(k.tief)}, Schluss ${de(k.schluss)}\n- 21-Tage-Schnitt ${de(k.schnitt_21)}, 50-Tage-Schnitt ${de(k.schnitt_50)}, 200-Tage-Schnitt ${de(k.schnitt_200)}\n- Realisierte Vola 20 Tage (annualisiert): ${de(k.realisierte_vola_20t_pct, 1)} % (Ersatz, falls kein Volatilitätsindex gefunden wird)`);
const kv = (n, d) => d && `- ${n} (${d.stand ?? "?"}): 2J ${de(d.werte?.["2Y"])} %, 10J ${de(d.werte?.["10Y"])} %, 30J ${de(d.werte?.["30Y"])} % · Vergleich ${d.vergleich?.label ?? "-"}: 10J ${de(d.vergleich?.werte?.["10Y"])} % · 2s10s ${de(d.spread_2s10s_bp, 0)} Bp.`;
z.push("\n## Anleihen & Zinsen", kv("Bund", out.bund), kv("US-Treasury (offiziell, Vortag)", out.us_treasury), kv("US-Treasury live", out.us_treasury_live));
if (out.bund_bundesbank) { const b = out.bund_bundesbank; z.push(`- Bund laut Bundesbank (${b["10J"].tag}): 2J ${de(b["2J"].wert)} % (${vz(b["2J"].veraenderung_bp, 1)} Bp.), 10J ${de(b["10J"].wert)} % (${vz(b["10J"].veraenderung_bp, 1)} Bp.) – Ersatz, wenn die Bund-Kurve oben fehlt`); }
if (out.fed_pfad) z.push(`- Fed: EFFR ${out.fed_pfad.effr?.rate} % (Zielband ${out.fed_pfad.effr?.from}–${out.fed_pfad.effr?.to} %); ` + out.fed_pfad.sitzungen.map((s) => `${s.datum}: ${de(s.nach)} % (${vz(s.schritt_bp, 1)} Bp., ${s.wahrscheinlichkeit_25bp} % für 25 Bp. ${s.richtung})`).join("; "));
if (out.leitzinsen) z.push("- Leitzinsen: " + out.leitzinsen.zeilen.map((r) => `${r.bank} ${r.satz} % (zuletzt ${r.letzte_aenderung}, ${vz(r.um_bp, 0)} Bp.)`).join("; "));
if (out.kredit) z.push("- Kreditaufschläge: " + out.kredit.zeilen.map((r) => `${r.name} ${r.bp} Bp. (${r.date}; 1 Woche ${vz(r.chg1w, 0)}, 1 Monat ${vz(r.chg1m, 0)}; Perzentil 1 Jahr ${r.pctile})`).join("; "));
z.push("\n## Kalender (Berlin-Zeit; Quelle Nasdaq-Kalender)");
for (const r of out.kalender?.zeilen || []) z.push(`- ${r.tag} ${r.zeit_berlin ?? ""} ${r.land}: ${r.termin} — Ist ${r.ist ?? "–"} · Prognose ${r.prognose ?? "–"} · vorher ${r.vorher ?? "–"}`);
z.push("\n## US-Datenüberraschungen (letzte Veröffentlichungen)");
for (const r of (out.us_ueberraschungen?.zeilen || []).slice(0, 8)) z.push(`- ${r.tag} ${r.termin}: Ist ${r.ist} vs. Prognose ${r.prognose} (S&P ${vz(r.spx_pct)} %, US-10J ${vz(r.us10y_bp, 1)} Bp.)`);
z.push("\n## Positionierung (CFTC COT)");
for (const r of out.positionierung?.zeilen || []) z.push(`- ${r.markt} (${r.stand}): ` + Object.entries(r.gruppen).map(([g, v]) => `${g} netto ${v.netto?.toLocaleString("de-DE")} (${vz(v.veraenderung, 0)})`).join(", "));
if (out.indikation && BERICHT === "dax") z.push(`\n## DAX-Indikation (vorbörslich)\n- ${de(out.indikation.wert, 0)} (${vz(out.indikation.veraenderung_pct)} % gegen Xetra-Schluss ${de(out.indikation.gegen_schluss)}) – ${out.indikation.quellen.map((q) => `${q.quelle} ${de(q.kurs, 0)} (${q.alter_min} min alt)`).join(", ")}`);
if (out.indikation && BERICHT === "us30") z.push(`\n## Dow-Indikation\n- ${de(out.indikation.wert, 0)} (Future ${vz(out.indikation.ym_pct)} %, Stand ${out.indikation.stand}; ${out.indikation.quelle})`);
if (out.dow_werte) {
  z.push(`\n## Dow-Werte (Beitrag in Indexpunkten; Divisor ${out.dow_werte.divisor}; Summe ${vz(out.dow_werte.summe_beitrag, 0)} Punkte)`);
  for (const r of out.dow_werte.werte.slice(0, 12)) z.push(r.fehler ? `- ${r.ticker}: n/v` : `- ${r.ticker} ${r.name}: ${de(r.jetzt)} $ (${vz(r.aenderung_pct)} %, ${r.quelle}) → ${vz(r.beitrag_punkte, 0)} Punkte`);
}
if (out.dow_zahlen) z.push("\n## Quartalszahlen von Dow-Werten (nächste Tage)", ...(out.dow_zahlen.length ? out.dow_zahlen.map((r) => `- ${r.tag} ${r.ticker} (${r.wann}): EPS-Prognose ${r.eps_prognose}`) : ["- keine"]));
z.push("\n## ING THINK (neueste Artikel)");
for (const a of (out.ing_think?.artikel || []).slice(0, 8)) z.push(`- ${a.zeit} — ${a.titel} — ${a.link}`);
if (Object.keys(out.fehler).length) z.push("\n## Fehler (n/v)", ...Object.entries(out.fehler).map(([n, e]) => `- ${n}: ${e}`));
console.log(z.filter(Boolean).join("\n"));
