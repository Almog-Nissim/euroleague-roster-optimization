# src/audits/patch_meta.py — חמשת התיקונים של יום 14, עם אימות
import re, shutil, pathlib

P = pathlib.Path(r"C:\Users\a9lmo\PycharmProjects\PythonProject\src\roster_sweep.py")
shutil.copy(P, P.with_suffix(".py.bak"))
src = P.read_text(encoding="utf-8")
orig = src
ok = []

# 1 — תווית העונה: SEASON היא שנת התחלה
a, b = 'f"{SEASON-1}/{SEASON-2000}"', 'f"{SEASON}/{(SEASON + 1) % 100:02d}"'
if a in src:
    src = src.replace(a, b); ok.append("1 label")

# 2 — saturation_note: המאגר לא נגמר
new2 = (
    'saturation_note="מעל נקודה זו התשואה השולית אינה תורמת עוד. "\n'
    '                                  "הניצול נשאר 99.1% והמנוע בוחר 12 "\n'
    '                                  "שחקנים, המאגר אינו נגמר, הכסף "\n'
    '                                  "מפסיק לקנות שיפור. תשואה פוחתת, "\n'
    '                                  "לא מיצוי.",\n'
    '                  '
)
src, n = re.subn(r'saturation_note=.*?,\n\s*(?=shape_caveat=)', new2, src, flags=re.S)
if n: ok.append("2 saturation_note")

# 3 — shape_caveat: בלי מספרים שלא שוחזרו
new3 = (
    'shape_caveat="צורת העקומה לפני הרוויה אינה יציבה: "\n'
    '                               "ב-budget_curve (20.8) התשואה השולית "\n'
    '                               "שלילית בנקודות מפוזרות לאורך הטווח "\n'
    '                               "בשתי העונות שנבדקו. הריצה ההיא קדמה "\n'
    '                               "לתיקון האינדקס של יום 12 ולא שוחזרה "\n'
    '                               "תחת הקוד הנוכחי. הסייג נוגע לאמינות "\n'
    '                               "הצורה, לא לעקומה המוצגת.",\n'
    '                  '
)
src, n = re.subn(r'shape_caveat=.*?,\n\s*(?=pool_size=)', new3, src, flags=re.S)
if n: ok.append("3 shape_caveat")

# 4 — fair_compare_warning: סייג 11 מ-20
a4 = '"usage_constrained_results.csv.",'
b4 = ('"usage_constrained_results.csv. "\n'
      '                                       "נמדד על 11 מ-20 מועדונים "\n'
      '                                       "(סגלים ≤16 בלבד), הנוטים "\n'
      '                                       "להיות עניים יותר.",')
if a4 in src:
    src = src.replace(a4, b4); ok.append("4 fair_compare_warning")

# 5 — דגל ירידה: השוואה מעוגל מול מעוגל
a5, b5 = 'q >= pts[-2]["q"] - 1e-6', 'round(q, 2) >= pts[-2]["q"] - 1e-9'
if a5 in src:
    src = src.replace(a5, b5); ok.append("5 mono flag")

print("בוצעו:", ok)
missing = {"1 label", "2 saturation_note", "3 shape_caveat",
           "4 fair_compare_warning", "5 mono flag"} - set(ok)
if missing:
    raise SystemExit(f"נכשל — לא נמצאו: {sorted(missing)} · הקובץ לא נכתב")

compile(src, str(P), "exec")          # נופל אם התחביר נשבר
P.write_text(src, encoding="utf-8")
print(f"נכתב. גיבוי: {P.with_suffix('.py.bak').name} · "
      f"{len(orig)} → {len(src)} תווים")