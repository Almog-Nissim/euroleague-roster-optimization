import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"C:\Users\a9lmo\PycharmProjects\PythonProject\dashboard\src\EngineVsReality.jsx"
L = open(p, encoding="utf-8").read().splitlines()
keys = ["המנוע מול כל המועדונים", "נקודת האקראי", "הצג נתונים מלאים",
        "סגל אקראי", "return (", "<section", "</section", "{/*"]
for i, s in enumerate(L, 1):
    for k in keys:
        if k in s:
            print(f"{i:>4} | {s.strip()[:100]}")
            break
print("סה\"כ שורות:", len(L))
