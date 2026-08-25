import { useState, useEffect } from "react";

/* ══════════════════════════════════════════════════════════════
   Headline — המסך הראשון
   public/dashboard_data.json  (פלט export_dashboard.py)

   כל מספר כאן עבר בקרת הקפאה. שינוי בכל אחד מהם שובר את
   הבנייה בפייתון לפני שהוא מגיע לכאן.
══════════════════════════════════════════════════════════════ */

const f = (n, d = 2) => (n == null || Number.isNaN(n) ? "—" : n.toFixed(d));
const pct = (n) => `${(n * 100).toFixed(1)}%`;

export default function Headline({ onOpenBuilder }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [openLim, setOpenLim] = useState(null);

  useEffect(() => {
    fetch("/dashboard_data.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then(setD)
      /* ⚠️ לא catch ריק. כשל שקט כאן הסתיר מסך שלם */
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return (
    <div dir="rtl" className="hl"><style>{CSS}</style>
      <p className="fail">dashboard_data.json לא נטען — {err}</p>
    </div>
  );
  if (!d) return <div dir="rtl" className="hl"><style>{CSS}</style>
    <p className="load">טוען…</p></div>;

  const H = d.headline.primary;
  const dec = d.headline.decomposition ?? [];
  const struct = dec[0], model = dec[1];

  return (
    <div dir="rtl" className="hl">
      <style>{CSS}</style>

      {/* ───────── הכותרת ───────── */}
      <header className="top">
        <div className="eyebrow">
          יורוליג · {d.benchmark.n} עונות־מועדון · {d.benchmark.seasons.join(" · ")}
        </div>

        <div className="huge" dir="ltr">{f(d.wasted.eur_m)}M EUR</div>
        <h1>
          זה מה שמועדון יורוליג ממוצע משלם בשנה
          על שחקנים שאינם חלק מהרוטציה.
        </h1>
        <p className="lede">
          {d.wasted.definition ??
            "כשמחלקים את דקות המשחק בין שחקני הסגל לפי התפוקה שלהם " +
            "לדקה, לחלקם לא נשארות דקות כלל."}
          {" "}זה <b>{pct(d.wasted.share)}</b> מהתקציב: בסגל טיפוסי
          של <b>{d.wasted.roster_median}</b>, רק <b>{d.wasted.n_scoring_median}</b>
          {" "}מקבלים מקום ברוטציה. לא מועדון חריג אחד — זה החציון
          של הליגה.
        </p>
        {d.wasted.caveat && (
          <p className="caveat">⚠️ {d.wasted.caveat}</p>
        )}

        <div className="second">
          <div className="secnum">
            <span className="sv">{H.value > 0 ? "+" : ""}{f(H.value)}</span>
            <span className="sl">ניצחונות בעונה</span>
          </div>
          <p className="sd">
            זה מה שאופטימיזציה של אותו תקציב מייצרת — בלי שקל נוסף,
            רק הקצאה אחרת. <span className="ci" dir="ltr">
              CI95 [{f(H.ci[0])}, {f(H.ci[1])}]
            </span>
            <em className="cav">{H.caveat}</em>
          </p>
        </div>
      </header>

      {/* ───────── הפירוק ───────── */}
      {struct && model && (
        <section className="card">
          <h2>מאיפה מגיע היתרון</h2>
          <p className="sub">
            השאלה הראשונה שצריך לשאול על כל מודל אופטימיזציה: כמה
            מהיתרון הוא <b>המודל</b>, וכמה רק <b>מבנה האילוצים</b>?
            סגל שהוגרל אקראית מהמאגר, תחת אותם אילוצים בדיוק, נותן
            את התשובה.
          </p>

          <ol className="steps">
            <li>
              <span className="stepnum bad" dir="ltr">{f(struct.wins)}</span>
              <div>
                <b>מבנה האילוצים לבדו</b>
                <p>{struct.note}</p>
                <span className="cin" dir="ltr">
                  CI95 [{f(struct.ci[0])}, {f(struct.ci[1])}]
                </span>
              </div>
            </li>
            <li>
              <span className="stepnum good" dir="ltr">+{f(model.wins)}</span>
              <div>
                <b>האופטימיזציה עצמה</b>
                <p>{model.note}</p>
                <span className="cin" dir="ltr">
                  CI95 [{f(model.ci[0])}, {f(model.ci[1])}]
                </span>
              </div>
            </li>
          </ol>

          <p className="punch">
            סגל אקראי <b>מפסיד</b> למועדון. כלומר היתרון אינו מיוצר
            על ידי 12 השחקנים, רצפות העמדה או תקרת הדקות — אלה
            דווקא עולים למנוע. הוא מיוצר על ידי הבחירה.
          </p>
        </section>
      )}

      {/* ───────── הבנצ'מרק ───────── */}
      <section className="card">
        <h2>איך זה נמדד</h2>
        <div className="grid3">
          <Fact v={d.benchmark.n} l="עונות־מועדון"
            h="כל מועדון, בתקציבו האמיתי, בשתי עונות" />
          <Fact v={`+${pct(d.benchmark.adv_free_pct)}`} l="מנוע חופשי"
            h="יתרון הניקוד על הסגל האמיתי, חציון" />
          <Fact v={`+${pct(d.benchmark.adv_cap_pct)}`} l="מנוע מאולץ"
            h="תחת זהות הכדור — אי אפשר לקנות חמישה שחקנים שכל אחד צורך 30% מההתקפות" />
        </div>
        <p className="sub">
          המספר שמוצג בכותרת הוא של המנוע <b>המאולץ</b>, הנמוך מהשניים.
          זהות הכדור היא אילוץ אריתמטי ולא הנחה: בחמישייה שעל הפרקט
          סכום הצריכה הוא בהכרח 100%, כי יש כדור אחד.
        </p>
      </section>

      {/* ───────── יציבות ───────── */}
      {d.stability && (
        <section className="card">
          <h2>מה יציב ומה לא</h2>
          <div className="ratios">
            {Object.entries(d.stability.ratio_by_season).map(([k, v]) => (
              <div key={k} className="rt">
                <span className="rv" dir="ltr">{f(v, 3)}</span>
                <span className="rl">{k}</span>
              </div>
            ))}
          </div>
          <p className="sub">
            היחס נע בין העונות, ובדיקת תמורות על 5,000 חלוקות אקראיות
            נותנת <b dir="ltr">p = {d.stability.permutation_p}</b> —
            הפער בין העונות <b>אינו מובהק</b>.
            רצועת 2024 לבדה היא <span dir="ltr">
              [{f(d.stability.ci_2024[0])}, {f(d.stability.ci_2024[1])}]
            </span>: על 18 מועדונים אי אפשר להבחין בין "התקציב מסביר
            הכל" ל"התקציב לא מסביר כלום". לכן {d.stability.note}.
          </p>
        </section>
      )}

      {/* ───────── מגבלות ───────── */}
      <section className="card lim">
        <h2>מה המנוע לא יודע</h2>
        <p className="sub">
          זה החלק שקובע אם אפשר להאמין לשאר. כל שורה כאן נמדדה או
          הוכרעה, ולא נוסחה בדיעבד.
        </p>
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
      </section>

      {onOpenBuilder && (
        <button className="cta" onClick={onOpenBuilder}>
          בנה קבוצה בעצמך ←
        </button>
      )}

      <footer>
        נוצר {d.meta.generated} · {d.meta.units} ·
        אזור אקסטרפולציה מ־{d.meta.extrapolation_from} יחידות.
        כל מספר כאן עבר בקרת הקפאה: שינוי בכל אחד מהם שובר את הבנייה.
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
.top{border-bottom:1px solid var(--ln);padding-bottom:38px;margin-bottom:34px;}
.huge{font-family:'IBM Plex Mono',monospace;font-weight:600;
 color:var(--real);font-size:clamp(40px,7vw,68px);line-height:1;
 margin:18px 0 12px;letter-spacing:-.02em;}
.hl h1{font-family:'Secular One',sans-serif;font-weight:400;
 font-size:clamp(19px,2.4vw,26px);line-height:1.5;margin:0;max-width:520px;}
.lede{font-size:14px;line-height:1.8;color:var(--dim);max-width:580px;
 margin:18px 0 0;}
.caveat{font-size:12.5px;line-height:1.7;color:var(--real);max-width:580px;
 margin:14px 0 0;padding-inline-start:12px;
 border-inline-start:2px solid rgba(242,161,60,.45);}
.lede b,.sub b,.punch b{color:var(--tx);}
.second{display:flex;gap:22px;align-items:flex-start;margin-top:32px;
 padding-top:26px;border-top:1px solid var(--ln);flex-wrap:wrap;}
.secnum{display:flex;flex-direction:column;min-width:130px;}
.sv{font-family:'IBM Plex Mono',monospace;font-size:44px;font-weight:600;
 color:var(--pred);line-height:1;}
.sl{font-size:12px;color:var(--dim);margin-top:4px;}
.sd{font-size:14px;line-height:1.7;color:var(--dim);flex:1;min-width:260px;margin:0;}
.ci{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--tx);
 display:inline-block;margin-inline-start:6px;}
.cav{display:block;font-style:normal;font-size:12px;color:var(--real);
 margin-top:8px;line-height:1.6;}
.card{background:var(--pan);border:1px solid var(--ln);border-radius:3px;
 padding:22px clamp(16px,3vw,28px);margin-bottom:20px;}
.hl h2{font-size:14px;letter-spacing:.04em;margin:0 0 12px;font-weight:700;}
.sub{font-size:13.5px;line-height:1.75;color:var(--dim);margin:0;max-width:660px;}
.steps{list-style:none;margin:20px 0 0;padding:0;}
.steps li{display:flex;gap:18px;align-items:flex-start;padding:16px 0;
 border-top:1px solid var(--ln);}
.stepnum{font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:600;
 min-width:96px;line-height:1;}
.stepnum.bad{color:var(--real);}.stepnum.good{color:var(--pred);}
.steps b{font-size:14px;display:block;margin-bottom:5px;}
.steps p{font-size:13px;color:var(--dim);margin:0 0 6px;line-height:1.65;}
.cin{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dim);}
.punch{font-size:14px;line-height:1.75;color:var(--dim);
 border-top:1px solid var(--ln);padding-top:16px;margin:14px 0 0;}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin-bottom:18px;}
.fact{display:grid;grid-template-rows:auto auto 1fr;gap:5px;padding:2px 16px;
 border-inline-start:1px solid var(--ln);}
.fact:first-child{border-inline-start:none;padding-inline-start:0;}
.fv{font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:600;line-height:1;}
.fl{font-size:12.5px;font-weight:600;}
.fh{font-size:10.5px;color:var(--dim);line-height:1.5;}
.ratios{display:flex;gap:26px;flex-wrap:wrap;margin-bottom:16px;}
.rt{display:flex;flex-direction:column;}
.rv{font-family:'IBM Plex Mono',monospace;font-size:24px;font-weight:600;
 color:var(--pred);line-height:1;}
.rl{font-size:11px;color:var(--dim);margin-top:3px;}
.lim{border-color:rgba(242,161,60,.35);}
.limlist{list-style:none;margin:18px 0 0;padding:0;}
.limlist li{display:flex;gap:14px;padding:14px 0;border-top:1px solid var(--ln);
 cursor:pointer;align-items:flex-start;}
.limlist .n{font-family:'IBM Plex Mono',monospace;font-size:11px;
 color:var(--real);padding-top:4px;}
.limlist .lb{flex:1;}
.limlist .lt{font-size:14px;line-height:1.45;display:block;margin-bottom:5px;}
.limlist .lp{font-size:13px;line-height:1.8;color:var(--dim);margin:0;
 max-width:600px;}
.limlist .lx{font-size:12px;line-height:1.75;color:var(--dim);margin:10px 0 0;
 padding-inline-start:12px;border-inline-start:2px solid var(--real);
 opacity:.85;max-width:600px;}
.limlist .lchev{font-family:'IBM Plex Mono',monospace;color:var(--dim);
 font-size:15px;padding-top:2px;}
.limlist li:hover .lt{color:var(--pred);}
.cta{background:none;border:1px solid var(--pred);color:var(--pred);
 font:inherit;font-size:14px;font-weight:600;padding:12px 24px;border-radius:3px;
 cursor:pointer;margin:8px 0 28px;}
.cta:hover{background:rgba(90,169,255,.1);}
.hl footer{font-size:11.5px;line-height:1.75;color:var(--dim);
 border-top:1px solid var(--ln);padding-top:16px;max-width:660px;}
@media (max-width:640px){.grid3{grid-template-columns:1fr;gap:16px;}
 .fact{border-inline-start:none;padding-inline-start:0;}
 .stepnum{min-width:72px;font-size:24px;}}
`;