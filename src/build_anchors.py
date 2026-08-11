"""
build_anchors.py  (v2 - Day 4)
------------------------------
בונה data/processed/salary_anchors.csv מכל רשימות השכר שנאספו.

שכבות (עמודת usage) - ההפרדה היא העיקר בקובץ הזה:
  calibrate       מכבי ת"א 23/24, 24/25, 25/26. דולר, נטו, מדווח.
                  זהו ורק זהו סט הכיול של מודל העלות.
  test            הפועל ת"א 25/26. אותה עונה, מועדון אחר, לא בכיול.
  structure_only  פנאתינייקוס/אולימפיאקוס 25/26, מכבי+הפועל 26/27,
                  הפועל יורוקאפ 24/25. מבנה יחסי בלבד.

למה structure_only ולא כיול:
  - עונה 26/27 מאוחרת לעונת הדמו (25/26) - מידע מהעתיד.
  - היוונים ביורו ומוערכים בטווחים של 25-40% ("€3.7M - €4.1M").
    מקור: "הערכות פיננסיות". השווה לעוגני מכבי, שם 20 מתוך 28
    תואמים בדיוק בין שני מקורות בלתי תלויים.
  - יורוקאפ היא ליגה אחרת. הפועל קפצה מ~6M ל-23M בעונה אחת.
    ובנוסף אין ל-11 מהשחקנים pir_lag ביורוליג - הם לא נכנסים
    לרגרסיה גם אם היינו רוצים.

כשמקורות חלוקים הרשומה נשמרת כטווח ולא נקודה: אי-ההסכמה היא
העדות היחידה שיש לנו על שגיאת המדידה.

הכל נטו כפי שפורסם. אין תיקון מאקרו, אין המרת מטבע, אין דפלציה.
מכפילי לאום (IL x2.0, זר x1.25) - ראו employer_cost_usd; הם
מדודים מהדאטה של 23/24 ו-24/25 ולא מוצהרים.

player_code נפתר בזמן הבנייה מתוך player_season.csv לפי player_name_el.
הקודים אינם נכתבים ידנית: בגרסה הקודמת 12 מתוך 28 היו שגויים, ושניים
הצביעו על שחקנים אחרים לגמרי (11970 = HARPER ולא BALDWIN). ה-join
החזיר 0 התאמות בשקט. הבנייה זורקת אם שם אינו נפתר ואינו ברשימת
NOT_IN_EUROLEAGUE.
"""

import pandas as pd
from paths import PROCESSED_DIR

# שמות שאינם בדאטה של היורוליג - ליגה מקומית בלבד, או לא נרשמו.
# רשימה מפורשת כדי שכל שם אחר שלא נפתר יזרוק ולא יישמט בשקט.
NOT_IN_EUROLEAGUE = {
    "יפתח זיו", "בוריסלב מלדנוב", "עוז בלייור",
}

SRC_IL = "BasketNews;Sport5;WallaSport;IsraelHayom"
SRC_GR = "BasketNews (estimates, via research report)"

# (he, el, code, list_a, list_b, is_israeli, employer_cost, notes)
# list_a = פרסום אינפוגרפי, list_b = פרסום טקסטואלי
TEL_2023 = [
    ("לורנצו בראון",     "BROWN, LORENZO",      None, 1_500_000, 1_600_000, 0, 2_000_000, ""),
    ("וויד בולדווין",    "BALDWIN IV, WADE",    None, 1_500_000, 1_500_000, 0, 1_875_000, ""),
    ("בונזי קולסון",     "COLSON, BONZIE",      None,   700_000,   900_000, 0, 1_125_000, ""),
    ("ג'וש ניבו",        "NEBO, JOSH",          None,   800_000,   800_000, 0, 1_000_000, ""),
    ("חסיאל ריברו",      "RIVERO, JASIEL",      None,   600_000,   600_000, 0,   750_000, ""),
    ("ג'יימס ווב",       "WEBB III, JAMES",     None,   400_000,   500_000, 0,   625_000, ""),
    ("תמיר בלאט",        "BLATT, TAMIR",        None,   400_000,   400_000, 1,   800_000, ""),
    ("ג'ון דיברתלומאו",  "DIBARTOLOMEO, JOHN",   None,   275_000,   400_000, 1,   800_000, "naturalised IL"),
    ("רומן סורקין",      "SORKIN, ROMAN",       None,   500_000,   375_000, 1,   750_000, ""),
    ("ג'ייק כהן",        "COHEN, JAKE",          None,   250_000,   300_000, 1,   600_000, "naturalised IL"),
    ("רפי מנקו",         "MENCO, RAFI",         None,   275_000,   300_000, 1,   600_000, ""),
    ("אנטוניוס קליבלנד", "CLEVELAND, ANTONIUS", None,   350_000,   250_000, 0,   312_500, ""),
]

TEL_2024 = [
    ("רומן סורקין",      "SORKIN, ROMAN",       None,      None,   850_000, 1, 1_700_000, ""),
    ("וונייה גבריאל",    "GABRIEL, WENYEN",     None,      None,   750_000, 0,   937_500, ""),
    ("רוקאס יוקובאיטיס", "JOKUBAITIS, ROKAS",   None,      None,   700_000, 0,   875_000, ""),
    ("ג'ון דיברתלומאו",  "DIBARTOLOMEO, JOHN",   None,      None,   650_000, 1, 1_300_000, "naturalised IL"),
    ("תמיר בלאט",        "BLATT, TAMIR",        None,      None,   650_000, 1, 1_300_000, ""),
    ("חסיאל ריברו",      "RIVERO, JASIEL",      None,      None,   600_000, 0,   750_000, ""),
    ("ליוואי רנדולף",    "RANDOLPH, LEVI",      None,      None,   500_000, 0,   625_000, ""),
    ("ג'יילן הורד",      "HOARD, JAYLEN",        None,      None,   400_000, 0,   500_000, ""),
    ("סייבן לי",         "LEE, SABEN",          None,      None,   400_000, 0,   500_000, ""),
    ("רפי מנקו",         "MENCO, RAFI",         None,      None,   300_000, 1,   600_000, ""),
    ("ג'ייק כהן",        "COHEN, JAKE",          None,      None,   280_000, 1,   560_000, "naturalised IL"),
    ("וויל ריימן",       "RAYMAN, WILLIAM",     None,      None,   225_000, 1,   281_250, "IL passport"),
]

TEL_2025 = [
    ("לוני ווקר",        "WALKER IV, LONNIE",   None, 2_200_000, 2_200_000, 0, None, ""),
    ("ג'יילן הורד",      "HOARD, JAYLEN",        None, 1_100_000, 1_000_000, 0, None, ""),
    ("ט.ג'יי ליף",       "LEAF, TJ",            None,   900_000, 1_000_000, 0, None, ""),
    ("רומן סורקין",      "SORKIN, ROMAN",       None,   900_000,   900_000, 1, None, ""),
    ("אושיי בריסט",      "BRISSETT, O'SHAE J",  None,   850_000,   950_000, 0, None, ""),
    ("ג'ף דאוטין",       "DOWTIN JR, JEFFREY",  None,   850_000,   800_000, 0, None, ""),
    ("תמיר בלאט",        "BLATT, TAMIR",        None,   700_000,   700_000, 1, None, ""),
    ("ג'ון דיברתלומאו",  "DIBARTOLOMEO, JOHN",   None,   650_000,   650_000, 1, None, "naturalised IL"),
    ("מרסיו סנטוס",      "SANTOS, MARCIO",      None,   600_000,   600_000, 0, None, ""),
    ("ג'ימי קלארק",      "CLARK III, JIMMY",    None,   400_000,   400_000, 0, None, ""),
    ("גור לביא",         "LAVI, GUR",           None,   400_000,   600_000, 1, None, "widest disagreement"),
    ("אורוש טריפונוביץ", "TRIFUNOVIC, UROS",     None,   250_000,   250_000, 0, None, ""),
    ("וויל ריימן",       "RAYMAN, WILLIAM",     None,   225_000,   225_000, 1, None, "IL passport"),
    ("קליפורד אומורוי",  "OMORUYI, CLIFFORD",   None,   150_000,      None, 0, None, "absent from list_b"),
    ("איפה לונדברג",     "LUNDBERG, IFFE",      None,   500_000,   500_000, 0, None, "mid-season signing, part-season"),
]

HTA_2025 = [
    ("ואסיליה מיצ'יץ'",  "MICIC, VASILIJE",      None, 6_000_000, 6_000_000, 0, None, ""),
    ("אלייז'ה בראיינט",  "BRYANT, ELIJAH",       None, 2_800_000, 2_800_000, 0, None, ""),
    ("דן אוטורו",        "OTURU, DAN",          None, 2_200_000, 2_200_000, 0, None, ""),
    ("ג'ונתן מוטלי",     "MOTLEY, JOHNATHAN",   None, 1_500_000, 1_500_000, 0, None, ""),
    ("אנטוניו בלייקני",  "BLAKENEY, ANTONIO",   None, 1_400_000, 1_400_000, 0, None, ""),
    ("ים מדר",           "MADAR, YAM",          None, 1_200_000, 1_200_000, 1, None, ""),
    ("ברונו קאבוקלו",    "CABOCLO, BRUNO",      None, 1_200_000, 1_200_000, 0, None, "traded HTA;DUB"),
    ("כריס ג'ונס",       "JONES, CHRIS",        None, 1_100_000, 1_100_000, 0, None, ""),
    ("קולין מלקולם",     "MALCOLM, COLLIN",     None, 1_100_000, 1_100_000, 0, None, ""),
    ("תומר גינת",        "GINAT, TOMER",        None,   500_000, 1_000_000, 1, None, "2x disagreement"),
    ("טאי אודיאסה",      "ODIASE, TAI",         None,   750_000,   850_000, 0, None, ""),
    ("איש ווינרייט",     "WAINRIGHT, ISH",      None,   750_000,   750_000, 0, None, ""),
    ("טיילר אניס",       "ENNIS, TYLER",         None,   700_000,   500_000, 0, None, ""),
    ("בר טימור",         "TIMOR, BAR",           None,   400_000,   400_000, 1, None, ""),
    ("גיא פלטין",        "PALATIN, GUY",        None,      None,   350_000, 1, None, "absent from list_a"),
    ("איתי שגב",         "SEGEV, ITAY",          None,      None,   300_000, 1, None, ""),
    ("יפתח זיו",         None,                     None,      None,   300_000, 1, None, "in squad, not registered for EL"),
    ("בוריסלב מלדנוב",   None,                     None,      None,   150_000, 0, None, "in squad, not registered for EL"),
    ("עוז בלייור",       None,                     None,      None,   130_000, 1, None, "in squad, not registered for EL"),
]

# --- structure_only ---
HTA_EUROCUP_2024 = [
    ("פטריק ברלי",   None, None, None, 1_800_000, 0, None, ""),
    ("ג'ונתן מוטלי", "MOTLEY, JOHNATHAN", None, None, 1_100_000, 0, None, ""),
    ("ברונו קאבוקלו","CABOCLO, BRUNO",    None, None, 1_250_000, 0, None, ""),
    ("בן בנטיל",     None, None, None,   750_000, 0, None, ""),
    ("איש ווינרייט", "WAINRIGHT, ISH",    None, None,   700_000, 0, None, ""),
    ("מרקוס פוסטר",  None, None, None,   600_000, 0, None, ""),
    ("תומר גינת",    "GINAT, TOMER",      None, None,   500_000, 1, None, ""),
    ("ג'ו רגלנד",    None, None, None,   450_000, 0, None, ""),
    ("פורוורד אנגולה",None, None, None,  450_000, 0, None, "sport5"),
    ("בר טימור",     "TIMOR, BAR",         None, None,   185_000, 1, None, ""),
    ("גיא פלטין",    "PALATIN, GUY",      None, None,   150_000, 1, None, ""),
    ("עוז בלייזר",   None, None, None,   130_000, 1, None, ""),
    ("מירון רוונה",  None, None, None,    70_000, 1, None, ""),
]

PAN_2025_EUR = [
    ("קנדריק נאן",        "NUNN, KENDRICK",     None, 4_500_000, 4_900_000, 0, None, "anchor"),
    ("נייג'ל הייז-דייוויס","HAYES-DAVIS, NIGEL", None, 4_000_000, 4_500_000, 0, None, "anchor"),
    ("גרשון יאבוסל",      "YABUSELE, GUERSCHON",None, 4_000_000, 4_000_000, 0, None, ""),
    ("מתיאס לסור",        "LESSORT, MATHIAS",   None, 2_700_000, 2_800_000, 0, None, "anchor"),
    ("קוסטאס סלוקאס",     "SLOUKAS, KOSTAS",    None, 2_000_000, 2_800_000, 0, None, ""),
    ("חואנצ'ו הרננגומז",  "HERNANGOMEZ, JUANCHO",None, 2_200_000, 2_500_000, 0, None, ""),
    ("אייזק בונגה",       "BONGA, ISAAC",       None, 2_150_000, 2_160_000, 0, None, ""),
    ("לורנצו בראון",      "BROWN, LORENZO",     None, 1_900_000, 1_900_000, 0, None, ""),
    ("צ'די עוסמן",        "OSMAN, CEDI",        None, 1_600_000, 1_700_000, 0, None, ""),
    ("מוסטפה פאל",        "FALL, MOUSTAPHA",    None, 1_600_000, 1_600_000, 0, None, ""),
    ("דינוס מיטוגלו",     "MITOGLOU, KONSTANTINOS", None, 750_000, 1_500_000, 0, None, "wide range"),
    ("ג'ריאן גרנט",       "GRANT, JERIAN",      None, 1_000_000, 1_400_000, 0, None, ""),
    ("ברנקו באדיו",       "BADIO, BRANCOU",     None, 1_300_000, 1_300_000, 0, None, ""),
    ("מריוס גריגוניס",    "GRIGONIS, MARIUS",   None, 1_100_000, 1_100_000, 0, None, ""),
    ("ניקוס רוגקאבופולוס",None, None, 1_100_000, 1_100_000, 0, None, ""),
    ("עומר יורטסבן",      "YURTSEVEN, OMER",    None, 1_000_000, 1_000_000, 0, None, ""),
    ("יואניס פאפאפטרו",   "PAPAPETROU, IOANNIS",None,   800_000,   800_000, 0, None, ""),
    ("ואסיליס טוליופולוס",None, None,   500_000,   500_000, 0, None, ""),
    ("פנאיוטיס קאלאיצאקיס",None, None,  350_000,   450_000, 0, None, ""),
    ("דימיטריס מוראיטיס", None, None,   200_000,   350_000, 0, None, ""),
    ("לפטריס מנצוקאס",    None, None,   300_000,   300_000, 0, None, ""),
    ("אלכסנדרוס סאמודורוב",None, None,  200_000,   200_000, 0, None, ""),
    ("יואניס קוזלוגלו",   None, None,   150_000,   150_000, 0, None, ""),
]

OLY_2025_EUR = [
    ("סשה וזנקוב",        "VEZENKOV, SASHA",  None, 3_700_000, 4_100_000, 0, None, "anchor"),
    ("אוון פורנייה",      "FOURNIER, EVAN",    None, 2_100_000, 2_500_000, 0, None, ""),
    ("מוסטפה פאל",        "FALL, MOUSTAPHA",   None, 1_700_000, 1_850_000, 0, None, "extended tenure"),
    ("ניקולה מילוטינוב",  "MILUTINOV, NIKOLA", None, 1_600_000, 1_650_000, 0, None, ""),
    ("טיילר דורסי",       "DORSEY, TYLER",     None, 1_400_000, 1_500_000, 0, None, ""),
    ("אלק פיטרס",         "PETERS, ALEC",      None, 1_100_000, 1_250_000, 0, None, ""),
    ("לוקה וילדוזה",      "VILDOZA, LUCA",     None, 1_000_000, 1_200_000, 0, None, ""),
    ("קוסטאס פאפאניקולאו","PAPANIKOLAOU, KOSTAS", None, 1_100_000, 1_200_000, 0, None, "extended tenure"),
    ("תומאס וולקאפ",      "WALKUP, THOMAS",    None,   950_000, 1_200_000, 0, None, "extended tenure"),
    ("פיליפ פטרושב",      "PETRUSEV, FILIP",   None, 1_000_000, 1_000_000, 0, None, ""),
    ("נייג'ל וויליאמס-גוס","WILLIAMS-GOSS, NIGEL", None, 850_000, 1_100_000, 0, None, ""),
    ("יאנוליס לארנצאקיס", "LARENTZAKIS, GIANNOULIS", None, 650_000, 750_000, 0, None, ""),
    ("שאקיל מקיסיק",      "MCKISSIC, SHAQUIELLE", None, 650_000, 650_000, 0, None, ""),
    ("מוזס רייט",         "WRIGHT, MOSES",     None,   500_000,   600_000, 0, None, ""),
    ("קינן אוונס",        "EVANS, KEENAN",     None,   500_000,   500_000, 0, None, ""),
]

BLOCKS = [
    # (rows, club, season, usage, currency, league, confidence, source)
    (TEL_2023,         "TEL", 2023, "calibrate",      "USD", "EL", "reported",  SRC_IL),
    (TEL_2024,         "TEL", 2024, "calibrate",      "USD", "EL", "reported",  SRC_IL),
    (TEL_2025,         "TEL", 2025, "calibrate",      "USD", "EL", "reported",  SRC_IL),
    (HTA_2025,         "HTA", 2025, "test",           "USD", "EL", "reported",  SRC_IL),
    (HTA_EUROCUP_2024, "HTA", 2024, "structure_only", "USD", "EC", "reported",  SRC_IL),
    (PAN_2025_EUR,     "PAN", 2025, "structure_only", "EUR", "EL", "estimated", SRC_GR),
    (OLY_2025_EUR,     "OLY", 2025, "structure_only", "EUR", "EL", "estimated", SRC_GR),
]


def resolve_codes(df: pd.DataFrame) -> pd.DataFrame:
    """פותר player_code לפי שם מול player_season.csv.
    זורק על כל שם שלא נפתר ואינו ב-NOT_IN_EUROLEAGUE."""
    pl = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})

    def norm(x):
        return "".join(ch for ch in str(x).upper() if ch.isalpha())

    lookup = (pl[["player_code", "player_name"]].drop_duplicates()
                .assign(k=lambda d: d.player_name.map(norm)))
    by_key = dict(zip(lookup.k, lookup.player_code))

    df = df.copy()
    df["player_code"] = df.player_name_el.map(
        lambda n: by_key.get(norm(n)) if pd.notna(n) else None)

    unresolved = df[df.player_code.isna() &
                    ~df.player_name_he.isin(NOT_IN_EUROLEAGUE) &
                    df.player_name_el.notna()]
    if len(unresolved):
        print("\n[FAIL] שמות שלא נפתרו לקוד:")
        print(unresolved[["club", "season", "player_name_el"]].to_string(index=False))
        raise RuntimeError("שם עוגן ללא התאמה ב-player_season.csv")

    n = df.player_code.notna().sum()
    print(f"[CHECK] נפתרו {n} מתוך {len(df)} עוגנים לקוד אמיתי")
    return df


def main():
    rows = []
    for data, club, season, usage, cur, league, conf, src in BLOCKS:
        for he, el, code, a, b, isr, emp, note in data:
            vals = [v for v in (a, b) if v is not None]
            lo, hi = min(vals), max(vals)
            mid = (lo + hi) / 2
            rows.append(dict(
                season=season, club=club, usage=usage,
                player_name_he=he, player_name_el=el, player_code=code,
                list_a=a, list_b=b,
                salary_low=lo, salary_high=hi, salary_mid=mid,
                is_range=int(lo != hi),
                rel_spread=round((hi - lo) / mid, 4),
                employer_cost=emp,
                employer_multiple=round(emp / mid, 3) if emp else None,
                currency=cur, basis="net", league=league,
                confidence=conf, is_israeli=isr,
                fx_adjusted=0, contract_years=1,
                source=src, notes=note,
            ))

    df = resolve_codes(pd.DataFrame(rows))

    if not PROCESSED_DIR.exists():
        raise SystemExit(f"PROCESSED_DIR לא קיים: {PROCESSED_DIR}")
    out = PROCESSED_DIR / "salary_anchors.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    if not out.exists():
        raise SystemExit(f"הכתיבה דווחה כהצלחה אך הקובץ אינו קיים: {out}")

    print(f"wrote {out.resolve()}\n  {len(df)} שורות\n")
    print("--- שכבות ---")
    print(df.groupby(["usage", "club", "season"]).agg(
        n=("salary_mid", "size"),
        total=("salary_mid", "sum"),
        cur=("currency", "first"),
    ).to_string())

    cal = df[df.usage == "calibrate"]
    print(f"\n--- סט הכיול: {len(cal)} תצפיות, "
          f"{cal.player_code.nunique()} שחקנים ייחודיים ---")
    print(cal.groupby("season").salary_mid.agg(["size", "sum", "median"]).to_string())

    rep = df[df.confidence == "reported"]
    est = df[df.confidence == "estimated"]
    print(f"\n--- אי-ודאות לפי מקור ---")
    print(f"  reported  n={len(rep):>3}  חולקים={int(rep.is_range.sum()):>3}  "
          f"פיזור ממוצע={rep.rel_spread.mean():.4f}")
    print(f"  estimated n={len(est):>3}  חולקים={int(est.is_range.sum()):>3}  "
          f"פיזור ממוצע={est.rel_spread.mean():.4f}")

    emp = df[df.employer_multiple.notna()]
    print(f"\n--- מכפיל עלות מעביד (מדוד, n={len(emp)}) ---")
    print(emp.groupby("is_israeli").employer_multiple.agg(
        ["size", "mean", "min", "max"]).round(3).to_string())

    # מסלולי שכר: אותו שחקן על פני עונות בסט הכיול
    multi = cal[cal.player_code.notna()].groupby("player_code").filter(
        lambda g: g.season.nunique() > 1)
    if len(multi):
        print(f"\n--- מסלולי שכר ({multi.player_code.nunique()} שחקנים) ---")
        piv = multi.pivot_table(index="player_name_el", columns="season",
                                values="salary_mid")
        print(piv.to_string())


if __name__ == "__main__":
    main()