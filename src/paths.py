"""
paths.py
--------
מקור אמת יחיד לנתיבים בפרויקט. כל סקריפט ב-src/ מייבא מכאן.
אין יותר נתיבים יחסיים ואין יותר שתי תיקיות data.

מיקום: src/paths.py
מחזיר אובייקטי Path (pathlib), לא מחרוזות.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent      # .../PythonProject/src
ROOT_DIR = BASE_DIR.parent                      # .../PythonProject

DATA_DIR      = ROOT_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)