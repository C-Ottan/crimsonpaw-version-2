import sys, json
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\IT-ADMIN\.gemini\antigravity-ide\brain\9c1c5fe9-439d-41a6-9fe9-389c0d6f9518\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        try:
            data = json.loads(line)
            content = str(data.get('content', ''))
            if '3d' in content.lower() and ('template' in content.lower() or 'card' in content.lower() or 'design' in content.lower()):
                print(f"Step {data.get('step_index')}: {content[:200]}...")
        except Exception as e:
            pass
