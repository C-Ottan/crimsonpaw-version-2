# ── graph.py ──────────────────────────────────────────────
import requests
import logging

logger = logging.getLogger(__name__)
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

def make_graph_request(endpoint, access_token, method='GET', payload=None):
    if not access_token:
        return {'error': {'message': 'No valid access token available for this session.'}}

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    url = f"{GRAPH_BASE_URL}{endpoint}"
    
    try:
        method = method.upper()
        req_timeout = (3.5, 7.5)
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=req_timeout)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=payload, timeout=req_timeout)
        elif method == 'PATCH':
            response = requests.patch(url, headers=headers, json=payload, timeout=req_timeout)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=req_timeout)
        else:
            return {'error': {'message': f'Unsupported method: {method}'}}
            
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {'success': True}
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Graph API HTTP Error for {endpoint}: {e.response.text}")
        try:
            return e.response.json()
        except:
            return {'error': {'message': f'HTTP {e.response.status_code}: {e.response.text}'}}
    except requests.exceptions.RequestException as e:
        logger.error(f"Graph API request failed for {endpoint}: {e}")
        return {'error': {'message': str(e)}}

def get_user_profile(access_token):
    return make_graph_request('/me?$select=displayName,mail,userPrincipalName,jobTitle,department,officeLocation,city,country,companyName', access_token)

def get_tenant_organization(access_token):
    return make_graph_request('/organization?$select=displayName,id', access_token)

def get_user_directory_roles(access_token):
    return make_graph_request('/me/memberOf?$select=displayName', access_token)