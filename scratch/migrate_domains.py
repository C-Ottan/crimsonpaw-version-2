import sqlite3

conn = sqlite3.connect('icebadger.db')
c = conn.cursor()
cols = [r[1] for r in c.execute('PRAGMA table_info(owned_domains)').fetchall()]
print('Existing cols:', cols)
if 'status' not in cols:
    c.execute("ALTER TABLE owned_domains ADD COLUMN status TEXT DEFAULT 'active'")
    print('Added status col')
if 'deleted_at' not in cols:
    c.execute("ALTER TABLE owned_domains ADD COLUMN deleted_at TEXT DEFAULT NULL")
    print('Added deleted_at col')
conn.commit()
print('Updated cols:', [r[1] for r in c.execute('PRAGMA table_info(owned_domains)').fetchall()])
conn.close()
