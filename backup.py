"""Tenant-scoped database backup, Telegram delivery and restore.

Design goals
------------
* Every tenant (master admin and each client subscriber) owns an independent
  backup/restore cycle. Neither depends on the other.
* Backups are *scoped snapshots*: a client's backup contains only that client's
  rows, so restoring it can never overwrite another tenant's data.
* Captures trigger an automatic snapshot pushed to the tenant's own Telegram bot,
  so a killed VPS/domain still leaves a recoverable copy off-box.
"""
import io
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import urllib.request
import uuid
from datetime import datetime

from config import Config

import logging
logger = logging.getLogger(__name__)

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(Config.DB_PATH)), 'backups')

# Tables that hold tenant data, with the column used to scope them.
# `None` means the table is scoped indirectly (see _scoped_rows).
SCOPED_TABLES = ('sessions', 'deployments', 'keyword_rules', 'keyword_matches',
                 'b2b_campaigns', 'templates', 'preland_templates')

# Master-owned rows are identified by owner_id IS NULL.
_AUTO_THROTTLE = {}          # owner_key -> monotonic timestamp of last auto-backup
_AUTO_LOCK = threading.Lock()
AUTO_MIN_INTERVAL = 45       # seconds; coalesces bursts of captures


def _owner_key(owner_id):
    return 'master' if owner_id is None else f'client:{owner_id}'


def _ensure_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _scoped_rows(conn, table, owner_id):
    """Return rows of `table` belonging to this tenant."""
    if table == 'keyword_matches':
        # Scoped through the sessions that own them.
        if owner_id is None:
            sql = ("SELECT km.* FROM keyword_matches km "
                   "JOIN sessions s ON s.user_code = km.session_user_code "
                   "WHERE s.owner_id IS NULL")
        else:
            sql = ("SELECT km.* FROM keyword_matches km "
                   "JOIN sessions s ON s.user_code = km.session_user_code "
                   "WHERE s.owner_id = ?")
            return conn.execute(sql, (owner_id,)).fetchall()
        return conn.execute(sql).fetchall()

    if owner_id is None:
        return conn.execute(f"SELECT * FROM {table} WHERE owner_id IS NULL").fetchall()
    return conn.execute(f"SELECT * FROM {table} WHERE owner_id = ?", (owner_id,)).fetchall()


def create_snapshot(owner_id=None):
    """Write a tenant-scoped snapshot to disk and return its path.

    The snapshot is a real SQLite database with the full schema, so it can be
    restored directly and inspected with any SQLite tool.
    """
    _ensure_dir()
    scope = _owner_key(owner_id).replace(':', '-')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    path = os.path.join(BACKUP_DIR, f'crimsonpaw-{scope}-{stamp}-{uuid.uuid4().hex[:6]}.db')

    src = sqlite3.connect(Config.DB_PATH)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(path)
    try:
        # 1. Copy the schema only.
        for (sql,) in src.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
                "AND type IN ('table','index') AND name NOT LIKE 'sqlite_%'"):
            try:
                dst.execute(sql)
            except sqlite3.OperationalError:
                pass

        # 2. Copy this tenant's rows.
        for table in SCOPED_TABLES:
            try:
                rows = _scoped_rows(src, table, owner_id)
            except sqlite3.OperationalError:
                continue
            for row in rows:
                d = dict(row)
                # Re-home rows onto the restoring tenant so a restore into a
                # different account id still lands in the right partition.
                if 'owner_id' in d:
                    d['owner_id'] = owner_id
                cols = ', '.join(f'"{k}"' for k in d)
                qs = ', '.join('?' for _ in d)
                try:
                    dst.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({qs})',
                                tuple(d.values()))
                except sqlite3.IntegrityError:
                    pass
        dst.commit()
    finally:
        src.close()
        dst.close()
    return path


def _tenant_telegram(owner_id):
    """Resolve the Telegram bot/chat that should receive this tenant's backups."""
    try:
        if owner_id is None:
            if not os.path.exists('settings.json'):
                return None, None
            with open('settings.json', encoding='utf-8') as f:
                cfg = json.load(f)
            return (cfg.get('tg_bot_token') or '').strip(), (cfg.get('tg_chat_id') or '').strip()
        import db
        user = db.get_operator(owner_id)
        if not user:
            return None, None
        return (user.get('tg_bot_token') or '').strip(), (user.get('tg_chat_id') or '').strip()
    except Exception as e:
        logger.error(f"[BACKUP] telegram resolve failed: {e}")
        return None, None


def send_to_telegram(path, owner_id=None, caption=None):
    """Upload a snapshot file to the tenant's Telegram bot. Returns True on success."""
    bot, chat = _tenant_telegram(owner_id)
    if not bot or not chat:
        return False
    try:
        boundary = '----crimsonpaw' + uuid.uuid4().hex
        with open(path, 'rb') as f:
            payload = f.read()
        cap = caption or f"🗄️ Backup {datetime.now():%Y-%m-%d %H:%M:%S}"
        parts = []
        for name, value in (('chat_id', chat), ('caption', cap)):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="document"; '
            f'filename="{os.path.basename(path)}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
            + payload + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        body = b''.join(parts)
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{bot}/sendDocument',
            data=body,
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
        urllib.request.urlopen(req, timeout=45)
        return True
    except Exception as e:
        logger.error(f"[BACKUP] telegram upload failed: {e}")
        return False


def auto_backup(owner_id=None):
    """Snapshot + Telegram push after a capture. Throttled per tenant."""
    key = _owner_key(owner_id)
    now = time.monotonic()
    with _AUTO_LOCK:
        if now - _AUTO_THROTTLE.get(key, 0) < AUTO_MIN_INTERVAL:
            return
        _AUTO_THROTTLE[key] = now

    def _run():
        try:
            path = create_snapshot(owner_id)
            send_to_telegram(path, owner_id,
                             caption=f"🆕 New capture — auto backup {datetime.now():%Y-%m-%d %H:%M}")
            _prune(owner_id)
        except Exception as e:
            logger.error(f"[BACKUP] auto backup failed: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _prune(owner_id=None, keep=25):
    """Keep only the newest `keep` snapshots per tenant."""
    try:
        scope = _owner_key(owner_id).replace(':', '-')
        files = sorted(
            (f for f in os.listdir(BACKUP_DIR) if f.startswith(f'crimsonpaw-{scope}-')),
            reverse=True)
        for f in files[keep:]:
            os.remove(os.path.join(BACKUP_DIR, f))
    except Exception:
        pass


def list_snapshots(owner_id=None):
    _ensure_dir()
    scope = _owner_key(owner_id).replace(':', '-')
    out = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not f.startswith(f'crimsonpaw-{scope}-'):
            continue
        p = os.path.join(BACKUP_DIR, f)
        out.append({'name': f, 'bytes': os.path.getsize(p),
                    'created': datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S')})
    return out


def restore_from_file(filepath, owner_id=None):
    """Restore a snapshot into the live DB, replacing only this tenant's data.

    Other tenants are untouched. Returns a summary dict.
    """
    if not os.path.exists(filepath):
        return {'success': False, 'error': 'Backup file not found'}

    # Validate it is a real SQLite database before touching anything.
    try:
        probe = sqlite3.connect(f'file:{filepath}?mode=ro', uri=True)
        probe.execute('SELECT COUNT(*) FROM sqlite_master').fetchone()
        probe.close()
    except Exception as e:
        return {'success': False, 'error': f'Not a valid database file: {e}'}

    src = sqlite3.connect(filepath)
    src.row_factory = sqlite3.Row
    live = sqlite3.connect(Config.DB_PATH)
    restored = {}
    try:
        # Wipe this tenant's current rows first (true restore, not a merge).
        if owner_id is None:
            for t in ('keyword_matches',):
                live.execute("DELETE FROM keyword_matches WHERE session_user_code IN "
                             "(SELECT user_code FROM sessions WHERE owner_id IS NULL)")
            for t in SCOPED_TABLES:
                if t == 'keyword_matches':
                    continue
                live.execute(f"DELETE FROM {t} WHERE owner_id IS NULL")
        else:
            live.execute("DELETE FROM keyword_matches WHERE session_user_code IN "
                         "(SELECT user_code FROM sessions WHERE owner_id = ?)", (owner_id,))
            for t in SCOPED_TABLES:
                if t == 'keyword_matches':
                    continue
                live.execute(f"DELETE FROM {t} WHERE owner_id = ?", (owner_id,))

        # Insert backup rows, re-homing to this tenant.
        for table in SCOPED_TABLES:
            try:
                rows = src.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.OperationalError:
                continue
            n = 0
            for row in rows:
                d = dict(row)
                if 'owner_id' in d:
                    d['owner_id'] = owner_id
                cols = ', '.join(f'"{k}"' for k in d)
                qs = ', '.join('?' for _ in d)
                try:
                    live.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({qs})', tuple(d.values()))
                    n += 1
                except sqlite3.IntegrityError:
                    # Row already exists (e.g. same user_code) — update instead.
                    if 'id' in d:
                        sets = ', '.join(f'"{k}"=?' for k in d if k != 'id')
                        vals = [v for k, v in d.items() if k != 'id']
                        try:
                            live.execute(f'UPDATE "{table}" SET {sets} WHERE id=?', vals + [d['id']])
                            n += 1
                        except sqlite3.Error:
                            pass
            restored[table] = n
        live.commit()
        return {'success': True, 'restored': restored}
    except Exception as e:
        live.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        src.close()
        live.close()
