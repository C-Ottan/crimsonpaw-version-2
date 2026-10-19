import sys, json
sys.stdout.reconfigure(encoding='utf-8')

steps_to_check = [71, 90, 512, 1199, 1211]
with open(r'C:\Users\IT-ADMIN\.gemini\antigravity-ide\brain\9c1c5fe9-439d-41a6-9fe9-389c0d6f9518\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get('step_index') in steps_to_check:
                print(f"=== STEP {data.get('step_index')} ({data.get('type')}) ===")
                content = str(data.get('content', ''))
                # find 3d in content
                idx = content.lower().find('3d')
                start = max(0, idx - 150)
                end = min(len(content), idx + 350)
                print(content[start:end])
        except Exception as e:
            pass
