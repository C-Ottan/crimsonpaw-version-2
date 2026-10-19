with open('sandbox_templates.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(300, 715):
    line = lines[i]
    if "'''" in line or '"""' in line:
        print(f"{i+1}: {line.strip()}")
