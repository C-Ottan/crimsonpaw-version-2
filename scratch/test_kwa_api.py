import urllib.request, json, http.cookiejar, time

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
login_data = json.dumps({'username': 'admin', 'password': 'admin'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:5000/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
res = opener.open(req)
print('Login status:', res.status)

# Stats
res = opener.open('http://127.0.0.1:5000/api/keyword_alerts/stats')
print('Stats:', json.loads(res.read().decode('utf-8')))

# Rules
res = opener.open('http://127.0.0.1:5000/api/keyword_alerts/rules')
data = json.loads(res.read().decode('utf-8'))
rules = data.get('rules', [])
print(f'Fetched {len(rules)} rules.')
for r in rules:
    print(f"  - [{r['severity']}] {r['name']}: {len(r['keywords'])} keywords")
