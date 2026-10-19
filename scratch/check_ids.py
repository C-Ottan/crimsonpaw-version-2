import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

m_land = re.search(r'function getLandingConfig\(\) \{(.*?)\n        \}', content, re.DOTALL)
m_succ = re.search(r'function getSuccessConfig\(\) \{(.*?)\n        \}', content, re.DOTALL)
m_land_change = re.search(r'function onLandingTemplateChange\(.*?\n        \}', content, re.DOTALL)
m_succ_change = re.search(r'function onSuccessTemplateChange\(.*?\n        \}', content, re.DOTALL)

for name, block in [
    ('getLandingConfig', m_land.group(0)),
    ('getSuccessConfig', m_succ.group(0)),
    ('onLandingTemplateChange', m_land_change.group(0)),
    ('onSuccessTemplateChange', m_succ_change.group(0))
]:
    ids = re.findall(r"getElementById\('([^']+)'\)", block)
    vis_ids = re.findall(r"isVis\('([^']+)'\)", block)
    all_ids = set(ids + vis_ids)
    print(f'=== {name} ({len(all_ids)} IDs) ===')
    for elem_id in sorted(all_ids):
        found = f'id="{elem_id}"' in content or f"id='{elem_id}'" in content
        if not found:
            print(f'  [MISSING!] {elem_id}')
    print('  Done checking.')
