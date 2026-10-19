import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('deployments.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx1 = text.find('def _mode_s_card')
idx2 = text.find('def _left_panel_html')
if idx1 != -1 and idx2 != -1:
    print(text[idx1:idx2])
