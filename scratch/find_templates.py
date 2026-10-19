import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('deployments.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
print("Matches in deployments.py:")
for m in re.finditer(r'def _dispatch_landing|TEMPLATES\s*=|PRESETS\s*=|SUPPORTED_TEMPLATES', text, re.IGNORECASE):
    idx = m.start()
    print(text[idx:idx+1500])
    print("="*40)
