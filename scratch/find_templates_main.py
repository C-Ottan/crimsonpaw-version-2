import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
matches = re.findall(r"['\"](Adobe|DocuSign|Dropbox|OneDrive|QuickBooks|Outlook|SharePoint|Microsoft 365)['\"]", text)
print("Template name occurrences count:", len(matches))
print("Sample:", set(matches))

# Look for template definitions or lists in main.py
for line in text.splitlines():
    if any(k in line for k in ['DEFAULT_PRESETS', 'landingTemplates', 'template_list', 'templates =']):
        print(line[:120])
