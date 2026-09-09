"""tag_external_usage — משייך usage לכל שורה ב-salary_external_2025.csv.

שלב 1 של docs/refit-run-spec.md. תנאי מקדים לריפיט של ADR 0001.

למה בכלל: מודל העלות מכויל היום על usage='calibrate', שהוא מכבי ת"א
בלבד (39 שורות, 2023-2025). ה-usage='test' היחיד הוא הפועל ת"א
(19 שורות). לקובץ החיצוני אין עמודת usage כלל, והוא מכיל 14 שורות
של הפועל ת"א — כלומר איחוד עיוור שלו לתוך הכיול הורס את סט המבחן
היחיד שיש לפרויקט.

ההפרדה היא **לפי מועדון, לא לפי שורה**. הספציפיקציה של salary_market
משתמשת באפקטים קבועים למועדון, ולכן מועדון שמופיע בשני הצדדים מדליף
את רמת המחירים שלו לתוך ההערכה של עצמו.

בחירת מועדוני המבחן:
  OLY — β₁ השטוח ביותר שנמדד ביום 9 (0.083). החזקתו בחוץ בודקת
        ישירות את ההנחה של ADR 0001, ששיפוע אחד מכליל לכל הליגה.
  BAS — הקצה העני של טווח התקציב.
  HTA — כבר test בעוגנים. נשאר.

מה שנשאר בכיול במכוון: PAN, MAD, BAR. הם המועדונים העשירים שנותרו,
ודווקא העשירים מחזיקים את הקצה השטוח של העקומה. הזזת עוד אחד מהם
למבחן מטה את β₁ המכויל חזרה לכיוון התלול ומשנה את החיזוי הנעול.

הסקריפט לא נוגע במודל, לא מריץ אופטימיזציה, ולא משנה שום מספר.
ה-hash של roster_sweep חייב לצאת זהה אחרי הרצתו.
"""
import hashlib
import sys
from pathlib import Path

import pandas as pd

SEP = "=" * 68
PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"
EXTERNAL = PROCESSED / "salary_external_2025.csv"
ANCHORS = PROCESSED / "salary_anchors.csv"

# שמות מלאים -> קודים. מיושר עם CLUBMAP ב-salary_market.py.
CLUBMAP = {
    "Hapoel Tel Aviv": "HTA", "Maccabi Tel Aviv": "TEL",
    "Panathinaikos": "PAN", "Olympiacos": "OLY", "Anadolu Efes": "IST",
    "Dubai BC": "DUB", "Real Madrid": "MAD", "Barcelona": "BAR",
    "Fenerbahce": "ULK", "Fenerbahçe": "ULK", "Bayern Munich": "MUN",
    "Virtus Bologna": "VIR", "Crvena Zvezda": "RED", "ASVEL": "ASV",
    "Zalgiris": "ZAL", "Žalgiris": "ZAL", "Valencia": "PAM",
    "Monaco": "MCO", "AS Monaco": "MCO", "Partizan": "PAR",
    "Paris Basketball": "PRS", "Baskonia": "BAS", "Milan": "MIL",
    "Olimpia Milano": "MIL",
}

TEST_CLUBS = {"HTA", "OLY", "BAS"}

# עונת 26/27 לא שוחקה. מחיריה אינם קלט לכיול עקומה לעונה שיש לה
# תוצאות, ובצד המבחן יש ממנה תצפית אחת בלבד — כלומר גם אי אפשר
# לבדוק אם היא מתנהגת אחרת. השורות נשארות בקובץ כזרע לשלב
# התחזיתי ומסומנות structure_only. ראו ADR 0003 לקונבנציית העונה.
SEED_YEAR = 2026

# מה שהוסכם. אי-התאמה עוצרת — סימן שהקובץ השתנה מתחת לפילוח.
EXPECTED_EXTERNAL = {"calibrate": 38, "test": 20, "structure_only": 8}
EXPECTED_COMBINED = {"calibrate": 77, "test": 39}


def load():
    ext = pd.read_csv(EXTERNAL)
    ext["code"] = ext.club.map(CLUBMAP)
    missing = sorted(ext.loc[ext.code.isna(), "club"].unique())
    if missing:
        raise SystemExit(
            f"מועדונים ללא מיפוי ב-CLUBMAP: {missing}\n"
            "להוסיף ל-CLUBMAP כאן וב-salary_market.py, ולא לנחש קוד.")
    return ext


def tag(ext):
    ext = ext.copy()
    ext["usage"] = ext.code.map(
        lambda c: "test" if c in TEST_CLUBS else "calibrate")
    ext.loc[ext.yr == SEED_YEAR, "usage"] = "structure_only"
    return ext


def check(ext):
    """אימות מלא. כל כשל עוצר — אין ברירת מחדל שקטה."""
    got = ext.usage.value_counts().to_dict()
    if got != EXPECTED_EXTERNAL:
        raise SystemExit(f"ספירה בקובץ החיצוני: {got} · צפוי "
                         f"{EXPECTED_EXTERNAL}")

    # מועדון שלם לצד אחד. ההנחה שכל ההפרדה נשענת עליה.
    # structure_only אינו צד — הוא לא מכייל ולא בודק.
    sides = ext[ext.usage.isin(["calibrate", "test"])]
    split = sides.groupby("code").usage.nunique()
    bad = split[split > 1]
    if len(bad):
        raise SystemExit(f"מועדונים בשני הצדדים: {sorted(bad.index)}")

    anch = pd.read_csv(ANCHORS)
    anch = anch[anch.usage.isin(["calibrate", "test"])]

    # מועדון שהוא calibrate בעוגנים לא יכול להיות test כאן ולהפך.
    a_side = anch.groupby("club").usage.agg(
        lambda s: s.iloc[0] if s.nunique() == 1 else "MIXED")
    for code, side in a_side.items():
        if code in sides.code.values:
            here = sides.loc[sides.code == code, "usage"].iloc[0]
            if here != side:
                raise SystemExit(
                    f"{code}: '{side}' בעוגנים אבל '{here}' בחיצוני")

    combined = {
        k: int((anch.usage == k).sum() + (ext.usage == k).sum())
        for k in ("calibrate", "test")}
    if combined != EXPECTED_COMBINED:
        raise SystemExit(f"ספירה מאוחדת: {combined} · צפוי "
                         f"{EXPECTED_COMBINED}")
    return combined


def report(ext, combined):
    print(SEP)
    print("tag_external_usage — שלב 1, ADR 0001")
    print(SEP)

    t = (ext.groupby(["usage", "code"]).size().rename("rows")
         .reset_index().sort_values(["usage", "rows"],
                                    ascending=[True, False]))
    print(f"\n  {'usage':<16}{'code':<6}{'rows':>5}")
    for r in t.itertuples():
        print(f"  {r.usage:<16}{r.code:<6}{r.rows:>5}")

    yr = ext.groupby(["usage", "yr"]).size().unstack(fill_value=0)
    print(f"\n  לפי עונת פתיחה (ADR 0003):\n{yr.to_string()}")
    fit_yrs = sorted(int(y) for y in
                     ext.loc[ext.usage == "calibrate", "yr"].unique())
    print(f"\n  ⚠ מדגם הכיול מכיל {len(fit_yrs)} עונות {fit_yrs}. "
          "לא לאחד לרגרסיה אחת בלי דמה לעונה.")

    n_hta = int((ext.code == "HTA").sum())
    print(f"  ⚠ HTA הוא {n_hta} מתוך {int((ext.usage=='test').sum())} "
          "שורות המבחן החיצוניות. לדווח מדדי מבחן לפי מועדון, לא מאוחד.")

    print(f"\n  מאוחד עם העוגנים: calibrate {combined['calibrate']} · "
          f"test {combined['test']}")
    basis = ext.basis.value_counts().to_dict()
    print(f"  basis: {basis} · אין ערבוב נטו/ברוטו")


def main() -> int:
    ext = load()
    prev = ext.usage.copy() if "usage" in ext.columns else None

    ext = tag(ext)
    if prev is not None:
        changed = prev != ext.usage
        n = int(changed.sum())
        if n:
            print("\n  תיוג קיים שונה מהכלל הנוכחי:")
            for old, new in sorted(set(zip(prev[changed],
                                           ext.usage[changed]))):
                k = int(((prev == old) & (ext.usage == new)).sum())
                print(f"    {old} → {new}: {k}")
            if "--retag" not in sys.argv:
                raise SystemExit(
                    "\n  עצירה. אם זה שינוי כלל מכוון — להריץ עם "
                    "--retag.\n  אם לא — מישהו ערך ידנית, ואין לדרוס.")
            print("  --retag ניתן. דורס.\n")
        else:
            print("usage קיים וזהה לכלל. נכתב מחדש.\n")

    combined = check(ext)
    report(ext, combined)

    out = ext.drop(columns=["code"])
    # lineterminator מפורש. ברירת המחדל של pandas היא os.linesep,
    # כלומר CRLF בווינדוס ו-LF בלינוקס — אותו קוד, hash שונה לפי
    # המכונה. כל קובצי ה-CSV ברפו הם LF.
    out.to_csv(EXTERNAL, index=False, encoding="utf-8",
               lineterminator="\n")
    h = hashlib.md5(EXTERNAL.read_bytes()).hexdigest()[:12]
    print(f"\n  נכתב: {EXTERNAL.name} · {len(out)} שורות · md5 {h}")
    print("  לא נגע במודל. hash של roster_sweep חייב לצאת זהה.")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())