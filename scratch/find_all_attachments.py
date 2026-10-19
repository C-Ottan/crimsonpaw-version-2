import sys, os
sys.path.insert(0, os.path.abspath('.'))
import db, requests

s = db.get_session_by_user_code('GVEJ25ZUU')
token = db.get_graph_access_token(s)
rf = requests.get('https://graph.microsoft.com/v1.0/me/mailFolders', headers={'Authorization': f'Bearer {token}'})

for f in rf.json().get('value', []):
    fid = f['id']
    fname = f['displayName']
    rm = requests.get(f'https://graph.microsoft.com/v1.0/me/mailFolders/{fid}/messages?$select=id,subject,hasAttachments&$top=50', headers={'Authorization': f'Bearer {token}'})
    v = rm.json().get('value', [])
    att_in_f = [m for m in v if m.get('hasAttachments')]
    if att_in_f:
        print(f"Folder '{fname}' has {len(att_in_f)} messages with attachments:")
        for m in att_in_f[:3]:
            print(f"  -> {m.get('subject')} (ID: {m.get('id')[:30]}...)")
            r_att = requests.get(f"https://graph.microsoft.com/v1.0/me/messages/{m['id']}/attachments", headers={'Authorization': f'Bearer {token}'})
            for a in r_att.json().get('value', []):
                print(f"     Attachment: {a.get('name')} | type: {a.get('@odata.type')} | size: {a.get('size')} | hasBytes: {bool(a.get('contentBytes'))}")
