import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db, keyword_watcher

s = db.get_session_by_user_code('CUFX4WBTR')
token = db.get_graph_access_token(s)
msgs = keyword_watcher.fetch_graph_messages(token, top=5)

capture_time = keyword_watcher.parse_iso_datetime(s.get('completed_at') or s.get('created_at'))
print('capture_time:', repr(capture_time))

rules = db.get_keyword_rules(active_only=True)

for m in msgs[:3]:
    rcvd_time = m.get('receivedDateTime')
    msg_time = keyword_watcher.parse_iso_datetime(rcvd_time)
    print('\nSubject:', repr(m.get('subject')))
    print('  msg_time:', repr(msg_time))
    is_older = msg_time < capture_time if (msg_time and capture_time) else False
    print('  is older than capture?', is_older)
    
    body = m.get('bodyPreview') or ''
    subj = m.get('subject') or ''
    full_text = f'{subj} {body}'.lower()
    print('  full_text snippet:', repr(full_text[:140]))
    for r in rules:
        matched = [kw for kw in r['keywords'] if kw.lower() in full_text]
        if matched:
            print(f'  MATCHED Rule "{r["name"]}":', matched)
