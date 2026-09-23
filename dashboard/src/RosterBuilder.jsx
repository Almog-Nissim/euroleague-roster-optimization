import { useState, useEffect, useMemo } from "react";
import { cname, seasonAvg, pct } from "./clubs";

/* ══════════════════════════════════════════════════════════════
   RosterBuilder — הבנאי
   קורא public/roster_sweep.json

   q          ערך המטרה החזוי. מונוטוני, 0 הפרות ב-64 מעברים.
   q_realised הנצפה — score_rows על ppm_true.
   clubs[].q  גם הוא score_rows על ppm_true → בר-השוואה ל-q_realised.
   ⛔ ולא ל-q. חזוי מול חזוי מנפח את היתרון ב-155% (fair_compare.py).
══════════════════════════════════════════════════════════════ */

const POSN = { G: "אחורי (Guard)", F: "כנף (Forward)", C: "מרכז (Center)" };
/* רצפות העמדה ב-LP מול מה שהליגה עושה בפועל (why_100, יום 8).
   רופפות פי ~2 — ולכן חמישייה של 4 אחוריים היא פתרון חוקי. */
const FLOORS = { model: { G: .163, F: .146, C: .043 },
                 real:  { G: .325, F: .255, C: .126 } };
const PRANK = { G: 0, F: 1, C: 2 };

/* מהסל החוצה: מרכז בצבע · כנפיים באגפים · אחוריים מאחור */
const SPOTS = [
  { x: 200, y: 74 },                                  // C
  { x: 100, y: 152 }, { x: 300, y: 152 },             // F
  { x: 142, y: 224 }, { x: 258, y: 224 },             // G
];

/* 🔴 v1.0: כל התצוגה ביורו הוסרה. ציר היורו נבדק ונדחה — refit_acceptance
   נכשל בשלושת השערים — ו-fit_eur נבנה ברמת מועדון.
   שלב 2, Q6: גם הגבולות lo/hi שישבו ב-meta.eur הוסרו. האזור האפור הוא
   הטווח שמועדונים אמיתיים הוציאו בפועל, נגזר בזמן ריצה מ-data.clubs —
   לא 19.5, שהיה גבול כיול היורו, ולא ערך מוקלד. */

const tc = (s) => s.split(/[\s,]+/).filter(Boolean)
  .map((w) => w[0] + w.slice(1).toLowerCase()).join(" ");
const nice = (n) => {
  if (!n || n.startsWith("#")) return "לא מזוהה";
  const [l, fst] = n.split(",").map((s) => s.trim());
  return fst ? `${tc(fst)} ${tc(l)}` : tc(n);
};
const f = (n, d = 1) => (n == null || Number.isNaN(n) ? "—" : n.toFixed(d));

export default function RosterBuilder() {
  const [data, setData] = useState(null);
  const [dash, setDash] = useState(null);
  const [season, setSeason] = useState(null);
  const [sortBy, setSortBy] = useState("gap");
  const [fail, setFail] = useState(false);
  const [i, setI] = useState(0);
  const [typed, setTyped] = useState("");

  useEffect(() => {
    fetch("/roster_sweep.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => { setData(d); setI(Math.floor((d.curve ?? d.free).length / 2)); })
      .catch(() => setFail(true));
    fetch("/dashboard_data.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        setDash(d);
        const ss = [...new Set((d.clubs || []).map((c) => c.season))];
        setSeason(Math.max(...ss));
      })
      .catch(() => {});
  }, []);

  const obsB = (data?.clubs ?? []).map((c) => c.budget);
  const OBS = obsB.length ? { lo: Math.min(...obsB), hi: Math.max(...obsB) } : null;
  /* תקציב מוצג כאחוז מהקבוצה הממוצעת בעונה של העקומה (data.clubs = עונה אחת). */
  const AVG = obsB.length ? obsB.reduce((a, b) => a + b, 0) / obsB.length : NaN;
  const P = (b) => pct(b, AVG);
  const AVGS = seasonAvg(dash?.clubs);
  // v1.0: העקומה היא המנוע של הכותרת ("curve"); "free" נשאר לקובץ הישן בלבד.
  const pts = data?.curve ?? data?.free ?? [];
  const p = pts[i];
  const prev = pts[i - 1];

  useEffect(() => { if (p) setTyped(String(P(p.budget))); }, [p?.budget, AVG]);

  const diff = useMemo(() => {
    if (!p || !prev) return { inn: [], out: [] };
    const cur = new Set(p.roster.map((r) => r.code));
    const old = new Set(prev.roster.map((r) => r.code));
    return {
      inn: p.roster.filter((r) => !old.has(r.code)),
      out: prev.roster.filter((r) => !cur.has(r.code)),
    };
  }, [p, prev]);

  // ניקוד לכל 10% תקציב נוסף (של קבוצה ממוצעת)
  const marginal = prev ? ((p.q - prev.q) / (p.budget - prev.budget)) * AVG * 0.1 : null;

  const [pick, setPick] = useState("");
  const rival = useMemo(() => {
    if (!p || !data?.clubs?.length) return null;
    if (pick) return data.clubs.find((c) => c.club === pick) ?? null;
    return data.clubs.reduce((a, b) =>
      Math.abs(b.budget - p.budget) < Math.abs(a.budget - p.budget) ? b : a);
  }, [p, data, pick]);
  const bGap = rival ? Math.abs(rival.budget - p.budget) : 0;

  const snap = (v) => {
    if (Number.isNaN(v)) return setTyped(String(P(p.budget)));
    v = (v / 100) * AVG;              // הקלט באחוזים, העקומה ביחידות פנימיות
    setI(pts.reduce((best, d, k) =>
      Math.abs(d.budget - v) < Math.abs(pts[best].budget - v) ? k : best, 0));
  };

  if (fail) return <Fail />;
  if (!data) return <div style={{ padding: 60, color: "#8894AC" }}>טוען…</div>;

  /* חמישייה מוצעת: 2G · 2F · 1C, המובילים בדקות בכל עמדה.
     ⚠️ המנוע מקצה דקות ואינו מרכיב חמישיות — זו תוספת של הממשק.
     אם חסר בעמדה, מושלם מהנותרים לפי דקות. */
  const byMin = [...p.roster].sort((a, b) => b.minutes - a.minutes);
  const five = (() => {
    const need = { C: 1, F: 2, G: 2 };
    const out = [];
    for (const pos of ["C", "F", "G"])
      out.push(...byMin.filter((r) => r.pos === pos).slice(0, need[pos]));
    if (out.length < 5) {
      const have = new Set(out.map((r) => r.code));
      out.push(...byMin.filter((r) => !have.has(r.code)).slice(0, 5 - out.length));
    }
    return out.sort((a, b) => PRANK[b.pos] - PRANK[a.pos] || b.minutes - a.minutes)
      .slice(0, 5);
  })();
  const fiveSet = new Set(five.map((r) => r.code));
  const bench = p.roster.filter((r) => !fiveSet.has(r.code))
    .sort((a, b) => b.minutes - a.minutes);
  const idle = p.roster.filter((r) => r.minutes < 0.5);

  const W = 780, H = 260, L = 46, R = 16, T = 22, B = 40;
  const vals = pts.flatMap((d) => [d.q, d.q_realised]);
  const lo = Math.floor(Math.min(...vals) / 10) * 10;
  const hi = Math.ceil(Math.max(...vals) / 10) * 10;
  const X = (b) => L + ((b - pts[0].budget) /
    (pts[pts.length - 1].budget - pts[0].budget)) * (W - L - R);
  const Y = (v) => H - B - ((v - lo) / (hi - lo)) * (H - T - B);
  const line = (k) => pts.map((d, n) =>
    `${n ? "L" : "M"}${X(d.budget).toFixed(1)},${Y(d[k]).toFixed(1)}`).join("");
  const band = line("q") + pts.slice().reverse()
    .map((d) => `L${X(d.budget).toFixed(1)},${Y(d.q_realised).toFixed(1)}`).join("") + "Z";
  const sat = data.meta.saturation;

  return (
    <div dir="rtl" className="rb">
      <style>{CSS}</style>

      <header className="hd">
        <div className="eyebrow">
          יורוליג {data.meta.label} · מאגר {data.meta.pool_size} שחקנים
        </div>
        <h1>איזו קבוצה אפשר לבנות<br />עם התקציב שלך?</h1>

        <div className="ctl">
          <div className="budget">
            <input className="bnum" type="number" value={typed}
              min={P(data.meta.b_lo)} max={P(data.meta.b_hi)} step={5}
              onChange={(e) => setTyped(e.target.value)}
              onBlur={() => snap(parseFloat(typed))}
              onKeyDown={(e) => e.key === "Enter" && snap(parseFloat(typed))}
              aria-label="תקציב" />
            <span className="bunit">
              % מהתקציב של קבוצה ממוצעת
              {OBS && (p.budget < OBS.lo || p.budget > OBS.hi) && (
                <em className="oob">אף קבוצה לא הוציאה סכום כזה, אז זו רק הערכה</em>
              )}
            </span>
          </div>
          <input className="slider" type="range" min={0} max={pts.length - 1}
            value={i} onChange={(e) => setI(+e.target.value)}
            aria-label="סליידר תקציב" />
        </div>

        <div className="kpihead">מה יוצא מהתקציב הזה</div>
        <div className="kpis">
          <Kpi v={f(p.q)} l="תפוקה צפויה" c="pred"
            h="מה שהמודל ציפה מהסגל הזה לפני העונה" />
          <Kpi v={f(p.q_realised)} l="תפוקה בפועל" c="real"
            h="מה שאותם שחקנים באמת עשו באותה עונה" />
          <Kpi v={marginal == null ? "—" : `+${f(marginal, 2)}`}
            l="מה קונים 10% נוספים" c={marginal != null && marginal < 0.5 ? "dim" : ""}
            h="כמה תפוקה מוסיפה הגדלת התקציב ב-10%" />
          <Kpi v={`${f((p.unspent / AVG) * 100, 1)}%`} l="תקציב שלא נוצל" c="dim"
            h="מה שנשאר אחרי שנקנו 12 השחקנים" />
        </div>
      </header>

      <section className="panel">
        <div className="ph">
          <h2>הסגל</h2>
          <span className="sub">
            חמישייה משוערת: 2 אחוריים, 2 כנפיים ומרכז · הוצאו {P(p.spent)}% מתוך {P(p.budget)}%
          </span>
        </div>

        <div className="courtwrap">
          <svg viewBox="0 0 400 300" className="court">
            <path d="M60 10 L60 88 A140 140 0 0 0 340 88 L340 10" className="cline" fill="none" />
            <rect x="160" y="10" width="80" height="96" className="cline" fill="none" />
            <circle cx="200" cy="106" r="36" className="cline" fill="none" />
            <line x1="176" y1="22" x2="224" y2="22" className="choop" />
            <circle cx="200" cy="34" r="8" className="choop" fill="none" />
            {five.map((r, k) => (
              <g key={r.code} transform={`translate(${SPOTS[k].x},${SPOTS[k].y})`}
                className={diff.inn.some((x) => x.code === r.code) ? "pl in" : "pl"}>
                <circle r="23" className={`pdot p${r.pos}`} />
                <text y="6" className="pnum">{f(r.minutes, 0)}</text>
                <text y="41" className="pname">{nice(r.name)}</text>
                <text y="55" className="pcost" direction="ltr">
                  {/* 🔴 v1.0: הוסר יורו לשחקן. fit_eur נבנה ברמת מועדון, ואצל
                      שחקן אחד הוא הציג סכום שלילי. תוכנית הסגירה, סעיף 2. */}
                  {r.pos}
                </text>
              </g>
            ))}
          </svg>
        </div>

        <div className="benchhead">
          <span>ספסל</span><span></span><span>דקות</span>
          <span className="bh-n">דק׳</span><span className="bh-n">מהתקציב</span>
        </div>
        <ol className="bench">
          {bench.map((r) => (
            <li key={r.code} className={"bl" + (r.minutes < 0.5 ? " idle" : "") +
              (diff.inn.some((x) => x.code === r.code) ? " in" : "")}>
              <span className={`chip p${r.pos}`} title={POSN[r.pos]}>{r.pos}</span>
              <span className="bname">
                {nice(r.name)}
              </span>
              <span className="bbar"><i style={{ width: `${(r.minutes / 32) * 100}%` }} /></span>
              <span className="bmin">{f(r.minutes, 0)}׳</span>
              <span className="bcost" title="אחוז מהתקציב של קבוצה ממוצעת">{f((r.cost / AVG) * 100, 1)}%</span>
            </li>
          ))}
        </ol>

        {idle.length > 0 && (
          <p className="note">
            המנוע מתכנן דקות ל<b>משחק ממוצע אחד</b>, ולכן <b>{idle.length}</b>{" "}
            שחקנים לא מקבלים דקות בכלל. זה בסדר, בכל סגל של 12 יש מי שלא
            משחק. מה שהמנוע לא רואה הוא את הערך של שחקן כזה כשמישהו מהחמישייה
            נפצע.
          </p>
        )}

        <p className="note">
          שחקן שמופיע כמעט בכל תקציב הוא "מציאה" לפי מודל המחיר. חלק מהם
          באמת זולים ביחס למה שהם נותנים, וחלק פשוט מתומחרים נמוך מדי: המודל
          רואה רק את הביצועים והוותק ביורוליג, לא עבר ב-NBA או שם גדול.
        </p>

        {(diff.inn.length > 0 || diff.out.length > 0) && (
          <div className="diff">
            <span className="dlbl">לעומת {P(prev.budget)}%</span>
            {diff.out.map((r) => <span key={r.code} className="tag out">{nice(r.name)}</span>)}
            {diff.inn.map((r) => <span key={r.code} className="tag in">{nice(r.name)}</span>)}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="ph">
          <h2>מה המנוע חשב, ומה קרה</h2>
          <span className="legend"><i className="lk pred" />חזוי<i className="lk real" />בפועל</span>
        </div>

        <svg viewBox={`0 0 ${W} ${H}`} className="chart">
          <defs>
            <pattern id="hx" width="7" height="7" patternTransform="rotate(45)"
              patternUnits="userSpaceOnUse"><line y2="7" className="hxl" /></pattern>
          </defs>
          {/* Q6: מחוץ לטווח התקציבים שנצפה — אקסטרפולציה. טקסטורה, לא רק צבע. */}
          {OBS && pts.length > 1 &&
            [[pts[0].budget, OBS.lo], [OBS.hi, pts[pts.length - 1].budget]]
              .filter(([a, b]) => b > a)
              .map(([a, b]) => (
                <g key={a}>
                  <rect x={X(a)} y={T} width={X(b) - X(a)} height={H - B - T}
                    fill="url(#hx)" className="xtra" />
                  {/* תווית רק לפס רחב דיו; פס צר (למשל 25.26–26) נשאר
                      עם הטקסטורה בלבד, והתווית לא גולשת מהתרשים. */}
                  {X(b) - X(a) > 90 && (
                    <text x={(X(a) + X(b)) / 2} y={H - B - 8} className="ax"
                      textAnchor="middle">אף קבוצה לא הוציאה כך</text>)}
                </g>))}
          {[lo, Math.round((lo + hi) / 2), hi].map((v) => (
            <g key={v}>
              <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} className="grid" />
              <text x={L - 8} y={Y(v) + 4} className="ax">{v}</text>
            </g>
          ))}
          {data.clubs.map((c) => (
            <line key={c.club} x1={X(c.budget)} x2={X(c.budget)}
              y1={H - B} y2={H - B + 6} className="tick" />
          ))}
          {sat && (
            <>
              <line x1={X(sat)} x2={X(sat)} y1={T} y2={H - B} className="sat" />
              {/* בדף RTL, text-anchor:end מצמיח את הטקסט ימינה — ובעקומת v1.0
                  הרוויה (26) יושבת בדיוק בקצה הימני, אז התווית חרגה מהתרשים.
                  start ב-RTL מצמיח שמאלה, אל תוך התרשים. */}
              <text x={X(sat) - 7} y={T + 10} className="satl"
                direction="rtl" style={{ textAnchor: "start" }}>מכאן הכסף כמעט מפסיק לקנות</text>
            </>
          )}
          <path d={band} fill="url(#hx)" />
          <path d={line("q")} className="lpred" fill="none" />
          <path d={line("q_realised")} className="lreal" fill="none" />
          <line x1={X(p.budget)} x2={X(p.budget)} y1={T} y2={H - B} className="cur" />
          <circle cx={X(p.budget)} cy={Y(p.q)} r="5" className="dpred" />
          <circle cx={X(p.budget)} cy={Y(p.q_realised)} r="4" className="dreal" />
          {[pts[0].budget, sat, pts[pts.length - 1].budget].filter(Boolean).map((b) => (
            <text key={b} x={X(b)} y={H - 12} className="ax mid">{P(b)}%</text>
          ))}
          <text x={(L + W - R) / 2} y={H - 1} className="ax mid dimx">
            תקציב (100% = קבוצה ממוצעת) · כל קו קטן הוא מועדון אמיתי
          </text>
        </svg>

        <p className="note">
          בתקציב הזה המנוע ציפה ל-<b className="real">{f(p.optimism ?? p.q - p.q_realised)}</b>{" "}
          נקודות יותר ממה שקרה בפועל. הפער גדול בתקציבים נמוכים וקטן
          בגבוהים: כשאין כסף הוא קונה שחקנים זולים, ועליהם התחזית הכי פחות
          מדויקת.
        </p>
      </section>

      {rival && (
        <section className="panel">
          <div className="ph">
            <h2>מול קבוצה אמיתית</h2>
            <select className="sel" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">הקרובה בתקציב</option>
              {[...data.clubs].sort((a, b) => b.budget - a.budget).map((c) => (
                <option key={c.club} value={c.club}>
                  {cname(c.club)} · {P(c.budget)}%
                </option>
              ))}
            </select>
          </div>
          {bGap > 1.5 && (
            <p className="alert">
              ⚠️ לשני הצדדים יש תקציבים שונים (פער של {P(bGap)}%), אז זו לא השוואה
              הוגנת.{" "}
              <button className="lnk" onClick={() => snap(rival.budget)}>
                השוו באותו תקציב
              </button>
            </p>
          )}
          <div className="vs">
            <div className="vsc">
              <span className="vsname">{cname(rival.club)}</span>
              <span className="vsn">{f(rival.q)}</span>
              <span className="vsl">
                תקציב <span dir="ltr">{P(rival.budget)}%</span> · {rival.n} שחקנים
              </span>
            </div>
            <div className="vsgap">
              <span className={p.q_realised >= rival.q ? "up" : "down"}>
                {p.q_realised >= rival.q ? "+" : ""}{f(p.q_realised - rival.q)}
              </span>
              <span className="vsl">הפרש</span>
            </div>
            <div className="vsc">
              <span className="vsname">המנוע</span>
              <span className="vsn pred">{f(p.q_realised)}</span>
              <span className="vsl">תקציב <span dir="ltr">{P(p.budget)}%</span> · {p.n} שחקנים</span>
            </div>
          </div>
          <p className="note">
שני הצדדים נמדדים לפי <b>מה שקרה בפועל</b>, ולא לפי תחזית. אילו
            היינו משווים תחזית של המנוע לתחזית של הקבוצה, היתרון היה מנופח
            בכ-12 נקודות אחוז. בגלל שההשוואה הוגנת, המנוע יכול גם להפסיד:
            בתקציבים נמוכים הוא קונה שחקנים זולים, ודווקא עליהם התחזית הכי
            פחות מדויקת.
          </p>
        </section>
      )}

      {dash?.clubs?.length > 0 && (() => {
        const seasons = [...new Set(dash.clubs.map((c) => c.season))].sort();
        const shown = season === "all" ? dash.clubs
          : dash.clubs.filter((c) => c.season === season);
        const rows = shown
          .map((c) => ({ ...c, gap: c.q_engine - c.q_club }))
          .sort((a, b) => sortBy === "gap" ? b.gap - a.gap
            : sortBy === "budget" ? b.budget - a.budget
            : b.q_club - a.q_club);

        /* דמבל: קו אחד למועדון, שתי נקודות — v1.0 / ADR 0006: המועדון על
           מה ששיחק, המנוע של הכותרת על התוכנית שלו. שתיהן על ppm_true.
           (אקראי / מאולץ / חופשי היו בקונבנציה הישנה והוסרו.) */
        const vals = rows.flatMap((c) => [c.q_club, c.q_engine]);
        const nWin = rows.filter((c) => c.gap > 0).length;
        const lo = Math.floor(Math.min(...vals) / 10) * 10;
        const hi = Math.ceil(Math.max(...vals) / 10) * 10;
        const RW = 720, LB = 74, RB = 18, ROW = 26, TOP = 26;
        const RH = TOP + rows.length * ROW + 14;
        const px = (v) => LB + ((v - lo) / (hi - lo)) * (RW - LB - RB);
        const py = (i) => TOP + i * ROW + ROW / 2;

        return (
          <section className="panel">
            <div className="ph">
              <h2>המנוע מול כל הקבוצות</h2>
              <span className="tabs">
                {seasons.map((s) => (
                  <button key={s} className={"tb" + (s === season ? " on" : "")}
                    onClick={() => setSeason(s)}>{s}/{(s + 1) % 100}</button>
                ))}
                <button className={"tb" + (season === "all" ? " on" : "")}
                  onClick={() => setSeason("all")}>שתיהן</button>
              </span>
            </div>

            <div className="lgnd">
              <span><i className="d club" />המועדון, כפי ששיחק</span>
              <span><i className="d free" />המנוע, התוכנית שלו</span>
            </div>

            <div className="tblwrap">
              <svg viewBox={`0 0 ${RW} ${RH}`} className="dumb"
                style={{ minWidth: 560 }}>
                {[lo, Math.round((lo + hi) / 2), hi].map((v) => (
                  <g key={v}>
                    <line x1={px(v)} x2={px(v)} y1={TOP - 6} y2={RH - 12}
                      className="gy" />
                    <text x={px(v)} y={TOP - 12} className="gt">{v}</text>
                  </g>
                ))}
                {rows.map((c, i) => {
                  const a = Math.min(c.q_club, c.q_engine);
                  const b = Math.max(c.q_club, c.q_engine);
                  return (
                    <g key={c.club + c.season}
                      className={c.club === rival?.club ? "dr on" : "dr"}>
                      <rect x="0" y={py(i) - ROW / 2} width={RW} height={ROW}
                        className="dbg" />
                      <text x={LB - 10} y={py(i) + 4} className="dlab">
                        {c.club}{season === "all" ? ` ${c.season % 100}` : ""}
                      </text>
                      <line x1={px(a)} x2={px(b)} y1={py(i)} y2={py(i)}
                        className="dline" />
                      <circle cx={px(c.q_club)} cy={py(i)} r="5" className="club" />
                      <circle cx={px(c.q_engine)} cy={py(i)} r="5.5" className="free" />
                      <title>
                        {`${c.club} ${c.season} · מועדון ${f(c.q_club)} · מנוע ${f(c.q_engine)} · פער ${f(c.gap)}`}
                      </title>
                    </g>
                  );
                })}
              </svg>
            </div>

            <p className="note">
              כל שורה היא קבוצה עם התקציב האמיתי שלה, ושתי הנקודות הן מה שקרה
              בפועל. המנוע מימין לקבוצה ב-<b>{nWin} מתוך {rows.length}</b>. המנוע
              נמדד לפי התוכנית שקבע לפני העונה, כולל המחיר של שחקנים שנפצעו,
              והקבוצה לפי מה שהיא באמת שיחקה.
            </p>

            <details className="det">
              <summary>הצג נתונים מלאים</summary>
              <div className="tblwrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th onClick={() => setSortBy("q")} className="clk">קבוצה</th>
                      {season === "all" && <th>עונה</th>}
                      <th onClick={() => setSortBy("budget")} className="clk num">תקציב</th>
                      <th className="num">הקבוצה</th>
                      <th className="num">המנוע</th>
                      <th onClick={() => setSortBy("gap")} className="clk num">פער</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((c) => (
                      <tr key={c.club + c.season}
                        className={c.club === rival?.club ? "hl" : ""}>
                        <td><b>{cname(c.club)}</b></td>
                        {season === "all" && <td className="num">{c.season}</td>}
                        <td className="num" dir="ltr">{pct(c.budget, AVGS[c.season])}%</td>
                        <td className="num">{f(c.q_club)}</td>
                        <td className="num predc">{f(c.q_engine)}</td>
                        <td className={"num " + (c.gap >= 0 ? "up" : "down")}>
                          {c.gap >= 0 ? "+" : ""}{f(c.gap)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </section>
        );
      })()}

      <footer>
        המנוע תמיד בונה סגל של 12 שחקנים, המינימום שמותר, בכל תקציב. התקציב
        מוצג כאחוז מהתקציב של קבוצה ממוצעת באותה עונה (100% זה ממוצע). אין
        כאן יורו בכוונה: ניסינו שלוש דרכים סבירות לתרגם ליורו, והן נתנו
        תשובות רחוקות מדי זו מזו.
      </footer>
    </div>
  );
}

const Kpi = ({ v, l, c, h }) => (
  <div className="kpi">
    <span className={`kv ${c || ""}`}>{v}</span>
    <span className="kl">{l}</span>
    {h && <span className="kh">{h}</span>}
  </div>
);
const Fail = () => (
  <div dir="rtl" style={{ padding: 60, fontFamily: "system-ui", color: "#E9EDF5",
    background: "#0E1420", minHeight: "100vh" }}>
    <h2>roster_sweep.json לא נמצא</h2>
    <p style={{ color: "#8894AC" }}>העתק אותו אל <code>dashboard/public/</code> ורענן.</p>
  </div>
);

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Secular+One&family=Assistant:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
.rb{--bg:#0E1420;--pan:#141C2B;--ln:#26314A;--tx:#E9EDF5;--dim:#8894AC;
 --pred:#5AA9FF;--real:#F2A13C;
 background:var(--bg);color:var(--tx);min-height:100vh;
 font-family:'Assistant',system-ui,sans-serif;
 padding:clamp(16px,4vw,52px);max-width:960px;margin:0 auto;}
.rb h1{font-family:'Secular One',sans-serif;font-size:clamp(32px,6vw,58px);
 line-height:1.06;margin:6px 0 34px;font-weight:400;}
.rb h2{font-size:14px;letter-spacing:.04em;margin:0;font-weight:700;}
.eyebrow{font-size:12px;letter-spacing:.16em;color:var(--dim);}
.hd{border-bottom:1px solid var(--ln);padding-bottom:30px;margin-bottom:30px;}
.ctl{display:flex;align-items:center;gap:26px;flex-wrap:wrap;}
.budget{display:flex;align-items:baseline;gap:7px;}
.bnum{font-family:'IBM Plex Mono',monospace;font-size:44px;font-weight:600;
 width:148px;background:transparent;border:none;border-bottom:2px solid var(--pred);
 color:var(--tx);padding:0 4px 4px;text-align:center;}
.bnum:focus{outline:none;border-bottom-color:var(--real);}
.bunit{font-size:10.5px;letter-spacing:.1em;color:var(--dim);
 display:flex;flex-direction:column;align-items:flex-start;gap:3px;}
.eur{font-family:'IBM Plex Mono',monospace;font-size:14px;color:var(--tx);
 font-weight:600;letter-spacing:0;white-space:nowrap;}
.eur .pm{color:var(--dim);font-size:11px;font-weight:400;}
.oob{font-style:normal;font-size:10px;color:var(--real);}
.bpos{font-style:normal;font-size:10.5px;color:var(--dim);
 font-weight:400;margin-inline-start:7px;}
.slider{flex:1;min-width:220px;-webkit-appearance:none;appearance:none;
 background:transparent;height:24px;}
.slider::-webkit-slider-runnable-track{height:3px;background:var(--ln);border-radius:2px;}
.slider::-moz-range-track{height:3px;background:var(--ln);border-radius:2px;}
.slider::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;margin-top:-10px;
 border-radius:50%;background:var(--pred);border:3px solid var(--bg);cursor:grab;}
.slider::-moz-range-thumb{width:22px;height:22px;border-radius:50%;background:var(--pred);
 border:3px solid var(--bg);cursor:grab;}
.slider:focus-visible{outline:2px solid var(--real);outline-offset:6px;}
.kpihead{font-size:11px;letter-spacing:.14em;color:var(--dim);
 margin:30px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--ln);}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:0;}
.kpi{display:grid;grid-template-rows:auto auto 1fr;gap:4px;
 padding:2px 16px;border-inline-start:1px solid var(--ln);max-width:none;}
.kpi:first-child{border-inline-start:none;padding-inline-start:0;}
.kv{font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:600;
 display:block;line-height:1;}
.kv.pred{color:var(--pred);}.kv.real{color:var(--real);}.kv.dim{color:var(--dim);}
.kl{font-size:12.5px;color:var(--tx);font-weight:600;line-height:1.2;}
.kh{font-size:10.5px;color:var(--dim);line-height:1.5;}
.sel{background:var(--bg);color:var(--tx);border:1px solid var(--ln);
 border-radius:3px;font-family:'Assistant',sans-serif;font-size:12px;padding:4px 8px;}
.alert{font-size:12px;color:var(--real);background:rgba(242,161,60,.08);
 border:1px solid rgba(242,161,60,.3);border-radius:3px;padding:8px 11px;
 margin:0 0 12px;line-height:1.6;}
.lnk{background:none;border:none;color:var(--pred);font:inherit;
 cursor:pointer;text-decoration:underline;padding:0 4px;}
.tabs{display:flex;gap:4px;}
.tb{background:none;border:1px solid var(--ln);color:var(--dim);border-radius:3px;
 font:inherit;font-size:11.5px;padding:3px 10px;cursor:pointer;}
.tb.on{border-color:var(--pred);color:var(--pred);}
.tblwrap{overflow-x:auto;}
.lgnd{display:flex;gap:18px;flex-wrap:wrap;font-size:11.5px;color:var(--dim);
 margin-bottom:10px;}
.lgnd span{display:flex;align-items:center;gap:6px;}
.lgnd .d{width:9px;height:9px;border-radius:50%;display:inline-block;}
.dumb{width:100%;height:auto;}
.dumb .gy{stroke:var(--ln);stroke-width:1;}
.dumb .gt{font-family:'IBM Plex Mono',monospace;font-size:9.5px;
 fill:var(--dim);text-anchor:middle;}
.dumb .dbg{fill:transparent;}
.dumb .dr:hover .dbg{fill:rgba(90,169,255,.06);}
.dumb .dr.on .dbg{fill:rgba(90,169,255,.1);}
.dumb .dlab{font-family:'IBM Plex Mono',monospace;font-size:10.5px;
 fill:var(--tx);text-anchor:end;}
.dumb .dline{stroke:var(--ln);stroke-width:2;}
.d.rand,.dumb .rand{background:#5A6478;fill:#5A6478;}
.d.club,.dumb .club{background:var(--tx);fill:var(--tx);}
.d.cap,.dumb .cap{background:var(--real);fill:var(--real);}
.d.free,.dumb .free{background:var(--pred);fill:var(--pred);}
.det{margin-top:16px;}
.det summary{font-size:12px;color:var(--dim);cursor:pointer;
 padding:8px 0;border-top:1px solid var(--ln);}
.det summary:hover{color:var(--pred);}
.tbl{width:100%;border-collapse:collapse;font-size:13px;}
.tbl th{font-size:10.5px;color:var(--dim);font-weight:600;text-align:start;
 padding:0 8px 8px;border-bottom:1px solid var(--ln);white-space:nowrap;}
.tbl th.clk{cursor:pointer;}
.tbl th.clk:hover{color:var(--pred);}
.tbl td{padding:6px 8px;border-bottom:1px solid var(--ln);}
.tbl .num{font-family:'IBM Plex Mono',monospace;text-align:end;}
.tbl tr.hl{background:rgba(90,169,255,.08);}
.tbl .predc{color:var(--pred);}
.tbl .dimc{color:var(--dim);}
.tbl .up{color:var(--pred);}
.tbl .down{color:var(--real);}
.panel{background:var(--pan);border:1px solid var(--ln);border-radius:3px;
 padding:20px clamp(14px,3vw,26px);margin-bottom:22px;}
.ph{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
 border-bottom:1px solid var(--ln);padding-bottom:10px;margin-bottom:16px;flex-wrap:wrap;}
.sub,.legend{font-size:12px;color:var(--dim);display:flex;align-items:center;gap:6px;}
.lk{width:16px;height:2px;display:inline-block;margin-inline-start:8px;}
.lk.pred{background:var(--pred);}.lk.real{background:var(--real);}
.courtwrap{max-width:430px;margin:0 auto;}
.court{width:100%;height:auto;overflow:visible;}
.cline{stroke:var(--ln);stroke-width:1.5;}
.choop{stroke:var(--real);stroke-width:2.4;fill:none;stroke-linecap:round;}
.pdot{stroke:var(--bg);stroke-width:2.5;}
.pG{fill:#5AA9FF;}.pF{fill:#8B93F0;}.pC{fill:#F2A13C;}
.pnum{font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;
 fill:#0E1420;text-anchor:middle;}
.pname{font-size:11.5px;fill:var(--tx);text-anchor:middle;font-weight:600;}
.pcost{font-size:9.5px;fill:var(--dim);text-anchor:middle;}
.pl.in .pdot{animation:pop .45s ease;}
@keyframes pop{from{transform:scale(.4);opacity:0}to{transform:scale(1);opacity:1}}
.benchhead{display:grid;grid-template-columns:24px 1fr 90px 40px 46px;gap:10px;
 margin-top:26px;padding-bottom:7px;border-bottom:1px solid var(--ln);
 font-size:10px;letter-spacing:.12em;color:var(--dim);}
.benchhead .bh-n{text-align:end;}
.bench{list-style:none;margin:0;padding:0;}
.bl{display:grid;grid-template-columns:24px 1fr 90px 40px 46px;gap:10px;
 align-items:center;padding:6px 0;border-bottom:1px solid var(--ln);font-size:13.5px;}
.bl.idle{opacity:.42;}
.bl.in{background:rgba(90,169,255,.09);}
.chip{font-size:10.5px;font-weight:700;text-align:center;border-radius:2px;
 color:#0E1420;padding:2px 0;}
.bname{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.bbar{height:5px;background:var(--ln);border-radius:3px;overflow:hidden;}
.bbar i{display:block;height:100%;background:var(--dim);}
.bmin,.bcost{font-family:'IBM Plex Mono',monospace;font-size:11.5px;
 color:var(--dim);text-align:end;}
.note{font-size:12.5px;line-height:1.7;color:var(--dim);margin:14px 0 0;max-width:640px;}
.note b{color:var(--tx);}.note b.real{color:var(--real);}
.diff{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:14px;}
.dlbl{font-size:11px;color:var(--dim);}
.tag{font-size:11.5px;padding:3px 9px;border-radius:2px;border:1px solid;}
.tag.in{border-color:var(--pred);color:var(--pred);}
.tag.out{border-color:var(--ln);color:var(--dim);text-decoration:line-through;}
.chart{width:100%;height:auto;}
.grid{stroke:var(--ln);stroke-width:1;}
.ax{font-family:'IBM Plex Mono',monospace;font-size:10px;fill:var(--dim);text-anchor:end;}
.ax.mid{text-anchor:middle;}
.ax.dimx{font-family:'Assistant',sans-serif;font-size:9.5px;opacity:.7;}
.tick{stroke:var(--dim);stroke-width:1.5;opacity:.55;}
.sat{stroke:var(--real);stroke-width:1;stroke-dasharray:3 4;opacity:.7;}
.satl{font-size:10px;fill:var(--real);text-anchor:end;}
.hxl{stroke:var(--real);stroke-width:1;opacity:.3;}
.lpred{stroke:var(--pred);stroke-width:2.4;}
.lreal{stroke:var(--real);stroke-width:1.6;stroke-dasharray:2 4;stroke-linecap:round;}
.cur{stroke:var(--tx);stroke-width:1;opacity:.45;}
.dpred{fill:var(--pred);}.dreal{fill:var(--real);}
.vs{display:flex;align-items:center;justify-content:space-around;gap:14px;
 text-align:center;padding:8px 0;flex-wrap:wrap;}
.vsc{display:flex;flex-direction:column;gap:3px;min-width:120px;}
.vsname{font-size:13px;font-weight:700;letter-spacing:.06em;}
.vsn{font-family:'IBM Plex Mono',monospace;font-size:32px;font-weight:600;}
.vsn.pred{color:var(--pred);}
.vsl{font-size:11px;color:var(--dim);}
.vsgap span:first-child{font-family:'IBM Plex Mono',monospace;font-size:20px;
 font-weight:600;display:block;}
.vsgap .up{color:var(--pred);}.vsgap .down{color:var(--real);}
.rb footer{font-size:11.5px;line-height:1.75;color:var(--dim);
 border-top:1px solid var(--ln);padding-top:16px;max-width:640px;}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}
@media (max-width:720px){.kpis{grid-template-columns:1fr 1fr;gap:18px 0;}
 .kpi:nth-child(3){border-inline-start:none;padding-inline-start:0;}}
@media (max-width:560px){.bl,.benchhead{grid-template-columns:22px 1fr 44px 42px;}
 .benchhead span:nth-child(3){display:none;}
 .bbar{display:none;}.kv{font-size:22px;}}
`;
