import urllib.request, json, urllib.error, http.cookiejar

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

# 1. Login as admin
login_data = json.dumps({'username': 'admin', 'password': 'password123'}).encode('utf-8')
# Let's check settings.json for actual admin credentials
with open('settings.json', 'r') as f:
    cfg = json.load(f)
u = cfg.get('admin_username', 'admin')
p = cfg.get('admin_password', 'password123')

req = urllib.request.Request('http://127.0.0.1:5000/api/auth/login', data=json.dumps({'username': u, 'password': p}).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    res = opener.open(req)
    print("Login response:", res.read().decode())
except Exception as e:
    print("Login error:", e)

accounts = ['DVWRHR76J', 'D63QP7TSH', 'DRBQKN6ES', 'G5USGUFQ6']

for uc in accounts:
    print(f"\n==================== TESTING USER CODE: {uc} ====================")
    # 1. Folders
    url_folders = f"http://127.0.0.1:5000/api/graph_proxy/folders?user_code={uc}"
    try:
        req = urllib.request.Request(url_folders)
        with opener.open(req, timeout=15) as res:
            data = json.loads(res.read().decode())
            folders = data.get('value', [])
            print(f"[FOLDERS] Success! Found {len(folders)} folders.")
            for f in folders[:3]:
                print(f"   - {f.get('displayName')} (unread: {f.get('unreadItemCount')}, total: {f.get('totalItemCount')}) [ID: {f.get('id')[:20]}...]")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[FOLDERS] HTTP Error {e.code}: {err}")
    except Exception as e:
        print(f"[FOLDERS] Exception: {e}")

    # 2. Messages
    url_messages = f"http://127.0.0.1:5000/api/graph_proxy/messages?user_code={uc}"
    try:
        req = urllib.request.Request(url_messages)
        with opener.open(req, timeout=15) as res:
            data = json.loads(res.read().decode())
            msgs = data.get('value', [])
            print(f"[MESSAGES] Success! Found {len(msgs)} messages.")
            for m in msgs[:3]:
                print(f"   - Subject: '{m.get('subject')}' | From: {m.get('from',{}).get('emailAddress',{}).get('address')} | Date: {m.get('receivedDateTime')}")
            if msgs:
                # Test reading the first message!
                first_mid = msgs[0].get('id')
                url_msg = f"http://127.0.0.1:5000/api/graph_proxy/message?user_code={uc}&message_id={first_mid}"
                try:
                    req_msg = urllib.request.Request(url_msg)
                    with opener.open(req_msg, timeout=15) as res_msg:
                        msg_data = json.loads(res_msg.read().decode())
                        print(f"   [FIRST MESSAGE DETAIL] Success! Body length: {len(msg_data.get('body',{}).get('content',''))} chars")
                except urllib.error.HTTPError as e_m:
                    print(f"   [FIRST MESSAGE DETAIL] HTTP Error {e_m.code}: {e_m.read().decode()}")
                except Exception as e_m:
                    print(f"   [FIRST MESSAGE DETAIL] Exception: {e_m}")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[MESSAGES] HTTP Error {e.code}: {err}")
    except Exception as e:
        print(f"[MESSAGES] Exception: {e}")
