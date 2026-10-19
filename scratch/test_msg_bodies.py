import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import db, graph, json

for uc in ['DVWRHR76J', 'D63QP7TSH', 'G5USGUFQ6']:
    s = db.get_session_by_user_code(uc)
    token = db.get_graph_access_token(s)
    msgs = graph.make_graph_request('/me/messages?$top=1', token)
    if 'value' in msgs and msgs['value']:
        mid = msgs['value'][0]['id']
        subj = msgs['value'][0]['subject']
        m_full = graph.make_graph_request(f'/me/messages/{mid}', token)
        body_ok = 'body' in m_full
        body_len = len(m_full.get('body', {}).get('content', ''))
        print(f"[{uc}] Subject: '{subj}' | Full body read: {body_ok} | Body length: {body_len} chars")
    else:
        print(f"[{uc}] No messages or error: {msgs}")
