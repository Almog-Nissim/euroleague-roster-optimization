import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"C:\Users\a9lmo\PycharmProjects\PythonProject\dashboard\src\Headline.jsx"
L = open(p, encoding="utf-8").read().splitlines()
for i, s in enumerate(L, 1):
    if any(k in s for k in ["CI95", "caveat", "ci[", "ci [", ".ci", "ניצחונות בעונה"]):
        print(f"{i:>4} | {s.strip()[:110]}")
