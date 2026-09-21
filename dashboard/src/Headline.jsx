import { useState, useEffect, useMemo } from "react";
import { cname as code2name, seasonAvg, pct as bpct } from "./clubs";

/* ══════════════════════════════════════════════════════════════
   Headline — המסך הראשון
   public/dashboard_data.json  (פלט export_dashboard.py)

   כל מספר כאן עבר בקרת הקפאה. שינוי בכל אחד מהם שובר את
   הבנייה בפייתון לפני שהוא מגיע לכאן.

   🔴 v1.0, שלב א' של הנגשה. המבחן של תוכנית הסגירה: זר מבין תוך
      30 שניות. לכן:
      1. המסך נפתח בשאלה ובתשובה (+5 ניצחונות), ולא ב-30.8%.
         ה-30.8% הוא חלוקה **בדיעבד** לפי התפוקה שהתממשה, וסותר את
         אזהרת העומק: ספסל הוא ביטוח. הוא נשאר, במסגור כן, למטה.
      2. "בחר קבוצה" — חציון על 38 מועדונים מופשט; המועדון שלך לא.
      3. האמון בארבעה משפטים עם סמל. הפירוט הטכני מאחורי "כל הפרטים".
      4. תקציב מוצג כאחוז מהתקציב של קבוצה ממוצעת בעונה (100% = ממוצע).
      בשכבה הראשית אין מספרי ADR, "קונבנציה", "בדיעבד" או "gap=0".
══════════════════════════════════════════════════════════════ */

const f = (n, d = 2) => (n == null || Number.isNaN(n) ? "—" : n.toFixed(d));
const pct = (n) => `${(n * 100).toFixed(1)}%`;

const cname = (c) => code2name(c.club);
const sname = (s) => `${s}/${String((s + 1) % 100).padStart(2, "0")}`;

export default function Headline({ onOpenBuilder }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [openLim, setOpenLim] = useState(null);
  const [pick, setPick] = useState(null);

  useEffect(() => {
    fetch("/dashboard_data.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then(setD)
      /* ⚠️ לא catch ריק. כשל שקט כאן הסתיר מסך שלם */
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  const clubs = useMemo(() => (d?.clubs ?? [])
    .slice().sort((a, b) => b.season - a.season || cname(a).localeCompare(cname(b), "he")),
    [d]);

  if (err) return (
    <div dir="rtl" className="hl"><style>{CSS}</style>
      <p className="fail">dashboard_data.json לא נטען — {err}</p>
    </div>
  );
  if (!d) return <div dir="rtl" className="hl"><style>{CSS}</style>
    <p className="load">טוען…</p></div>;

  const H = d.headline.primary;
  const struct = (d.headline.decomposition ?? [])[0];
  const key = (c) => `${c.club}-${c.season}`;
  const club = clubs.find((c) => key(c) === pick)
    ?? clubs.find((c) => c.club === "TEL" && c.season === 2025) ?? clubs[0];
  const AVGS = seasonAvg(d.clubs);
  const top = club ? Math.max(club.q_club, club.q_engine) * 1.08 : 1;

  return (
    <div dir="rtl" className="hl">
      <style>{CSS}</style>

      {/* ───────── השאלה והתשובה ───────── */}
      <header className="top">
        <div className="eyebrow">
          יורוליג · {d.benchmark.n} קבוצות · {d.benchmark.seasons.map(sname).join(" ו־")}
        </div>
        <h1 className="ask">
          באותו תקציב בדיוק — כמה ניצחונות אפשר היה להוסיף, רק בבחירה
          אחרת של שחקנים?
        </h1>
        <div className="answer">
          <span className="huge blue" dir="ltr">+{f(H.value, 1)}</span>
          <span className="unit">ניצחונות בעונה, בערך</span>
        </div>
        <p className="lede">
          הטווח הסביר: <b>בין {f(H.ci[0], 1)} ל־{f(H.ci[1], 1)}</b>. גם בקצה
          הזהיר — יותר ניצחונות, בלי להוסיף שקל. ובכל{" "}
          <b>{d.benchmark.n_win} מתוך {d.benchmark.n}</b> הקבוצות שבדקנו,
          הסגל שהמנוע בנה הפיק יותר מהסגל האמיתי.
        </p>
      </header>

      {/* ───────── הקבוצה שלך ───────── */}
      {club && (
        <section className="card duel">
          <div className="duelhead">
            <h2>ומה עם הקבוצה שלך?</h2>
            <select value={key(club)} onChange={(e) => setPick(e.target.value)}
              aria-label="בחר קבוצה">
              {clubs.map((c) => (
                <option key={key(c)} value={key(c)}>{cname(c)} · {sname(c.season)}</option>
              ))}
            </select>
          </div>
          <p className="sub">
            התקציב של {cname(club)} בעונת {sname(club.season)} היה{" "}
            <b>{bpct(club.budget, AVGS[club.season])}% מהתקציב של קבוצה ממוצעת</b>{" "}
            באותה עונה. בדיוק אותו תקציב קיבל גם המנוע.
          </p>

          <div className="bars">
            <div className="bar">
              <span className="bl">הסגל האמיתי</span>
              <span className="track"><i className="real"
                style={{ width: `${(club.q_club / top) * 100}%` }} /></span>
              <span className="bv" dir="ltr">{f(club.q_club, 1)}</span>
            </div>
            <div className="bar">
              <span className="bl">הסגל של המנוע</span>
              <span className="track"><i className="pred"
                style={{ width: `${(club.q_engine / top) * 100}%` }} /></span>
              <span className="bv" dir="ltr">{f(club.q_engine, 1)}</span>
            </div>
          </div>
          <p className="verdict">
            {club.adv > 0
              ? <>המנוע היה מפיק <b className="blue">{pct(club.adv)} יותר</b> באותו תקציב.</>
              : <>כאן הקבוצה האמיתית הייתה טובה יותר מהמנוע.</>}
          </p>
          <p className="fine">
            המספרים הם תרומה במדד PIR (מדד התרומה הרשמי של היורוליג) למשחק,
            לפי מה שהשחקנים באמת הפיקו באותה עונה. לקבוצה בודדת התוצאה
            רועשת יותר מהממוצע — אל תסיק ממנה לבדה.
          </p>
          {onOpenBuilder && club.season === 2025 && (
            <button className="cta" onClick={onOpenBuilder}>
              נסה לבנות סגל בעצמך ←
            </button>
          )}
        </section>
      )}

      {/* ───────── למה אפשר לסמוך על זה ───────── */}
      <section className="card">
        <h2>למה אפשר לסמוך על זה — ובמה לא</h2>
        <ul className="trust">
          <li><span className="ic" aria-hidden>⚖️</span><div>
            <b>השוואה הוגנת.</b> המנוע לא יודע מראש מי ייפצע ומי יתפוצץ —
            בדיוק כמו המאמן. כשתכנן דקות לשחקן שלא היה זמין, הוא שילם על זה.
          </div></li>
          <li><span className="ic" aria-hidden>🪑</span><div>
            <b>ספסל קצר.</b> המנוע מחזיק 12 שחקנים, קבוצה אמיתית 15–20. בגלל
            זה כ־14% מהדקות שתכנן הלכו
            לשחקנים שנפצעו — והוא עדיין יצא עדיף.
          </div></li>
          <li><span className="ic" aria-hidden>🎚️</span><div>
            <b>רגיש לכלל אחד.</b> אם מגבילים עוד קצת כמה דקות מותר לתת
            לכוכבים, היתרון קטן בכשליש. הגבול שבחרנו הוא מה שקבוצות
            אמיתיות עשו בפועל.
          </div></li>
          <li><span className="ic" aria-hidden>🔋</span><div>
            <b>עייפות לא בפנים.</b> ניסינו למדוד אותה מנתוני משחק, ולא ניתן
            להפריד בינה לבין מאמן שמשאיר שחקן חם על הפרקט. זה <b>לא</b> אומר
            שהיא לא קיימת.
          </div></li>
        </ul>
      </section>

      {/* ───────── זה לא הכללים ───────── */}
      {struct && (
        <section className="card">
          <h2>זה לא "הכללים עושים את העבודה"</h2>
          <p className="sub">
            שאלנו: אולי כל סגל שעומד באותם כללים (12 שחקנים, עמדות, אותו
            תקציב) היה מנצח? אז בחרנו סגל <b>באקראי</b> תחת אותם כללים בדיוק.
            הוא <b>הפסיד</b> לקבוצה האמיתית — בערך{" "}
            <b dir="ltr">{f(Math.abs(struct.wins), 1)}</b> ניצחונות פחות בעונה.
            כלומר היתרון מגיע מ<b>בחירת השחקנים</b>, לא מהכללים.
          </p>
          <p className="fine">
            נמדד בשיטת הניקוד הקודמת. הכיוון הוא מה שחשוב; מדידה מחדש
            מתוכננת לגרסה הבאה.
          </p>
        </section>
      )}

      {/* ───────── במבט לאחור ───────── */}
      <section className="card">
        <h2>במבט לאחור</h2>
        <div className="answer small">
          <span className="huge orange" dir="ltr">{pct(d.wasted.share)}</span>
          <span className="unit">מתקציב השחקנים</span>
        </div>
        <p className="sub">
          אם יודעים בסוף העונה מי באמת הפיק, בערך שליש מהתקציב הלך לשחקנים
          שכמעט לא היו נחוצים. <b>אבל זה לא "בזבוז" פשוט</b>: אי אפשר לדעת
          את זה מראש, וספסל הוא גם ביטוח לפציעות — בדיוק הדבר שהמנוע שילם
          עליו כשהחזיק רק 12.
        </p>
      </section>

      {/* ───────── הכול, למי שרוצה ───────── */}
      <details className="card deep">
        <summary>כל הפרטים — למי שרוצה לבדוק</summary>

        <div className="grid3">
          <Fact v={d.benchmark.n} l="קבוצות־עונה"
            h="כל קבוצה, בתקציב האמיתי שלה, בשתי עונות" />
          <Fact v={`+${pct(d.benchmark.adv_cap_pct)}`} l="יתרון בתפוקה, חציון"
            h="אף צד לא מקבל ידיעה מראש של מי יצא טוב" />
          <Fact v={`${d.benchmark.n_win}/${d.benchmark.n}`} l="קבוצות שבהן המנוע עדיף"
            h="כל חישוב הוכח כמיטבי, לא רק קירוב" />
        </div>
        <p className="sub">
          המנוע כפוף לשני כללים שלא ניתן לעקוף: בחמישייה שעל הפרקט יש כדור
          אחד, ולכן סך "צריכת ההתקפות" הוא בדיוק 100%; ואף רוטציה לא מרוכזת
          בכוכבים יותר ממה שקבוצה אמיתית עשתה.
        </p>

        {d.stability && (
          <>
            <h3>מה יציב ומה לא</h3>
            <p className="sub">
              ההשפעה של התקציב על הניצחונות נעה בין העונות (
              {Object.entries(d.stability.ratio_by_season)
                .map(([k, v]) => `${k}: ${f(v, 2)}`).join(" · ")}
              ), אבל הפער אינו מובהק (<span dir="ltr">p = {d.stability.permutation_p}</span>).
              לכן היא נמדדת על כל העונות יחד.
            </p>
          </>
        )}

        <h3>כל המגבלות</h3>
        <ol className="limlist">
          {d.limitations.map((L, i) => {
            const o = typeof L === "string" ? { t: L } : L;
            return (
              <li key={i} className={openLim === i ? "on" : ""}
                onClick={() => setOpenLim(openLim === i ? null : i)}>
                <span className="n" dir="ltr">{String(i + 1).padStart(2, "0")}</span>
                <div className="lb">
                  <b className="lt">{o.t}</b>
                  {o.p && <p className="lp">{o.p}</p>}
                  {openLim === i && o.x && <p className="lx">{o.x}</p>}
                </div>
                {o.x && <span className="lchev">{openLim === i ? "−" : "+"}</span>}
              </li>
            );
          })}
        </ol>
      </details>

      <footer>
        עודכן {d.meta.generated}. תקציב מוצג כאחוז מהתקציב של קבוצה ממוצעת
        באותה עונה; אין כאן יורו, כי התרגום ליורו נבדק ונפסל.{" "}
        כל מספר כאן נבדק מול הקבצים שיצרו אותו לפני שהאתר נבנה.
      </footer>
    </div>
  );
}

const Fact = ({ v, l, h }) => (
  <div className="fact">
    <span className="fv" dir="ltr">{v}</span>
    <span className="fl">{l}</span>
    <span className="fh">{h}</span>
  </div>
);

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Secular+One&family=Assistant:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
.hl{--bg:#0E1420;--pan:#141C2B;--ln:#26314A;--tx:#E9EDF5;--dim:#8894AC;
 --pred:#5AA9FF;--real:#F2A13C;
 background:var(--bg);color:var(--tx);min-height:100vh;
 font-family:'Assistant',system-ui,sans-serif;
 padding:clamp(18px,4vw,60px);max-width:900px;margin:0 auto;}
.hl .load,.hl .fail{color:var(--dim);padding:40px 0;}
.hl .fail{color:var(--real);}
.eyebrow{font-size:11.5px;letter-spacing:.16em;color:var(--dim);}
.top{border-bottom:1px solid var(--ln);padding-bottom:34px;margin-bottom:30px;}
.hl h1.ask{font-family:'Secular One',sans-serif;font-weight:400;
 font-size:clamp(21px,2.8vw,30px);line-height:1.45;margin:14px 0 0;max-width:620px;}
.answer{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:22px 0 6px;}
.answer.small{margin:6px 0 12px;}
.huge{font-family:'IBM Plex Mono',monospace;font-weight:600;
 font-size:clamp(46px,8vw,76px);line-height:1;letter-spacing:-.02em;}
.answer.small .huge{font-size:clamp(34px,5vw,48px);}
.huge.blue,.blue{color:var(--pred);}
.huge.orange{color:var(--real);}
.unit{font-size:15px;color:var(--dim);}
.lede{font-size:15px;line-height:1.8;color:var(--dim);max-width:620px;margin:10px 0 0;}
.lede b,.sub b,.verdict b,.trust b{color:var(--tx);}
.card{background:var(--pan);border:1px solid var(--ln);border-radius:3px;
 padding:22px clamp(16px,3vw,28px);margin-bottom:20px;}
.hl h2{font-size:17px;margin:0 0 12px;font-weight:700;}
.hl h3{font-size:14px;margin:22px 0 8px;font-weight:700;}
.sub{font-size:14px;line-height:1.8;color:var(--dim);margin:0;max-width:660px;}
.fine{font-size:12px;line-height:1.7;color:var(--dim);margin:12px 0 0;max-width:620px;opacity:.9;}

.duelhead{display:flex;justify-content:space-between;align-items:center;
 gap:12px;flex-wrap:wrap;margin-bottom:6px;}
.duelhead h2{margin:0;}
.duel select{background:var(--bg);color:var(--tx);border:1px solid var(--ln);
 border-radius:3px;font:inherit;font-size:14px;padding:7px 10px;min-width:190px;}
.bars{margin:18px 0 6px;display:grid;gap:10px;}
.bar{display:grid;grid-template-columns:110px 1fr 56px;align-items:center;gap:12px;}
.bl{font-size:13px;color:var(--dim);}
.track{height:14px;background:rgba(255,255,255,.04);border-radius:0 4px 4px 0;overflow:hidden;}
.track i{display:block;height:100%;border-radius:4px 0 0 4px;}
.track i.real{background:var(--real);}.track i.pred{background:var(--pred);}
.bv{font-family:'IBM Plex Mono',monospace;font-size:14px;color:var(--tx);text-align:left;}
.verdict{font-size:16px;line-height:1.6;margin:12px 0 0;color:var(--dim);}

.trust{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:0;}
.trust li{display:flex;gap:14px;padding:14px 0;border-top:1px solid var(--ln);
 font-size:14px;line-height:1.75;color:var(--dim);}
.trust li:first-child{border-top:none;padding-top:4px;}
.ic{font-size:22px;line-height:1.2;min-width:30px;text-align:center;}

.deep summary{cursor:pointer;font-size:15px;font-weight:700;color:var(--tx);
 list-style:none;}
.deep summary::before{content:"+ ";color:var(--pred);font-family:'IBM Plex Mono',monospace;}
.deep[open] summary::before{content:"− ";}
.deep[open] summary{margin-bottom:18px;}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin-bottom:18px;}
.fact{display:grid;grid-template-rows:auto auto 1fr;gap:5px;padding:2px 16px;
 border-inline-start:1px solid var(--ln);}
.fact:first-child{border-inline-start:none;padding-inline-start:0;}
.fv{font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:600;line-height:1;}
.fl{font-size:12.5px;font-weight:600;}
.fh{font-size:11px;color:var(--dim);line-height:1.5;}
.limlist{list-style:none;margin:10px 0 0;padding:0;}
.limlist li{display:flex;gap:14px;padding:14px 0;border-top:1px solid var(--ln);
 cursor:pointer;align-items:flex-start;}
.limlist .n{font-family:'IBM Plex Mono',monospace;font-size:11px;
 color:var(--real);padding-top:4px;}
.limlist .lb{flex:1;}
.limlist .lt{font-size:14px;line-height:1.45;display:block;margin-bottom:5px;}
.limlist .lp{font-size:13px;line-height:1.8;color:var(--dim);margin:0;max-width:600px;}
.limlist .lx{font-size:12px;line-height:1.75;color:var(--dim);margin:10px 0 0;
 padding-inline-start:12px;border-inline-start:2px solid var(--real);
 opacity:.85;max-width:600px;}
.limlist .lchev{font-family:'IBM Plex Mono',monospace;color:var(--dim);
 font-size:15px;padding-top:2px;}
.limlist li:hover .lt{color:var(--pred);}
.cta{background:none;border:1px solid var(--pred);color:var(--pred);
 font:inherit;font-size:14px;font-weight:600;padding:11px 22px;border-radius:3px;
 cursor:pointer;margin:18px 0 0;}
.cta:hover{background:rgba(90,169,255,.1);}
.hl footer{font-size:12px;line-height:1.75;color:var(--dim);
 border-top:1px solid var(--ln);padding-top:16px;max-width:660px;}
@media (max-width:640px){.grid3{grid-template-columns:1fr;gap:16px;}
 .fact{border-inline-start:none;padding-inline-start:0;}
 .bar{grid-template-columns:92px 1fr 48px;gap:8px;}
 .duel select{min-width:0;width:100%;}}
`;
