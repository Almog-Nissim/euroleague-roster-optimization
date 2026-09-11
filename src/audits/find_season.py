import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import glob
for p in glob.glob(r"C:\Users\a9lmo\PycharmProjects\PythonProject\dashboard\src\*.jsx"):
    for i, s in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
        if "season" in s and ("{" in s or "join" in s) and "//" not in s[:6]:
            print(f"{p.split(chr(92))[-1]}:{i} | {s.strip()[:95]}")
