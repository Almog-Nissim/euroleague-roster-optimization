import re
t = open(r"C:\Users\a9lmo\PycharmProjects\PythonProject\dashboard\dist\roster_sweep.json", encoding="utf-8").read()
print("NaN חשוף:", len(re.findall(r'(?<![\w"])NaN(?![\w"])', t)))
print("nan כלשהו:", len(re.findall("nan", t, re.I)))
for m in list(re.finditer("nan", t, re.I))[:3]:
    print("  ...", t[max(0,m.start()-45):m.start()+8])
