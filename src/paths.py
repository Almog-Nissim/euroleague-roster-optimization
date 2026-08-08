"""
paths.py
--------
מקור אמת יחיד לנתיבים בפרויקט. כל סקריפט ב-src/ מייבא מכאן.
אין יותר נתיבים יחסיים ואין יותר שתי תיקיות data.

מיקום: src/paths.py
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # .../PythonProject/src
ROOT_DIR = os.path.dirname(BASE_DIR)                    # .../PythonProject

DATA_DIR      = os.path.join(ROOT_DIR, "data")
RAW_DIR       = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)