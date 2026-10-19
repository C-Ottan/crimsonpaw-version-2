with open('deployments.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx = text.find('def _left_panel_html')
if idx != -1:
    print(text[idx:idx+2500])
