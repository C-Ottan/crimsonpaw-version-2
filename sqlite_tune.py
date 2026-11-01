"""Global SQLite tuning for concurrent serving.

The app opens ~90 short-lived connections and never set WAL or a busy timeout,
which is fine for the single-threaded Flask dev server but breaks the moment a
real WSGI server serves requests on multiple threads: concurrent writers get an
immediate `database is locked` instead of waiting.

Importing this module patches sqlite3.connect once so every call site (db.py,
deployments.py, core/*) inherits:
  * a busy timeout, so writers queue instead of erroring
  * WAL journaling, so readers never block the writer (persistent, set once)
  * NORMAL sync, safe under WAL and much cheaper than FULL
"""
import sqlite3

_orig_connect = sqlite3.connect
_applied = set()


def _tuned_connect(*args, **kwargs):
    kwargs.setdefault('timeout', 30.0)
    conn = _orig_connect(*args, **kwargs)
    try:
        conn.execute('PRAGMA busy_timeout = 30000')
        db_path = args[0] if args else kwargs.get('database')
        if isinstance(db_path, str) and db_path not in _applied:
            # Journal mode is a persistent property of the file; set it once.
            conn.execute('PRAGMA journal_mode = WAL')
            conn.execute('PRAGMA synchronous = NORMAL')
            _applied.add(db_path)
    except sqlite3.Error:
        pass
    return conn


sqlite3.connect = _tuned_connect
