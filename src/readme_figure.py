"""
readme_figure.py
----------------
התרשים של ה-README: היתרון של המנוע לכל עונת-מועדון, ממוין, עם החציון.
נוצר מ-headline_exact.csv — כלומר מאותו קובץ שממנו נגזרת הכותרת של v1.0.

למה SVG שנכתב ידנית ולא matplotlib: matplotlib לא מותקן, ותלות חדשה
בפרויקט בשביל תרשים אחד אינה שווה את זה. SVG חד בכל גודל, ו-GitHub מציג
אותו ב-README. יש לו גם מצב כהה משלו דרך prefers-color-scheme.

הרצה:  python src/readme_figure.py   ->  figures/headline_advantage.svg
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "headline_advantage.svg"
SRC = PROCESSED_DIR / "headline_exact.csv"
WINS = PROCESSED_DIR / "wins_conversion.csv"

# מהפלטה המאומתת של skill ה-dataviz (series-1, surfaces, text tokens)
LIGHT = dict(bg="#fcfcfb", bar="#2a78d6", ink="#0b0b0b", ink2="#52514e",
             grid="#e6e5e1", ref="#52514e")
DARK = dict(bg="#1a1a19", bar="#3987e5", ink="#ffffff", ink2="#c3c2b7",
            grid="#34332f", ref="#c3c2b7")

W = 820
ML, MR, MT, MB = 110, 40, 92, 58      # שוליים: תוויות משמאל, כותרת למעלה
ROW, BAR = 16, 12                     # פס של 16, עמודה של 12 -> 4 מרווח (>= 2)
R = 4                                 # קצה מעוגל, בסיס ישר


def bar_path(x0, y, w, h, r):
    """עמודה אופקית: ישרה בבסיס (x0), מעוגלת בקצה הנתונים."""
    r = min(r, w, h / 2)
    x1 = x0 + w
    return (f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} "
            f"Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
            f"V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} "
            f"H{x0:.1f} Z")


def main() -> int:
    d = pd.read_csv(SRC)
    d = d[d.sol_status == 1].copy()
    d["label"] = d.season.astype(str) + " " + d.club
    d["v"] = d.adv_F_exact * 100
    d = d.sort_values("v", ascending=False).reset_index(drop=True)
    med = float(d.v.median())
    wc = pd.read_csv(WINS)
    cap = wc[wc.engine == "מאולץ"].iloc[0]

    n = len(d)
    H = MT + n * ROW + MB
    pw = W - ML - MR
    vmax = 10 * (int(d.v.max() // 10) + 1)
    sx = pw / vmax

    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d" '
             f'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif">')
    s.append('<title id="t">Engine vs actual club on the same budget: production '
             'advantage per club-season</title>')
    s.append(f'<desc id="d">{n} club-seasons, 2024/25 and 2025/26, sorted. All '
             f'{n} are positive. Median {med:.1f}%, about {cap.wins:+.1f} wins per '
             f'season.</desc>')
    css = []
    for mode, c in (("light", LIGHT), ("dark", DARK)):
        rules = (f".bg{{fill:{c['bg']}}} .bar{{fill:{c['bar']}}} "
                 f".ink{{fill:{c['ink']}}} .ink2{{fill:{c['ink2']}}} "
                 f".grid{{stroke:{c['grid']}}} .ref{{stroke:{c['ref']}}}")
        css.append(rules if mode == "light"
                   else f"@media (prefers-color-scheme: dark){{{rules}}}")
    s.append("<style>" + " ".join(css) + "</style>")
    s.append(f'<rect class="bg" width="{W}" height="{H}"/>')

    # כותרת ותת-כותרת — בטקסט, לא בצבע הסדרה
    s.append(f'<text class="ink" x="{ML}" y="30" font-size="17" font-weight="600">'
             f'Same budget, the engine\'s roster out-produces the club\'s in '
             f'{int((d.v > 0).sum())} of {n}</text>')
    s.append(f'<text class="ink2" x="{ML}" y="52" font-size="13">Production '
             f'advantage of the engine over the club\'s actual roster, per '
             f'club-season · v1.0, proven optimal</text>')

    # רשת ציר X — רצסיבית, נסוגה
    top, bot = MT - 8, MT + n * ROW
    for t in range(0, vmax + 1, 10):
        x = ML + t * sx
        s.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" '
                 f'y2="{bot}" stroke-width="1"/>')
        s.append(f'<text class="ink2" x="{x:.1f}" y="{bot + 18}" font-size="11" '
                 f'text-anchor="middle">{t}%</text>')

    # העמודות
    for i, r in d.iterrows():
        y = MT + i * ROW + (ROW - BAR) / 2
        w = max(r.v * sx, 1.0)
        s.append(f'<path class="bar" d="{bar_path(ML, y, w, BAR, R)}">'
                 f'<title>{r.label}: {r.v:+.1f}%</title></path>')
        s.append(f'<text class="ink2" x="{ML - 8}" y="{y + BAR - 2:.1f}" '
                 f'font-size="11" text-anchor="end">{r.label}</text>')

    # קו החציון, עם תווית ישירה
    mx = ML + med * sx
    s.append(f'<line class="ref" x1="{mx:.1f}" y1="{top - 6}" x2="{mx:.1f}" '
             f'y2="{bot}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    s.append(f'<text class="ink" x="{mx + 6:.1f}" y="{top + 2}" font-size="12" '
             f'font-weight="600">median {med:.1f}% ≈ {cap.wins:+.2f} wins/season '
             f'[{cap.lo:+.2f}, {cap.hi:+.2f}]</text>')

    # כותרת ציר ומקור
    s.append(f'<text class="ink2" x="{ML + pw / 2:.1f}" y="{H - 14}" font-size="11" '
             f'text-anchor="middle">advantage in production (engine ÷ club − 1) · '
             f'source: data/processed/headline_exact.csv</text>')
    s.append("</svg>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(s), encoding="utf-8")
    ok = n == 38 and abs(med - 18.92) < 0.05
    print(f"  {'✅' if ok else '❌'} {n} עונות-מועדון · חציון {med:.2f}% "
          f"(צפוי 18.92) · נכתב {OUT.relative_to(ROOT)}  "
          f"({OUT.stat().st_size / 1024:.0f} KB)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
