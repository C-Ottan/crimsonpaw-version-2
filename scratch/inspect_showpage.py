import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
matches = re.findall(r"function showPage\([^\)]*\)\s*\{", text)
print("showPage function matches:", len(matches))

idx = text.find("function showPage(")
if idx != -1:
    print(text[idx:idx+1500])
