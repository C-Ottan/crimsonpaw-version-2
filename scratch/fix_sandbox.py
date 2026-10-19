with open('sandbox_templates.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print('0-indexed line 150:', lines[150][:40])
print('0-indexed line 348:', lines[348][:40])
print('0-indexed line 349:', lines[349][:40])

assert 'return' in lines[150]
assert 'credentials' in lines[348]

lines[349] = "    status_tag = cfg.get('status_tag', 'Lobby Open · Admission Required')\n"
new_lines = lines[:150] + lines[349:]

with open('sandbox_templates.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Success, cleaned sandbox_templates.py')
