import re

with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

matches = re.findall(r'@app\.route\([\'"]([^\'"]+)[\'"]', text)
sandbox_routes = [r for r in matches if 'sandbox' in r.lower()]
print('Total app routes:', len(matches))
print('Sandbox routes:', sandbox_routes)
