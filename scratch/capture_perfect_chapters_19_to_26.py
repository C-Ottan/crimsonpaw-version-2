import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

BASE_URL = "http://127.0.0.1:5000"
ASSETS_DIR = r"c:\Users\IT-ADMIN\Desktop\FLOW\ICEBADGER\icebadger\audit_assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# 1. Authenticate admin session
s = requests.Session()
s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Sysadmin"})
otp = s.get(f"{BASE_URL}/api/auth/test-otp").json().get("otp")
if otp:
    s.post(f"{BASE_URL}/api/auth/verify-2fa", json={"code": otp})

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1050")
opts.add_argument("--disable-gpu")
opts.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=opts)
driver.set_window_size(1600, 1050)

def snap(filename, desc):
    path = os.path.join(ASSETS_DIR, filename)
    time.sleep(1.2)
    driver.save_screenshot(path)
    sz = os.path.getsize(path) / 1024
    print(f"[CAPTURED] {filename} ({sz:.1f} KB) - {desc}")

try:
    # Set cookies
    driver.get(f"{BASE_URL}/dashboard")
    for cookie in s.cookies:
        driver.add_cookie({"name": cookie.name, "value": cookie.value, "domain": "127.0.0.1"})
    driver.get(f"{BASE_URL}/dashboard")
    time.sleep(2)

    # ── 1. Chapter 19: Keyword Surveillance & Hit Ledger ──────
    driver.find_element(By.ID, "nav-keyword-alerts").click()
    time.sleep(2)
    snap("manual_24_keyword_alerts_ledger.png", "Chapter 19: Continuous Keyword Surveillance & Hit Ledger")

    # ── 2. Chapter 20: Keyword Surveillance Rule Creator Modal 
    driver.execute_script("openNewKeywordRuleModal();")
    time.sleep(1.5)
    snap("manual_25_keyword_new_rule_modal.png", "Chapter 20: Keyword Surveillance Rule Creator Modal")
    driver.execute_script("closeKeywordRuleModal();")
    time.sleep(0.5)

    # ── 3. Chapter 21: Extractor & Sorter Suite ───────────────
    driver.find_element(By.ID, "nav-extractor").click()
    time.sleep(1.5)
    driver.execute_script("""
        let ta = document.getElementById('ext-raw-input') || document.querySelector('#page-extractor textarea');
        if (ta) {
            ta.value = "admin@axiomtech.com:AdminMasterPass2026!\\njohn.doe@victim-finance.org:Winter2026!\\nhttps://login.microsoftonline.com/common/oauth2/v2.0/token\\nsarah.connor@cyberdyne.org:Skynet#991\\neyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.dummy_access_token_payload\\nadmin@axiomtech.com:AdminMasterPass2026!\\naccounting@acme-corp.com:InvoicePay2026!\\nhttps://teams.microsoft.com/l/meetup-join/19%3ameeting";
            ta.dispatchEvent(new Event('input'));
        }
        if (typeof runExtractor === 'function') runExtractor('emails');
        else if (typeof extractEmails === 'function') extractEmails();
    """)
    time.sleep(1.5)
    snap("manual_26_extractor_sorter_suite.png", "Chapter 21: Extractor & Sorter Suite with Loaded Data")

    # ── 4. Chapter 22: B2B Targeted Spear-Phishing Campaign Builder
    driver.find_element(By.ID, "nav-b2b").click()
    time.sleep(1.5)
    driver.execute_script("""
        let cName = document.getElementById('b2b-campaign-name');
        if (cName) { cName.value = "Q4 Executive Security Review - Internal Phish"; cName.dispatchEvent(new Event('input')); }
        let cSub = document.getElementById('b2b-subject');
        if (cSub) { cSub.value = "Urgent: Microsoft Teams Executive Briefing Access Required"; cSub.dispatchEvent(new Event('input')); }
        let cRec = document.getElementById('b2b-recipients');
        if (cRec) { cRec.value = "david.vance@targetcorp.com, David Vance, VP Operations\\nellen.ripley@targetcorp.com, Ellen Ripley, Dir Security\\nmarcus.vanceley@axiomtech.com, Marcus Vanceley, CTO"; cRec.dispatchEvent(new Event('input')); }
        let cBody = document.getElementById('b2b-body');
        if (cBody) { cBody.value = "Hello {NAME},\\n\\nPlease join the mandatory executive session for {COMPANY} using the link below:\\n{UNIQUE_LINK}\\n\\nRegards,\\nCorporate IT"; cBody.dispatchEvent(new Event('input')); }
        if (typeof updateB2BLivePreview === 'function') updateB2BLivePreview();
    """)
    time.sleep(1.5)
    snap("manual_27_b2b_campaign_sender.png", "Chapter 22: B2B Targeted Campaign Builder")

    # ── 5. Chapter 23: Live Sessions Vault ─────────────────────
    driver.find_element(By.ID, "nav-sessions").click()
    time.sleep(2)
    snap("manual_28_live_sessions_vault.png", "Chapter 23: Captured Victim Sessions & PRT Vault")

    # ── 6. Chapter 24: Role-Based Access Control & Operators Ledger
    driver.find_element(By.ID, "nav-operators").click()
    time.sleep(2)
    snap("manual_29_operators_rbac_ledger.png", "Chapter 24: Operators Ledger with Staged Accounts & Actions")

    # ── 7. Chapter 25: Operator Provisioning Modal ────────────
    driver.execute_script("openNewOperatorModal();")
    time.sleep(1.5)
    snap("manual_30_add_operator_modal.png", "Chapter 25: Operator Provisioning & Delegated Inboxes Modal")
    driver.execute_script("let m = document.getElementById('operatorModal'); if (m) m.classList.remove('active');")
    time.sleep(0.5)

    # ── 8. Chapter 25b: Operator Info Copy Confirmation ───────
    driver.execute_script("""
        let opData = {
            username: 'op_alpha',
            operator_token: 'a1b2c3d4e5f6',
            assigned_sessions: ['DVWRHR76J']
        };
        if (typeof copyOperatorAccountInfoRow === 'function') {
            copyOperatorAccountInfoRow(opData);
        } else if (typeof showToast === 'function') {
            showToast('✓ Operator account info copied to clipboard!');
        }
    """)
    time.sleep(1.2)
    snap("manual_30b_operator_info_copy.png", "Chapter 25: Operator Account Info Copy Confirmation")

    # ── 9. Chapter 25c: Operator Portal Gateway (/m/<token>) ──
    driver.get(f"{BASE_URL}/m/a1b2c3d4e5f6")
    time.sleep(1.5)
    snap("manual_30c_operator_portal_gateway.png", "Chapter 25: Operator Portal Authentication Gateway")

    # ── 10. Chapter 26: Enterprise Platform Settings ───────────
    driver.get(f"{BASE_URL}/dashboard")
    time.sleep(1)
    driver.find_element(By.ID, "nav-settings").click()
    time.sleep(2)
    snap("manual_31_platform_settings.png", "Chapter 26: Enterprise Platform Settings & Azure Entra ID")

finally:
    driver.quit()

print("\n=== ALL CHAPTERS 19-26 SCREENSHOTS HARVESTED SUCCESSFULLY ===")
