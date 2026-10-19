with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'function setPreviewTab' in line:
        print(f"setPreviewTab at line {i+1}:")
        for j in range(i, min(len(lines), i+30)):
            print(f"{j+1}: {lines[j].strip()}")
        break
