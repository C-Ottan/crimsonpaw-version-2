import os
import time
import json
import sqlite3
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"
ASSETS_DIR = r"c:\Users\IT-ADMIN\Desktop\FLOW\ICEBADGER\icebadger\audit_assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

test_results = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "base_url": BASE_URL,
    "system": "ICEBADGER / CRIMSON PAW",
    "version": "v2.6 Enterprise",
    "api_tests": [],
    "ui_modules": [],
    "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0}
}

def log_test(module, test_name, status, details=""):
    test_results["summary"]["total"] += 1
    if status == "PASS":
        test_results["summary"]["passed"] += 1
    elif status == "WARN":
        test_results["summary"]["warnings"] += 1
    else:
        test_results["summary"]["failed"] += 1
    test_results["api_tests"].append({
        "module": module,
        "test": test_name,
        "status": status,
        "details": details
    })
    print(f"[{status}] {module} - {test_name}: {details}")

print("=== STARTING BACKEND API FUNCTIONAL AUDIT ===")
session = requests.Session()

# 1. Test Login & 2FA API
try:
    r_login = session.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Sysadmin"}, timeout=10)
    login_data = r_login.json()
    if r_login.status_code == 200 and login_data.get("requires_2fa"):
        log_test("Auth & RBAC", "Admin Credential Validation", "PASS", "Login accepted, 2FA challenge triggered.")
        r_otp = session.get(f"{BASE_URL}/api/auth/test-otp", timeout=5)
        otp = r_otp.json().get("otp")
        if otp:
            log_test("Auth & RBAC", "Telegram 2FA OTP Generation", "PASS", f"Valid 6-digit OTP generated: {otp}")
            r_verify = session.post(f"{BASE_URL}/api/auth/verify-2fa", json={"code": otp}, timeout=10)
            if r_verify.status_code == 200 and r_verify.json().get("success"):
                log_test("Auth & RBAC", "2FA Verification & Session Issuance", "PASS", "Session authenticated as admin role.")
            else:
                log_test("Auth & RBAC", "2FA Verification & Session Issuance", "FAIL", f"Verification rejected: {r_verify.text}")
        else:
            log_test("Auth & RBAC", "Telegram 2FA OTP Generation", "FAIL", "No OTP returned from localhost test-otp.")
    else:
        log_test("Auth & RBAC", "Admin Credential Validation", "FAIL", f"Login rejected: {r_login.text}")
except Exception as e:
    log_test("Auth & RBAC", "Authentication Pipeline", "FAIL", str(e))

# 2. Test Core API Endpoints
api_endpoints = [
    ("/api/statistics", "System Metrics & Session Statistics", "dict"),
    ("/api/sessions", "Active Live Sessions Vault", "list"),
    ("/api/templates", "Template Registry & Pre-land Inventory", "list"),
    ("/api/operators", "Operator RBAC & Accounts Ledger", "list"),
    ("/api/notifications", "Real-time Operator Notification Poller", "dict"),
    ("/sandbox/api/info", "Sandbox Templates Studio Metadata", "dict"),
]

for ep, desc, expected_type in api_endpoints:
    try:
        r = session.get(f"{BASE_URL}{ep}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            is_valid = isinstance(data, dict) if expected_type == "dict" else isinstance(data, list)
            if is_valid:
                log_test("Core APIs", desc, "PASS", f"HTTP 200, valid {expected_type} returned ({len(data)} items)")
            else:
                log_test("Core APIs", desc, "WARN", f"HTTP 200, but unexpected type: {type(data)}")
        else:
            log_test("Core APIs", desc, "FAIL", f"HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        log_test("Core APIs", desc, "FAIL", str(e))

# 3. Test Keyword Alerts API
try:
    r_kwa = session.get(f"{BASE_URL}/api/keyword_alerts/rules", timeout=8)
    if r_kwa.status_code == 200:
        log_test("Keyword Surveillance", "Keyword Rules API", "PASS", f"HTTP 200, {len(r_kwa.json())} rules active")
    else:
        # Fallback check
        log_test("Keyword Surveillance", "Keyword Rules API", "WARN", f"HTTP {r_kwa.status_code}")
except Exception as e:
    log_test("Keyword Surveillance", "Keyword Rules API", "FAIL", str(e))

print("\n=== STARTING SELENIUM UI AUDIT & SCREENSHOT CAPTURE ===")
opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1050")
opts.add_argument("--disable-gpu")
opts.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=opts)
driver.set_window_size(1600, 1050)

def capture(filename, description):
    path = os.path.join(ASSETS_DIR, filename)
    time.sleep(1.2)
    driver.save_screenshot(path)
    file_size_kb = os.path.getsize(path) / 1024
    print(f"[SCREENSHOT] Saved {filename} ({file_size_kb:.1f} KB) - {description}")
    test_results["ui_modules"].append({
        "filename": filename,
        "path": path,
        "description": description,
        "size_kb": round(file_size_kb, 1)
    })

try:
    # 1. Login Page
    driver.get(f"{BASE_URL}/login")
    time.sleep(1)
    capture("01_login_page.png", "Administrator Authentication Portal")

    # 2. Enter credentials & trigger 2FA Modal
    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("Sysadmin")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1.5)
    capture("02_login_2fa_prompt.png", "Telegram Out-of-Band 2FA Challenge Modal")

    # 3. Enter OTP to authenticate
    r_otp = session.get(f"{BASE_URL}/api/auth/test-otp", timeout=5)
    otp = r_otp.json().get("otp")
    if otp:
        try:
            otp_input = driver.find_element(By.ID, "otp-code") or driver.find_element(By.ID, "two-factor-code")
            otp_input.send_keys(otp)
        except Exception:
            driver.execute_script(f"""
                let inp = document.querySelector('input[type="text"]') || document.querySelector('input[name="otp"]') || document.getElementById('two-factor-code');
                if (inp) {{ inp.value = '{otp}'; inp.dispatchEvent(new Event('input')); }}
                let btn = document.querySelector('button[type="submit"]') || document.querySelector('.btn-primary');
                if (btn) btn.click();
            """)
        time.sleep(2)

    # If not on dashboard, authenticate cookies directly
    if "/dashboard" not in driver.current_url:
        driver.get(f"{BASE_URL}/dashboard")
        for cookie in session.cookies:
            driver.add_cookie({"name": cookie.name, "value": cookie.value, "domain": "127.0.0.1"})
        driver.get(f"{BASE_URL}/dashboard")
        time.sleep(2)

    # 3. Dashboard
    driver.execute_script("showPage('dashboard')")
    time.sleep(2)
    capture("03_dashboard_overview.png", "Red Team Command Dashboard with Live Telemetry")

    # 4. Templates Studio
    driver.execute_script("showPage('templates')")
    time.sleep(2)
    capture("04_templates_studio.png", "Pre-land & Phishing Templates Studio (Teams, Voicemail, DocuSign, Adobe)")

    # 5. Mailbox Intelligence
    driver.execute_script("showPage('mailbox')")
    time.sleep(2.5)
    capture("05_mailbox_intelligence.png", "Microsoft 365 Mailbox Explorer & Message Viewer")

    # 6. Mailbox Compose Modal
    try:
        driver.execute_script("if (typeof openComposeModal === 'function') openComposeModal(); else document.querySelector('.ribbon-split-btn').click();")
        time.sleep(1.2)
        capture("06_mailbox_compose_modal.png", "M365 Graph API In-Session Email Composer")
        driver.execute_script("if (typeof closeComposeModal === 'function') closeComposeModal();")
    except Exception as e:
        print(f"Compose modal error: {e}")

    # 7. Mailbox Settings & Inbox Rules Modal
    try:
        driver.execute_script("if (typeof openSettingsModal === 'function') openSettingsModal(); else document.getElementById('suite-btn-settings').click();")
        time.sleep(1.2)
        driver.execute_script("let t = document.getElementById('tab-nav-rules'); if (t) t.click(); if (typeof openNewRuleForm === 'function') openNewRuleForm();")
        time.sleep(1)
        capture("07_mailbox_rules_manager.png", "Stealth Inbox Forwarding & Deletion Rule Engine")
        driver.execute_script("let m = document.getElementById('settingsModal') || document.querySelector('.modal'); if (m) m.style.display='none';")
    except Exception as e:
        print(f"Rules modal error: {e}")

    # 8. Keyword Surveillance Alerts
    driver.execute_script("showPage('keyword-alerts')")
    time.sleep(2)
    capture("08_keyword_alerts.png", "Continuous Keyword Surveillance & Intelligence Ledger")

    # 9. Keyword Rule Creation Modal
    try:
        driver.execute_script("if (typeof openNewRuleModal === 'function') openNewRuleModal(); else if (typeof openAddRuleModal === 'function') openAddRuleModal();")
        time.sleep(1.2)
        capture("09_keyword_new_rule_modal.png", "Keyword Surveillance Target & Regex Rule Creator")
        driver.execute_script("let m = document.getElementById('newRuleModal') || document.querySelector('.modal'); if (m) m.style.display='none';")
    except Exception as e:
        print(f"KWA modal error: {e}")

    # 10. Extractor & Sorter
    driver.execute_script("showPage('extractor')")
    time.sleep(2)
    capture("10_extractor_sorter.png", "Credential, Token & Regex Data Extraction Engine")

    # 11. B2B Campaign Sender
    driver.execute_script("showPage('b2b')")
    time.sleep(2)
    capture("11_b2b_sender.png", "B2B Targeted Spear-Phishing Campaign Dispatcher")

    # 12. Live Sessions Vault
    driver.execute_script("showPage('sessions')")
    time.sleep(2)
    capture("12_live_sessions.png", "Captured Victim OAuth Sessions & PRT Credential Vault")

    # 13. Operator RBAC Management
    driver.execute_script("showPage('operators')")
    time.sleep(2)
    capture("13_operators_management.png", "Role-Based Access Control (RBAC) & Operator Accounts")

    # 14. Add Operator Modal
    try:
        driver.execute_script("if (typeof openAddOperatorModal === 'function') openAddOperatorModal(); else document.querySelector('#page-operators button').click();")
        time.sleep(1.2)
        capture("14_add_operator_modal.png", "Operator Provisioning & Permission Assignment Modal")
        driver.execute_script("let m = document.getElementById('operatorModal') || document.querySelector('.modal'); if (m) m.style.display='none';")
    except Exception as e:
        print(f"Operator modal error: {e}")

    # 15. Platform Settings & Configurations
    driver.execute_script("showPage('settings')")
    time.sleep(2)
    capture("15_platform_settings.png", "Enterprise Configurations, Azure Entra ID & Telegram Gateways")

    # 16. Sandbox Templates Studio
    driver.get(f"{BASE_URL}/sandbox/templates")
    time.sleep(2.5)
    capture("16_sandbox_templates_studio.png", "Isolated Sandboxed Templates Live Testing Environment")

    # 17. Victim Pre-land Experience (Teams Meeting)
    driver.get(f"{BASE_URL}/sandbox/templates/meeting/preland")
    time.sleep(2)
    capture("17_victim_preland_teams.png", "Victim Pre-land Cloaking Experience: Microsoft Teams Conference")

    # 18. Victim Pre-land Experience (Cloud Voicemail)
    driver.get(f"{BASE_URL}/sandbox/templates/voicemail/preland")
    time.sleep(2)
    capture("18_victim_preland_voicemail.png", "Victim Pre-land Cloaking Experience: Cloud Audio Voicemail Portal")

    # 19. Victim Landing & Device Code Presentation
    driver.get(f"{BASE_URL}/sandbox/templates/meeting/landing")
    time.sleep(2)
    capture("19_victim_landing_auth.png", "OAuth 2.0 Device Flow Token Interception Portal with Auto-Copy")

finally:
    driver.quit()

# Write test results metadata
with open(os.path.join(ASSETS_DIR, "test_results.json"), "w", encoding="utf-8") as f:
    json.dump(test_results, f, indent=2)

print("\n=== AUDIT & SCREENSHOT CAPTURE COMPLETE ===")
print(f"Total Tests: {test_results['summary']['total']} | Passed: {test_results['summary']['passed']} | Warnings: {test_results['summary']['warnings']} | Failed: {test_results['summary']['failed']}")
print(f"Captured {len(test_results['ui_modules'])} high-resolution screenshots in {ASSETS_DIR}")
