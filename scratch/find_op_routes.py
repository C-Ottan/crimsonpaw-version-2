import re

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

for m in re.finditer(r'@app\.route\([\'"](/m/[^\'"]*)[\'"]', text):
    line_no = text[:m.start()].count('\n') + 1
    print(f'Line {line_no}: {m.group(0)}')

for m in re.finditer(r'@app\.route\([\'"]([^"\']*(?:operator|login)[^"\']*)[\'"]', text):
    line_no = text[:m.start()].count('\n') + 1
    print(f'Line {line_no}: {m.group(0)}')
