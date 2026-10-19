import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx = text.find('btn-prev-landing')
if idx != -1:
    print(text[idx-200:idx+800])
