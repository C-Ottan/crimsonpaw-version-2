import base64

teams_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="teamsGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#5B5FC7"/>
      <stop offset="100%" stop-color="#464EB8"/>
    </linearGradient>
    <linearGradient id="teamsLight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#9299F7"/>
      <stop offset="100%" stop-color="#7B83EB"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#teamsGrad)"/>
  <circle cx="45" cy="22" r="6" fill="url(#teamsLight)"/>
  <path d="M37 32 C37 28.5 40 26 45 26 C50 26 53 28.5 53 32 L53 40 L37 40 Z" fill="url(#teamsLight)"/>
  <rect x="10" y="16" width="30" height="32" rx="6" fill="#333A8C" opacity="0.5"/>
  <rect x="8" y="14" width="30" height="32" rx="6" fill="#505AC9" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
  <path d="M17 22 L29 22 L29 26 L25 26 L25 38 L21 38 L21 26 L17 26 Z" fill="#FFFFFF"/>
</svg>'''

voicemail_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="vmGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0078D4"/>
      <stop offset="100%" stop-color="#004E8C"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#vmGrad)"/>
  <circle cx="22" cy="34" r="9" fill="none" stroke="#FFFFFF" stroke-width="3.5"/>
  <circle cx="42" cy="34" r="9" fill="none" stroke="#FFFFFF" stroke-width="3.5"/>
  <line x1="22" y1="43" x2="42" y2="43" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="22" cy="34" r="3.5" fill="#50E6FF"/>
  <circle cx="42" cy="34" r="3.5" fill="#50E6FF"/>
  <rect x="16" y="14" width="3.5" height="7" rx="1.5" fill="#50E6FF"/>
  <rect x="23" y="10" width="3.5" height="11" rx="1.5" fill="#FFFFFF"/>
  <rect x="30.25" y="7" width="3.5" height="14" rx="1.5" fill="#50E6FF"/>
  <rect x="37.5" y="10" width="3.5" height="11" rx="1.5" fill="#FFFFFF"/>
  <rect x="44.5" y="14" width="3.5" height="7" rx="1.5" fill="#50E6FF"/>
</svg>'''

teams_b64 = 'data:image/svg+xml;base64,' + base64.b64encode(teams_svg.encode('utf-8')).decode('utf-8')
vm_b64 = 'data:image/svg+xml;base64,' + base64.b64encode(voicemail_svg.encode('utf-8')).decode('utf-8')

with open('assets.py', 'r', encoding='utf-8') as f:
    content = f.read()

entries = f"""    'Teams': '{teams_b64}',
    'Microsoft Teams': '{teams_b64}',
    'Teams Meeting': '{teams_b64}',
    'Voicemail': '{vm_b64}',
    'Cloud Voicemail': '{vm_b64}',
    'Microsoft 365 Voicemail': '{vm_b64}',"""

marker = "'Crimson Paw':"
idx = content.find(marker)
end_of_line = content.find('\n', idx) + 1

if "'Teams':" not in content:
    new_content = content[:end_of_line] + entries + '\n' + content[end_of_line:]
    with open('assets.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully added Teams and Voicemail to assets.py!")
else:
    print("Teams and Voicemail already in assets.py")
