import { useState, useEffect, useMemo } from "react";
import { seasonAvg, pct } from "./clubs";

/* ══════════════════════════════════════════════════════════════
   EngineVsReality — "מנוע מול מציאות"
   public/dashboard_data.json

   ⚠️ כל הערכים כאן על ppm_true — **נצפים**. השוואת ערכים חזויים
      משני הצדדים מנפחת את יתרון המנוע ב-155% (fair_compare.py).

   כל סעיף עונה על שאלה אחת. זו לא החלטה עיצובית אלא הכרחית:
   ארבע נקודות באותו גרף הפכו את הדמבל לפיזור חסר משמעות.

   ⚠️ יום 14: סעיף 01 (המנוע מול כל המועדונים) מוסתר ב-{false && }
      ולא נמחק. randBeats/engBeats נשארים מחושבים למקרה שיוחזר.
══════════════════════════════════════════════════════════════ */

const f = (n, d = 1) => (n == null || Number.isNaN(n) ? "—" : n.toFixed(d));
const pctf = (n) => `${(n * 100).toFixed(0)}%`;

export default function EngineVsReality() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [season, setSeason] = useState("all");
  const [sort, setSort] = useState("gap");

  useEffect(() => {
    fetch("/dashboard_data.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then(setD)
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  const avgs = useMemo(() => seasonAvg(d?.clubs), [d]);
  const rows = useMemo(() => {
    if (!d?.clubs) return [];
    return d.clubs
      .filter((c) => season === "all" || c.season === season)
      .map((c) => ({
        ...c,
        // v1.0 (ADR 0006): המנוע של הכותרת על התוכנית שלו, מול המועדון
        // על מה ששיחק. q_free / q_cap / q_rand היו בקונבנציה הישנה.
        gEng: c.q_engine - c.q_club,
        bp: pct(c.budget, avgs[c.season]),   // תקציב כאחוז מהממוצע בעונה
      }))
      .sort((a, b) => sort === "budget" ? b.budget - a.budget
        : sort === "club" ? a.club.localeCompare(b.club)
        : b.gEng - a.gEng);
  }, [d, season, sort]);

  if (err) return <Shell><p className="fail">dashboard_data.json — {err}</p></Shell>;
  if (!d) return <Shell><p className="load">טוען…</p></Shell>;

  const seasons = [...new Set(d.clubs.map((c) => c.season))].sort();
  const randBeats = rows.filter((r) => r.gRand > 0).length;
  const engBeats = rows.filter((r) => r.gEng > 0).length;

  /* ── גאומטריה: עמודות מתפצלות ── */
  const W = 760, LB = 52, RB = 54, ROW = 30, TOP = 34;
  const HT = TOP + rows.length * ROW + 16;
  const span = Math.max(...rows.flatMap((r) =>
    [Math.abs(r.gEng), Math.abs(r.gRand ?? 0)])) * 1.06;
  const MID = LB + (W - LB - RB) * 0.34;      // אפס לא במרכז: הצד החיובי ארוך
  const sx = (v) => MID + (v / span) * (v >= 0 ? (W - RB - MID) : (MID - LB));

  /* ── פיזור: תקציב מול פער ── */
  const SW = 760, SH = 250, SL = 52, SR = 20, ST = 20, SB = 42;
  const bx = rows.map((r) => r.bp);
  const gy = rows.map((r) => r.gEng);
  const bLo = Math.floor(Math.min(...bx) / 5) * 5, bHi = Math.ceil(Math.max(...bx) / 5) * 5;
  const gLo = Math.floor(Math.min(...gy) / 5) * 5, gHi = Math.ceil(Math.max(...gy) / 5) * 5;
  const px = (v) => SL + ((v - bLo) / (bHi - bLo)) * (SW - SL - SR);
  const py = (v) => SH - SB - ((v - gLo) / (gHi - gLo)) * (SH - ST - SB);
  const mx = bx.reduce((a, b) => a + b, 0) / bx.length;
  const my = gy.reduce((a, b) => a + b, 0) / gy.length;
  const cov = bx.reduce((s, v, i) => s + (v - mx) * (gy[i] - my), 0);
  const vx = bx.reduce((s, v) => s + (v - mx) ** 2, 0);
  const slope = vx ? cov / vx : 0;
  const rr = cov / Math.sqrt(vx * gy.reduce((s, v) => s + (v - my) ** 2, 0));

  return (
    <Shell>
      <header className="top">
        <div className="eyebrow">
          {d.benchmark.n} קבוצות ועונות · הכול לפי מה שקרה בפועל
        </div>
        <h1>מנוע מול מציאות</h1>
        <div className="ctrls">
          <span className="tabs">
            {seasons.map((s) => (
              <button key={s} className={"tb" + (s === season ? " on" : "")}
                onClick={() => setSeason(s)}>{s}/{(s + 1) % 100}</button>
            ))}
            <button className={"tb" + (season === "all" ? " on" : "")}
              onClick={() => setSeason("all")}>שתיהן</button>
          </span>
          <span className="tabs">
            {[["gap", "לפי פער"], ["budget", "לפי תקציב"], ["club", "א״ב"]].map(
              ([k, l]) => (
                <button key={k} className={"tb" + (sort === k ? " on" : "")}
                  onClick={() => setSort(k)}>{l}</button>
              ))}
          </span>
        </div>
      </header>

      {/* ═══ 1 — מוסתר, יום 14 ═══ */}
      {false && (
      <section className="q">
        <div className="qh">
          <span className="qn">01</span>
          <div>
            <h2>האם היתרון מגיע מהמודל, או רק ממבנה האילוצים?</h2>
            <p className="qs">
              כל עמודה נמדדת ביחס לסגל האמיתי של אותו מועדון (הקו האנכי).
              ימינה — טוב יותר מהמועדון. שמאלה — גרוע יותר.
              <b> סגל אקראי</b> הוגרל מאותו מאגר תחת אותם אילוצים בדיוק:
              12 שחקנים, רצפות עמדה, תקרת דקות, אותו תקציב.
            </p>
          </div>
        </div>

        <div className="lgnd">
          <span><i className="sw rand" />סגל אקראי</span>
          <span><i className="sw free" />המנוע</span>
        </div>

        <div className="scroll">
          <svg viewBox={`0 0 ${W} ${HT}`} className="viz" style={{ minWidth: 620 }}>
            {[-span * 0.5, 0, span * 0.5].map((v) => (
              <g key={v}>
                <line x1={sx(v)} x2={sx(v)} y1={TOP - 10} y2={HT - 14}
                  className={v === 0 ? "zero" : "gy"} />
                <text x={sx(v)} y={TOP - 16} className="gt">
                  {v === 0 ? "המועדון" : (v > 0 ? "+" : "") + f(v, 0)}
                </text>
              </g>
            ))}
            {rows.map((r, i) => {
              const y = TOP + i * ROW;
              const bar = (v, cls, off, h) => v == null ? null : (
                <rect x={Math.min(sx(0), sx(v))} y={y + off} height={h}
                  width={Math.abs(sx(v) - sx(0))} className={cls} />
              );
              return (
                <g key={r.club + r.season} className="br">
                  <rect x="0" y={y} width={W} height={ROW} className="brbg" />
                  <text x={LB - 10} y={y + ROW / 2 + 4} className="lab">
                    {r.club}{season === "all" ? ` ${r.season % 100}` : ""}
                  </text>
                  {bar(r.gRand, "brand", 4, 9)}
                  {bar(r.gEng, "bfree", 16, 9)}
                  <text x={W - RB + 8} y={y + ROW / 2 + 4} className="val">
                    {r.gEng > 0 ? "+" : ""}{f(r.gEng)}
                  </text>
                  <title>{`${r.club} ${r.season} · אקראי ${f(r.gRand)} · מנוע ${f(r.gEng)}`}</title>
                </g>
              );
            })}
          </svg>
        </div>

        <p className="ans">
          <b>התשובה:</b> סגל אקראי מנצח את המועדון ב-<b>{randBeats} מתוך {rows.length}</b>
          {" "}בלבד, בעוד המנוע מנצח ב-<b>{engBeats}</b>. אילו האילוצים היו
          מייצרים את היתרון, האקראי היה נמצא גם הוא מימין לקו.
          הוא לא — ולכן היתרון מגיע מהבחירה.
        </p>
      </section>
      )}

      {/* ═══ 2 ═══ */}
      <section className="q">
        <div className="qh">
          <span className="qn">01</span>
          <div>
            <h2>מי מרוויח יותר מהמנוע, קבוצות עשירות או עניות?</h2>
            <p className="qs">
              כל נקודה היא קבוצה. ככל שהיא ימינה יותר, התקציב שלה גדול יותר.
              ככל שהיא גבוהה יותר, המנוע הוסיף לה יותר.
            </p>
          </div>
        </div>

        <div className="scroll">
          <svg viewBox={`0 0 ${SW} ${SH}`} className="viz" style={{ minWidth: 560 }}>
            {[gLo, 0, gHi].map((v) => (
              <g key={v}>
                <line x1={SL} x2={SW - SR} y1={py(v)} y2={py(v)}
                  className={v === 0 ? "zero" : "gy"} />
                <text x={SL - 8} y={py(v) + 4} className="gt end">{v}</text>
              </g>
            ))}
            {[bLo, (bLo + bHi) / 2, bHi].map((v) => (
              <text key={v} x={px(v)} y={SH - 14} className="gt">{v}%</text>
            ))}
            <line x1={px(bLo)} y1={py(my + slope * (bLo - mx))}
              x2={px(bHi)} y2={py(my + slope * (bHi - mx))} className="trend" />
            {rows.map((r) => (
              <g key={r.club + r.season}>
                <circle cx={px(r.bp)} cy={py(r.gEng)} r="5" className="pt" />
                <text x={px(r.bp)} y={py(r.gEng) - 9} className="ptl">{r.club}</text>
                <title>{`${r.club} · תקציב ${r.bp}% · פער ${f(r.gEng)}`}</title>
              </g>
            ))}
            <text x={(SL + SW - SR) / 2} y={SH - 1} className="gt dimx">
              תקציב (100% = קבוצה ממוצעת בעונה)
            </text>
          </svg>
        </div>

        <p className="ans">
          <b>התשובה:</b> כל 10% תקציב נוסף {slope < 0 ? "מקטינים" : "מגדילים"}{" "}
          את הפער ב-<b dir="ltr">{f(Math.abs(slope * 10), 2)}</b> נקודות בלבד
          (מתאם <b dir="ltr">r = {f(rr, 2)}</b>).
          {Math.abs(rr) < 0.3
            ? " כמעט אין קשר: גם קבוצות עשירות משאירות ניצחונות על השולחן, לא רק עניות."
            : rr < 0
              ? " לקבוצות עשירות יש פחות מה להוסיף, כי הכסף כבר קנה להן את רוב מה שאפשר."
              : " דווקא לקבוצות העשירות יש יותר מה להרוויח."}
          {" "}חשוב לזכור שזו השוואה בין קבוצות ולא ניסוי. קבוצה עשירה שונה
          מקבוצה ענייה גם בדברים שלא מדדנו.
        </p>
      </section>

      {/* ═══ 3 — מוסתר ב-v1.0 ═══
          מודל האפס לכל מועדון (סגל אקראי מול המועדון) נמדד בקונבנציה
          הקודמת, והטווח "3% עד 88%" היה מוקלד בטקסט. גזירה מחדש תחת
          ADR 0006 ברשימת v2. מוסתר כמו סעיף 1 ביום 14, לא נמחק. */}
      {false && (
      <section className="q">
        <div className="qh">
          <span className="qn">02</span>
          <div>
            <h2>עד כמה זה יציב בין מועדונים?</h2>
            <p className="qs">
              לכל מועדון הוגרלו כ־300 סגלים אקראיים. הרצועה מראה באיזה
              אחוז מההגרלות הסגל האקראי ניצח את הסגל האמיתי.
            </p>
          </div>
        </div>

        <div className="strip">
          {rows.filter((r) => r.rand_win != null)
            .sort((a, b) => a.rand_win - b.rand_win)
            .map((r) => (
              <div key={r.club + r.season} className="sr"
                title={`${r.club} ${r.season} · ${pctf(r.rand_win)}`}>
                <span className="sl">{r.club}</span>
                <span className="sb">
                  <i style={{ width: `${r.rand_win * 100}%` }}
                    className={r.rand_win > 0.5 ? "hi" : ""} />
                </span>
                <span className="sv">{pctf(r.rand_win)}</span>
              </div>
            ))}
        </div>

        <p className="ans">
          <b>התשובה:</b> בכלל לא יציב. הטווח נע מ־3% ל־88%. יש מועדונים
          שסגל מוגרל באקראי היה עדיף על מה שהם בנו, ויש כאלה שכמעט
          בלתי אפשרי לנצח. <b>הממוצע מסתיר את זה</b>, ולכן הוא מוצג
          כאן פרוס.
        </p>
      </section>
      )}

      {/* ═══ נתונים מלאים ═══ */}
      <details className="det">
        <summary>הצג את כל המספרים</summary>
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>קבוצה</th><th>עונה</th><th className="n">תקציב</th>
                <th className="n">הקבוצה, כפי ששיחקה</th>
                <th className="n">המנוע, לפי התוכנית</th>
                <th className="n">פער</th><th className="n">יתרון</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.club + r.season}>
                  <td><b>{r.club}</b></td>
                  <td className="n">{r.season}</td>
                  <td className="n">{r.bp}%</td>
                  <td className="n">{f(r.q_club)}</td>
                  <td className="n freec">{f(r.q_engine)}</td>
                  <td className={"n " + (r.gEng >= 0 ? "up" : "down")}>
                    {r.gEng >= 0 ? "+" : ""}{f(r.gEng)}
                  </td>
                  <td className="n">{pctf(r.adv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <footer>
        <b>המנוע</b> כאן הוא אותו מנוע שמוצג במסך הראשי, והוא כפוף לשני
        אילוצים. האחד: על המגרש יש כדור אחד, ולכן סך ההתקפות שהסגל מסיים
        אינו יכול לחרוג ממה שחמישה שחקנים מסיימים בפועל. השני: ריכוז הדקות
        בשחקנים המובילים אינו עולה על הריכוז המרבי שנמדד בליגה.
        <br />
        <b>הניקוד</b> נעשה בלי ידיעה בדיעבד לשני הצדדים. המנוע נמדד לפי
        תוכנית הדקות שקבע לפני העונה. דקות שתוכננו לשחקן שלא היה זמין אינן
        עוברות לשאר הסגל, אלא נזקפות לרמת שחקן חלופי, כלומר התפוקה האופיינית של
        שחקן שמחתימים באמצע העונה. הקבוצה נמדדת לפי הרוטציה ששיחקה בפועל.
      </footer>
    </Shell>
  );
}

const Shell = ({ children }) => (
  <div dir="rtl" className="evr"><style>{CSS}</style>{children}</div>
);

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Secular+One&family=Assistant:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
.evr{--bg:#0E1420;--pan:#141C2B;--ln:#26314A;--tx:#E9EDF5;--dim:#8894AC;
 --pred:#5AA9FF;--real:#F2A13C;--gray:#5A6478;
 background:var(--bg);color:var(--tx);min-height:100vh;
 font-family:'Assistant',system-ui,sans-serif;
 padding:clamp(18px,4vw,56px);max-width:940px;margin:0 auto;}
.evr .load,.evr .fail{color:var(--dim);padding:40px 0;}
.evr .fail{color:var(--real);}
.eyebrow{font-size:11.5px;letter-spacing:.15em;color:var(--dim);}
.evr h1{font-family:'Secular One',sans-serif;font-weight:400;
 font-size:clamp(28px,4.5vw,44px);margin:10px 0 22px;line-height:1.1;}
.top{border-bottom:1px solid var(--ln);padding-bottom:22px;margin-bottom:34px;}
.ctrls{display:flex;gap:14px;flex-wrap:wrap;}
.tabs{display:flex;gap:4px;}
.tb{background:none;border:1px solid var(--ln);color:var(--dim);border-radius:3px;
 font:inherit;font-size:11.5px;padding:4px 11px;cursor:pointer;}
.tb.on{border-color:var(--pred);color:var(--pred);}
.q{background:var(--pan);border:1px solid var(--ln);border-radius:3px;
 padding:22px clamp(14px,3vw,26px);margin-bottom:22px;}
.qh{display:flex;gap:16px;align-items:flex-start;margin-bottom:16px;}
.qn{font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--real);
 padding-top:3px;}
.evr h2{font-size:17px;font-weight:700;margin:0 0 8px;line-height:1.35;}
.qs{font-size:13px;line-height:1.75;color:var(--dim);margin:0;max-width:620px;}
.qs b,.ans b{color:var(--tx);}
.lgnd{display:flex;gap:18px;font-size:11.5px;color:var(--dim);margin-bottom:10px;}
.lgnd span{display:flex;align-items:center;gap:6px;}
.sw{width:16px;height:8px;display:inline-block;border-radius:1px;}
.sw.rand{background:var(--gray);}.sw.free{background:var(--pred);}
.scroll{overflow-x:auto;}
.viz{width:100%;height:auto;}
.viz .gy{stroke:var(--ln);stroke-width:1;}
.viz .zero{stroke:var(--tx);stroke-width:1.4;opacity:.65;}
.viz .gt{font-family:'IBM Plex Mono',monospace;font-size:9.5px;fill:var(--dim);
 text-anchor:middle;}
.viz .gt.end{text-anchor:end;}
.viz .gt.dimx{font-family:'Assistant',sans-serif;font-size:10px;opacity:.75;}
.viz .lab{font-family:'IBM Plex Mono',monospace;font-size:10.5px;fill:var(--tx);
 text-anchor:end;}
.viz .val{font-family:'IBM Plex Mono',monospace;font-size:10.5px;fill:var(--dim);}
.viz .brbg{fill:transparent;}
.viz .br:hover .brbg{fill:rgba(90,169,255,.07);}
.viz .brand{fill:var(--gray);}
.viz .bfree{fill:var(--pred);}
.viz .pt{fill:var(--pred);opacity:.85;}
.viz .ptl{font-family:'IBM Plex Mono',monospace;font-size:8.5px;
 fill:var(--dim);text-anchor:middle;}
.viz .trend{stroke:var(--real);stroke-width:1.4;stroke-dasharray:4 4;opacity:.8;}
.ans{font-size:13.5px;line-height:1.8;color:var(--dim);margin:16px 0 0;
 border-top:1px solid var(--ln);padding-top:14px;max-width:660px;}
.strip{display:flex;flex-direction:column;gap:3px;margin-bottom:4px;}
.sr{display:grid;grid-template-columns:52px 1fr 42px;gap:10px;align-items:center;}
.sr .sl{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--tx);}
.sr .sb{height:9px;background:var(--ln);border-radius:2px;overflow:hidden;}
.sr .sb i{display:block;height:100%;background:var(--gray);}
.sr .sb i.hi{background:var(--real);}
.sr .sv{font-family:'IBM Plex Mono',monospace;font-size:10.5px;
 color:var(--dim);text-align:end;}
.det{margin-bottom:26px;}
.det summary{font-size:12.5px;color:var(--dim);cursor:pointer;padding:10px 0;
 border-top:1px solid var(--ln);border-bottom:1px solid var(--ln);}
.det summary:hover{color:var(--pred);}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:12px;}
.tbl th{font-size:10px;color:var(--dim);font-weight:600;text-align:start;
 padding:0 8px 8px;border-bottom:1px solid var(--ln);white-space:nowrap;}
.tbl td{padding:5px 8px;border-bottom:1px solid var(--ln);}
.tbl .n{font-family:'IBM Plex Mono',monospace;text-align:end;}
.tbl .dimc{color:var(--dim);}.tbl .freec{color:var(--pred);}
.tbl .up{color:var(--pred);}.tbl .down{color:var(--real);}
.evr footer{font-size:12px;line-height:1.8;color:var(--dim);
 border-top:1px solid var(--ln);padding-top:16px;max-width:660px;}
.evr footer b{color:var(--tx);}
@media (max-width:620px){.qh{gap:10px;}.evr h2{font-size:15px;}}
`;