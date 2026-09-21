"""
methods_pdf.py
--------------
בונה `METHODS.pdf` מ-`METHODS.md`. קיים כדי שה-PDF לא יתיישן שוב בשקט.

--------------------------------------------------------------------
למה סקריפט ולא כלי מהמדף
--------------------------------------------------------------------
במכונה הזאת אין pandoc, אין weasyprint, אין wkhtmltopdf ואין LaTeX.
מה שכן יש הוא Chrome, וזה למעשה **המנוע הטוב ביותר** לעברית: יישום
bidi מלא, שבירת שורות נכונה, וטיפול בקוד לטיני בתוך פסקה עברית.
לכן: markdown -> HTML -> `chrome --headless --print-to-pdf`.

ההמרה מכסה בכוונה רק את התת-קבוצה ש-`METHODS.md` משתמשת בה —
כותרות, מודגש, קוד inline, בלוקי קוד, טבלאות, ציטוטים, רשימות,
וקווי הפרדה. היא לא ממיר markdown כללי ולא מתיימרת להיות.

--------------------------------------------------------------------
🔴 הכלל שנלמד כאן
--------------------------------------------------------------------
`METHODS.pdf` נוצר ביום 8 ונשאר בשורש בלי מחולל, ולכן כשהמסמך עבר
לספק `market` הוא הפך לגרסה סותרת שאיש לא יכול לבנות מחדש. **ארטיפקט
מקומט בלי סקריפט מייצר הוא סעיף 8א.**

הרצה:  python src/methods_pdf.py
"""

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_MD = ROOT / "METHODS.md"
OUT_PDF = ROOT / "METHODS.pdf"

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 18mm 16mm; }
html { direction: rtl; }
body {
  font-family: "Segoe UI", Arial, "Noto Sans Hebrew", sans-serif;
  font-size: 10.5pt; line-height: 1.65; color: #1a1a1a;
}
h1 { font-size: 19pt; margin: 0 0 4pt; border-bottom: 2px solid #1a1a1a;
     padding-bottom: 5pt; }
h2 { font-size: 14pt; margin: 20pt 0 6pt; border-bottom: 1px solid #bbb;
     padding-bottom: 3pt; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; page-break-after: avoid; }
p  { margin: 5pt 0; }
ul { margin: 5pt 0; padding-right: 18pt; padding-left: 0; }
li { margin: 2pt 0; }
hr { border: 0; border-top: 1px solid #ddd; margin: 14pt 0; }

/* 🔴 קוד וטבלאות חייבים להיות LTR. בלוק קוד ב-RTL מתהפך ונעשה
   חסר משמעות — זה בדיוק מה שה-CLAUDE.md מזהיר עליו בטקסט. */
code, pre {
  font-family: Consolas, "Courier New", monospace;
  direction: ltr; unicode-bidi: isolate;
}
code { background: #f2f2f2; padding: 1px 4px; border-radius: 3px;
       font-size: 9.5pt; }
pre  { background: #f7f7f7; border: 1px solid #e0e0e0; border-radius: 4px;
       padding: 8pt 10pt; overflow-x: auto; white-space: pre;
       text-align: left; font-size: 9pt; line-height: 1.45;
       page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }

table { border-collapse: collapse; margin: 8pt 0; width: 100%;
        font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 4pt 7pt; text-align: right;
         vertical-align: top; }
th { background: #f0f0f0; font-weight: 600; }

blockquote { margin: 8pt 0; padding: 6pt 12pt 6pt 10pt;
             border-right: 3px solid #999; background: #fafafa; }
blockquote p { margin: 3pt 0; }
strong { font-weight: 600; }
"""


def inline(s: str) -> str:
    """קוד inline קודם, כדי שמודגש בתוך קוד לא יפורש."""
    out, parts = [], re.split(r"(`[^`]+`)", s)
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
        else:
            e = html.escape(part)
            e = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e)
            e = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", e)
            out.append(e)
    return "".join(out)


def convert(md: str) -> str:
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]

        if ln.startswith("```"):                      # בלוק קוד
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf))
                       + "</code></pre>")
            continue

        if re.match(r"^\s*\|.*\|\s*$", ln):           # טבלה
            rows = []
            while i < len(lines) and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = [r for r in rows
                    if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in r)]
            if not body:
                continue
            head, rest = body[0], body[1:]
            t = ["<table><thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rest:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r)
                         + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        if ln.startswith(">"):                        # ציטוט
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip())
                i += 1
            para = " ".join(x for x in buf if x)
            out.append(f"<blockquote><p>{inline(para)}</p></blockquote>")
            continue

        if re.match(r"^\s*[-*]\s+", ln):              # רשימה
            buf = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in buf)
                       + "</ul>")
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", ln)        # כותרת
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if re.match(r"^\s*---+\s*$", ln):             # קו הפרדה
            out.append("<hr>")
            i += 1
            continue

        if ln.strip() == "":
            i += 1
            continue

        buf = []                                      # פסקה
        while i < len(lines) and lines[i].strip() and \
                not re.match(r"^(#{1,4}\s|```|>|\s*[-*]\s|\s*\|)", lines[i]) and \
                not re.match(r"^\s*---+\s*$", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>" + inline("<br>".join(buf)).replace(
                "&lt;br&gt;", "<br>") + "</p>")

    return ("<!doctype html><html dir=\"rtl\" lang=\"he\"><head>"
            "<meta charset=\"utf-8\"><title>METHODS</title>"
            f"<style>{CSS}</style></head><body>" + "\n".join(out)
            + "</body></html>")


def main() -> int:
    """🔴 תוקן אחרי code review. הגרסה הקודמת מחקה את METHODS.pdf המקומט
    **לפני** ההמרה, כך ש-Chrome שנכשל השאיר את הריפו בלי PDF, וכתבה
    _methods_build.html לשורש, שקריסה השאירה שם כקובץ תועה. עכשיו הכול
    נבנה בתיקייה זמנית, והקובץ המקומט מוחלף רק אחרי הצלחה, בפעולה אחת.
    """
    import tempfile
    if not SRC_MD.exists():
        print(f"❌ לא נמצא {SRC_MD}")
        return 1
    exe = next((c for c in CHROME if Path(c).exists()), None)
    if exe is None:
        print("❌ לא נמצא Chrome או Edge. אין ממיר PDF במכונה הזאת. "
              "METHODS.pdf לא נגע.")
        return 1

    md = SRC_MD.read_text(encoding="utf-8")
    before = OUT_PDF.stat().st_size if OUT_PDF.exists() else None
    with tempfile.TemporaryDirectory() as td:
        tmp_html = Path(td) / "methods.html"
        tmp_pdf = Path(td) / "methods.pdf"
        tmp_html.write_text(convert(md), encoding="utf-8")
        cmd = [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
               f"--print-to-pdf={tmp_pdf}", tmp_html.resolve().as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        ok = tmp_pdf.exists() and tmp_pdf.stat().st_size > 20_000
        if ok:
            shutil.copyfile(tmp_pdf, OUT_PDF)      # הקובץ המקומט מוחלף רק כאן

    print(f"  מקור : {SRC_MD.name}  ({len(md):,} תווים)")
    print(f"  מנוע : {Path(exe).name}")
    if ok:
        was = f" · הקודם {before/1024:.0f} KB" if before is not None else ""
        print(f"  ✅ נכתב: {OUT_PDF.name}  ({OUT_PDF.stat().st_size/1024:.0f} KB){was}")
    else:
        print(f"  ❌ לא נוצר PDF תקין. rc={r.returncode}. "
              f"METHODS.pdf הקיים לא נגע.")
        print((r.stderr or "")[-600:])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
