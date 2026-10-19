# ── oauth.py ─────────────────────────────────────────────
import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

def request_device_code():
    payload = {'client_id': Config.CLIENT_ID, 'scope': Config.SCOPE}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(Config.DEVICE_CODE_URL, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('user_code'), data.get('device_code'), data.get('verification_uri') or data.get('verification_url'), data.get('expires_in')
    except Exception as e:
        logger.error(f"Failed to request device code: {e}")
        return None, None, None, None

def poll_token(device_code):
    payload = {'client_id': Config.CLIENT_ID, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'device_code': device_code}
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