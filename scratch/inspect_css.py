with open('deployments.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx = text.find('return f"""<style>')
if idx != -1:
    print(text[idx:idx+3500])
