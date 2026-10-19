import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx = text.find('<aside class="sidebar">')
if idx == -1:
    idx = text.find('class="sidebar"')
if idx != -1:
    print(text[idx:idx+1500])
