with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    for i, line in enumerate(f):
        if 'id="page-' in line:
            print(f"{i+1}: {line.strip()[:75]}")
