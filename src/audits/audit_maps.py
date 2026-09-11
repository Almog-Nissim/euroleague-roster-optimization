# src/audits/audit_maps.py
import ast, pathlib

SRC = pathlib.Path(r"C:\Users\a9lmo\PycharmProjects\PythonProject\src")
found = {}

for p in sorted(SRC.rglob("*.py")):
    if ".venv" in str(p) or p.name == "audit_maps.py":
        continue
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        print(f"  ! לא נקרא: {p.name}")
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        try:
            d = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        flat = {str(x) for x in d.keys()} | {str(x) for x in d.values()}
        if "CSK" not in flat:
            continue
        for t in node.targets:
            if isinstance(t, ast.Name):
                m = d if "CSK" in {str(v) for v in d.values()} \
                      else {v: k for k, v in d.items()}
                found[(p.name, t.id, node.lineno)] = m

print(f"נמצאו {len(found)} מיפויים\n" + "=" * 70)
if not found:
    raise SystemExit("לא נמצא כלום — בדוק את SRC")

base_key = next(k for k in found if k[0] == "club_codes.py")
base = found[base_key]
print(f"בסיס: {base_key[0]}:{base_key[2]} ({base_key[1]}) · "
      f"{len(base)} שמות · {len(set(base.values()))} קודים\n")

diffs = 0
for k, m in sorted(found.items()):
    if k == base_key:
        continue
    miss = sorted(set(base.values()) - set(m.values()))
    extra = sorted(set(m.values()) - set(base.values()))
    conflict = sorted(n for n in set(m) & set(base) if m[n] != base[n])
    ok = not (miss or extra or conflict)
    diffs += 0 if ok else 1
    print(f"{'OK  ' if ok else 'DIFF'} {k[0]}:{k[2]} ({k[1]}) n={len(m)}")
    if miss:
        print(f"       קודים חסרים: {miss}")
    if extra:
        print(f"       קודים עודפים: {extra}")
    if conflict:
        print(f"       שם->קוד סותר: {[(n, m[n], base[n]) for n in conflict]}")

print("=" * 70)
print(f"נבדלים: {diffs} מתוך {len(found) - 1}")