/* שמות המועדונים בעברית, לפי הקודים ב-team_season.
   PAR = פרטיזן, PRS = פריז. */
export const CLUB = {
  BAR: "ברצלונה", MAD: "ריאל מדריד", MIL: "מילאנו", ULK: "פנרבחצה",
  IST: "אנדולו אפס", TEL: 'מכבי ת"א', MUN: "באיירן", BAS: "באסקוניה",
  OLY: "אולימפיאקוס", PAM: "ולנסיה", PAN: "פנאתינייקוס", ZAL: "ז'לגיריס",
  ASV: "אסוול", BER: "אלבה ברלין", RED: "הכוכב האדום", MCO: "מונקו",
  PAR: "פרטיזן", VIR: "וירטוס", PRS: "פריז", HTA: 'הפועל ת"א', DUB: "דובאי",
};
export const cname = (code) => CLUB[code] ?? code;

/* תקציב לתצוגה: אחוז מהתקציב של קבוצה ממוצעת באותה עונה (100% = ממוצע).
   היחידה הפנימית (1 = שחקן ממוצע במאגר) לא אינטואיטיבית, ויורו נפסל.
   זה שינוי סקאלה בלבד — לא נוגע במנוע ולא במספר אחד בנתונים. */
export const seasonAvg = (clubs) => {
  const acc = {};
  for (const c of clubs ?? []) {
    (acc[c.season] ??= []).push(c.budget);
  }
  return Object.fromEntries(Object.entries(acc)
    .map(([s, b]) => [s, b.reduce((x, y) => x + y, 0) / b.length]));
};
export const pct = (b, avg) => (avg ? Math.round((b / avg) * 100) : NaN);
