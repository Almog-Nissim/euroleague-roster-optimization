import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"C:\Users\a9lmo\PycharmProjects\PythonProject\dashboard\src\EngineVsReality.jsx"
L = open(p, encoding="utf-8").read().splitlines()
for i in range(100, 163):
    print(f"{i+1:>4} | {L[i]}")
