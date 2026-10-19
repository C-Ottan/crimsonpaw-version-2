import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import db, graph

s = db.get_session_by_user_code('D63QP7TSH')
token = db.get_graph_access_token(s)

inbox = graph.make_graph_request('/me/mailFolders/inbox/messages?$top=20', token)
print(f"Marcus Vanceley Inbox messages found: {len(inbox.get('value', []))}")
for m in inbox.get('value', []):
    print(f" - Subject: '{m.get('subject')}' | ID: {m.get('id')[:40]}...")

deleted = graph.make_graph_request('/me/mailFolders/deleteditems/messages?$top=10', token)
print(f"Marcus Vanceley Deleted Items found: {len(deleted.get('value', []))}")
for m in deleted.get('value', []):
    print(f" - Deleted Subject: '{m.get('subject')}' | ID: {m.get('id')[:40]}...")
