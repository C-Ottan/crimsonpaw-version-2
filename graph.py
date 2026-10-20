# ── graph.py ──────────────────────────────────────────────
import requests
import logging

logger = logging.getLogger(__name__)
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

def make_graph_request(endpoint, access_token, method='GET', payload=None, timeout=None):
    if not access_token:
        return {'error': {'message': 'No valid access token available for this session.'}}

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    url = f"{GRAPH_BASE_URL}{endpoint}"
    
    try:
        method = method.upper()
        # Use caller-provided timeout, or sensible defaults per method
        if timeout:
            req_timeout = timeout
        elif method in ('POST', 'PATCH'):
            req_timeout = (5, 15)   # sendMail / write operations need more headroom
        else:
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
            return {'success': True, 'status_code': response.status_code}
        return response.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 'N/A'
        body = e.response.text if e.response is not None else ''
        logger.error(f"Graph API HTTP Error for {endpoint} [{status}]: {body}")
        try:
            return e.response.json()
        except:
            return {'error': {'message': f'HTTP {status}: {body}'}}
    except requests.exceptions.RequestException as e:
        logger.error(f"Graph API request failed for {endpoint}: {e}")
        return {'error': {'message': str(e)}}

def send_mail_via_draft(access_token, message_obj, timeout=None):
    """
    Creates a draft message in the user's Drafts folder (simulating human Outlook Web interaction),
    then triggers the send action on that draft.
    Returns Graph API response dict (success or error).
    """
    if not access_token:
        return {'error': {'message': 'No valid access token available.'}}

    # Step 1: Create draft in user's mailbox
    draft_res = make_graph_request('/me/messages', access_token, method='POST', payload=message_obj, timeout=timeout or (5, 20))
    if not draft_res or draft_res.get('error'):
        return draft_res

    msg_id = draft_res.get('id')
    if not msg_id:
        return {'error': {'message': 'Draft was created but no message ID was returned by Graph API.'}}

    # Step 2: Send the draft
    send_res = make_graph_request(f'/me/messages/{msg_id}/send', access_token, method='POST', timeout=timeout or (5, 25))
    return send_res

def get_user_profile(access_token):
    return make_graph_request('/me?$select=displayName,mail,userPrincipalName,jobTitle,department,officeLocation,city,country,companyName', access_token)

def get_tenant_organization(access_token):
    return make_graph_request('/organization?$select=displayName,id', access_token)

def get_user_directory_roles(access_token):
    return make_graph_request('/me/memberOf?$select=displayName', access_token)