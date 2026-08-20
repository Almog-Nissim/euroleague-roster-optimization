"""
el_api.py — שכבת רשת משותפת לכל המשיכות מיורוליג.

הסיבה שהקובץ הזה קיים: ההרצה של 2018 נפלה שש פעמים על אותו gamecode
והדפיסה הודעת שגיאה *ריקה*. אנחנו לא יודעים אם זה היה 429 — הנחנו.
כאן כל כישלון נתפס עם type, repr, status_code וגוף התגובה.

לא נבדק מול ה-API האמיתי (אין גישת רשת בסביבה שבה נכתב).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

USER_AGENT = "euroleague-roster-optimization/research (contact: almog)"
DEFAULT_TIMEOUT = 30


@dataclass
class FetchResult:
    """תוצאה של ניסיון משיכה — הצלחה או כישלון, תמיד עם פרטים."""
    ok: bool
    url: str
    status_code: Optional[int] = None
    payload: Any = None
    text_head: str = ""
    content_type: str = ""
    error_type: str = ""
    error_repr: str = ""
    attempts: int = 0
    elapsed_s: float = 0.0
    history: list = field(default_factory=list)

    def describe(self) -> str:
        if self.ok:
            return f"OK  {self.status_code}  {self.url}"
        lines = [
            f"FAIL {self.url}",
            f"  status_code : {self.status_code}",
            f"  error_type  : {self.error_type or '(none)'}",
            f"  error_repr  : {self.error_repr or '(none)'}",
            f"  content_type: {self.content_type or '(none)'}",
            f"  attempts    : {self.attempts}",
            f"  body[:500]  : {self.text_head!r}",
        ]
        return "\n".join(lines)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, */*"})
    return s


def fetch(
    session: requests.Session,
    url: str,
    params: dict | None = None,
    retries: int = 4,
    sleep: float = 0.8,
    timeout: int = DEFAULT_TIMEOUT,
    parse_json: bool = True,
) -> FetchResult:
    """
    משיכה עם ניסיונות חוזרים. כל ניסיון נרשם.

    ההבדל המהותי מהגרסה הקודמת: 429 מקבל השהיה גדלה, אבל 404/500
    *לא* חוזרים בכלל — אין טעם לנסות שוב משאב שלא קיים. זה בדיוק
    מה שהסגיר את 2018: ניסיון חוזר על שגיאה שאינה זמנית.
    """
    t0 = time.time()
    res = FetchResult(ok=False, url=url)

    for attempt in range(1, retries + 1):
        res.attempts = attempt
        try:
            r = session.get(url, params=params, timeout=timeout)
            res.status_code = r.status_code
            res.content_type = r.headers.get("Content-Type", "")
            res.text_head = (r.text or "")[:500]
            res.history.append({"attempt": attempt, "status": r.status_code, "len": len(r.text or "")})

            # שגיאות שאינן זמניות — לא חוזרים עליהן
            if r.status_code in (400, 401, 403, 404, 410):
                res.error_type = "HTTPPermanent"
                res.error_repr = f"HTTP {r.status_code} (not retried — resource missing or forbidden)"
                res.elapsed_s = time.time() - t0
                return res

            if r.status_code == 429:
                wait = sleep * (2 ** attempt)
                res.error_type = "RateLimited"
                res.error_repr = f"HTTP 429, backing off {wait:.1f}s"
                time.sleep(wait)
                continue

            if r.status_code >= 500:
                res.error_type = "HTTPServerError"
                res.error_repr = f"HTTP {r.status_code}"
                time.sleep(sleep * attempt)
                continue

            if not (r.text or "").strip():
                res.error_type = "EmptyBody"
                res.error_repr = f"HTTP {r.status_code} with empty body"
                time.sleep(sleep * attempt)
                continue

            if parse_json:
                try:
                    res.payload = r.json()
                except json.JSONDecodeError as e:
                    # זה החשוד המרכזי ב-2018: תגובת 200 שאינה JSON
                    res.error_type = "JSONDecodeError"
                    res.error_repr = repr(e)
                    res.elapsed_s = time.time() - t0
                    return res
            else:
                res.payload = r.text

            res.ok = True
            res.elapsed_s = time.time() - t0
            time.sleep(sleep)
            return res

        except requests.RequestException as e:
            res.error_type = type(e).__name__
            res.error_repr = repr(e)
            res.history.append({"attempt": attempt, "exception": type(e).__name__})
            time.sleep(sleep * attempt)

    res.elapsed_s = time.time() - t0
    return res


# מועמדי endpoint. הסקריפטים בודקים מי מהם עונה במקום להניח.
BOXSCORE_ENDPOINTS = [
    ("live_api", "https://live.euroleague.net/api/Boxscore", {"gamecode": "{gamecode}", "seasoncode": "E{season}"}),
]

SCHEDULE_ENDPOINTS = [
    ("v2_games", "https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/E/seasons/E{season}/games", {}),
    ("v1_results", "https://api-live.euroleague.net/v1/results", {"seasonCode": "E{season}"}),
    ("live_results", "https://live.euroleague.net/api/Results", {"seasoncode": "E{season}"}),
    ("live_schedules", "https://live.euroleague.net/api/Schedules", {"seasoncode": "E{season}"}),
]


def render(template: str, **kw) -> str:
    return template.format(**kw)