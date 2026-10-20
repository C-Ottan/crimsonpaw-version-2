#!/usr/bin/env python3
"""
CRIMSON PAW – Nightly Database Backup to Telegram
==================================================
Runs as a cron job (e.g. every day at 02:00 UTC).
  1. Reads the superadmin's Telegram bot_token + chat_id from the operators table.
  2. Creates a safe WAL-checkpoint copy of the SQLite database.
  3. Sends the .db file as a Telegram document with a status caption.
  4. Cleans up the temporary copy.

Usage (cron):
  0 2 * * * /usr/bin/python3 /opt/crimsonpaw/backup_to_telegram.py >> /var/log/crimsonpaw_backup.log 2>&1
"""

import os
import sys
import sqlite3
import shutil
import datetime
import requests
import tempfile

# ── Configuration ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.environ.get("ICEBADGER_DB_PATH", os.path.join(BASE_DIR, "icebadger.db"))

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def get_telegram_creds():
    """Retrieve bot_token and chat_id from settings.json (admin) or operators table (fallback)."""
    # 1. Try settings.json first (admin's Telegram credentials)
    settings_path = os.path.join(BASE_DIR, "settings.json")
    try:
        if os.path.exists(settings_path):
            import json
            with open(settings_path, 'r') as f:
                cfg = json.load(f)
            token = (cfg.get('tg_bot_token') or '').strip()
            chat  = (cfg.get('tg_chat_id') or '').strip()
            if token and chat:
                log("Using Telegram credentials from settings.json")
                return token, chat
    except Exception as e:
        log(f"WARNING: Could not read settings.json: {e}")

    # 2. Fallback: first operator with Telegram configured (any role)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT tg_bot_token, tg_chat_id FROM operators "
            "WHERE tg_bot_token IS NOT NULL AND tg_bot_token != '' "
            "AND tg_chat_id IS NOT NULL AND tg_chat_id != '' "
            "ORDER BY id ASC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            log("Using Telegram credentials from operators table")
            return row['tg_bot_token'], row['tg_chat_id']
    except Exception as e:
        log(f"ERROR reading Telegram creds from DB: {e}")

    return None, None

def safe_copy_db(src_path, dst_path):
    """
    Create a safe backup of a SQLite database using the backup API.
    This handles WAL mode correctly and avoids sending a partially-written file.
    """
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

def send_to_telegram(bot_token, chat_id, file_path, caption):
    """Send a file as a document to a Telegram chat."""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(file_path, 'rb') as f:
        resp = requests.post(
            url,
            data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
            files={'document': (os.path.basename(file_path), f)},
            timeout=120
        )
    return resp

def main():
    log("=== CRIMSON PAW DB Backup to Telegram ===")

    # 1. Validate DB exists
    if not os.path.exists(DB_PATH):
        log(f"FATAL: Database not found at {DB_PATH}")
        sys.exit(1)

    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    log(f"Database: {DB_PATH} ({db_size_mb:.2f} MB)")

    # 2. Get Telegram credentials from DB
    bot_token, chat_id = get_telegram_creds()
    if not bot_token or not chat_id:
        log("FATAL: No superadmin Telegram credentials configured. "
            "Set up Telegram bot in Settings → Telegram first.")
        sys.exit(1)
    log(f"Telegram chat_id: {chat_id}")

    # 3. Create safe backup copy in temp directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"crimsonpaw_backup_{timestamp}.db"
    tmp_dir = tempfile.mkdtemp(prefix="cpaw_bak_")
    backup_path = os.path.join(tmp_dir, backup_name)

    try:
        log("Creating safe database copy...")
        safe_copy_db(DB_PATH, backup_path)
        backup_size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        log(f"Backup created: {backup_path} ({backup_size_mb:.2f} MB)")

        # Telegram file limit is 50 MB for bots
        if backup_size_mb > 49:
            log(f"WARNING: Backup is {backup_size_mb:.1f} MB (Telegram limit is 50 MB). Attempting anyway...")

        # 4. Send to Telegram
        hostname = os.uname().nodename if hasattr(os, 'uname') else "VPS"
        caption = (
            f"🔴 <b>CRIMSON PAW – Daily Backup</b>\n"
            f"📅 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"🖥️ Host: <code>{hostname}</code>\n"
            f"💾 Size: <b>{backup_size_mb:.2f} MB</b>\n"
            f"📊 DB: <code>{os.path.basename(DB_PATH)}</code>"
        )

        log("Sending to Telegram...")
        resp = send_to_telegram(bot_token, chat_id, backup_path, caption)

        if resp.status_code == 200 and resp.json().get('ok'):
            log("✅ Backup sent successfully!")
        else:
            log(f"ERROR: Telegram API returned: {resp.status_code} - {resp.text}")
            sys.exit(1)

    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
    finally:
        # 5. Cleanup temp files
        try:
            shutil.rmtree(tmp_dir)
            log("Temp files cleaned up.")
        except Exception:
            pass

    log("=== Backup complete ===")

if __name__ == "__main__":
    main()
