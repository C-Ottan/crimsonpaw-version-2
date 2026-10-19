with open('sandbox_templates.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Let's find index where line starts with "    return f'''<!DOCTYPE html>" around line 466
target_start = -1
for i in range(450, 480):
    if "return f'''<!DOCTYPE html>" in lines[i]:
        target_start = i
        break

target_end = -1
for i in range(640, 680):
    if "status_tag = cfg.get" in lines[i]:
        target_end = i
        break

print('target_start:', target_start, repr(lines[target_start][:35]))
print('target_end:', target_end, repr(lines[target_end][:35]))

assert target_start != -1 and target_end != -1

lines[target_end] = "    status_tag = cfg.get('status_tag', 'New Voicemail · Encrypted Recording')\n"
new_lines = lines[:target_start] + lines[target_end:]

with open('sandbox_templates.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Success, cleaned voicemail in sandbox_templates.py')
