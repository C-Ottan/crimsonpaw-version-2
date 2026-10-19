import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

BASE_URL = "http://127.0.0.1:5000"
ASSETS_DIR = r"c:\Users\IT-ADMIN\Desktop\FLOW\ICEBADGER\icebadger\audit_assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# 1. Log in via requests to get valid session cookies
s = requests.Session()
r_login = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Sysadmin"})
r_otp = s.get(f"{BASE_URL}/api/auth/test-otp")
otp = r_otp.json().get("otp")
if otp:
    s.post(f"{BASE_URL}/api/auth/verify-2fa", json={"code": otp})

# 2. Setup Selenium
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
    print(f"[HARVESTED] {filename} ({sz:.1f} KB) - {desc}")

try:
    # ── 1. Public Landing Page ─────────────────────────────────
    driver.get(f"{BASE_URL}/landing")
    time.sleep(1.5)
    snap("manual_01_public_landing.png", "Public Landing Page")

    # ── 2. Sign-In Page ───────────────────────────────────────
    driver.get(f"{BASE_URL}/login")
    time.sleep(1.2)
    snap("manual_02_sign_in_page.png", "Sign-in / Login Page")

    # ── 3. 2FA Modal ──────────────────────────────────────────
    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("Sysadmin")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1.5)
    snap("manual_03_sign_in_2fa_modal.png", "Telegram 2FA Verification Challenge Modal")

    # Inject authenticated session cookies into browser
    driver.get(f"{BASE_URL}/dashboard")
    for cookie in s.cookies:
        driver.add_cookie({"name": cookie.name, "value": cookie.value, "domain": "127.0.0.1"})
    driver.get(f"{BASE_URL}/dashboard")
    time.sleep(2)

    # ── 4. Command Dashboard ──────────────────────────────────
    driver.execute_script("showPage('dashboard')")
    time.sleep(2)
    snap("manual_04_command_dashboard.png", "Command Dashboard Overview")

    # ── 5. Templates Studio ───────────────────────────────────
    driver.execute_script("showPage('templates')")
    time.sleep(2)
    snap("manual_06_templates_studio_overview.png", "Templates Studio Catalog")

    # ── 6. Domain Manager: Buy Domains Modal ───────────────────
    try:
        driver.execute_script("openBuyDomainsModal(); switchDomainTab('search');")
        time.sleep(1.5)
        snap("manual_07_domain_manager_buy_search.png", "Domain Manager: Buy Domains Search Modal")
    except Exception as e:
        print("Error Buy Domains:", e)

    # ── 7. Domain Manager: Owned Domains Tab ──────────────────
    try:
        driver.execute_script("switchDomainTab('owned');")
        time.sleep(1.5)
        snap("manual_08_domain_manager_owned.png", "Domain Manager: Owned Domains Table")
    except Exception as e:
        print("Error Owned Domains:", e)

    # ── 8. Domain Manager: Deleted Domains Modal ──────────────
    try:
        driver.execute_script("closeBuyDomainsModal(); openDeletedDomainsModal();")
        time.sleep(1.5)
        snap("manual_09_domain_manager_deleted.png", "Domain Manager: Deleted & Archived Domains")
        driver.execute_script("closeDeletedDomainsModal();")
    except Exception as e:
        print("Error Deleted Domains:", e)

    # ── 9. Templates: Teams Meeting (Preland, Landing, Success)
    driver.get(f"{BASE_URL}/preview/preland?template=Teams%20Meeting")
    time.sleep(1.5)
    snap("manual_10_template_teams_preland.png", "Teams Meeting: Pre-land Lure")

    driver.get(f"{BASE_URL}/preview/landing?template=Teams%20Meeting&mode=S")
    time.sleep(1.5)
    snap("manual_11_template_teams_landing.png", "Teams Meeting: Device Code Landing")

    driver.get(f"{BASE_URL}/preview/success?template=Teams%20Meeting")
    time.sleep(1.5)
    snap("manual_12_template_teams_success.png", "Teams Meeting: Admitted Success State")

    # ── 10. Templates: Cloud Voicemail (Preland, Landing, Success)
    driver.get(f"{BASE_URL}/preview/preland?template=Cloud%20Voicemail")
    time.sleep(1.5)
    snap("manual_13_template_voicemail_preland.png", "Cloud Voicemail: Pre-land Lure")

    driver.get(f"{BASE_URL}/preview/landing?template=Cloud%20Voicemail&mode=S")
    time.sleep(1.5)
    snap("manual_14_template_voicemail_landing.png", "Cloud Voicemail: Device Code Landing")

    driver.get(f"{BASE_URL}/preview/success?template=Cloud%20Voicemail")
    time.sleep(1.5)
    snap("manual_15_template_voicemail_success.png", "Cloud Voicemail: Verified Success State")

    # ── 11. Templates: OneDrive (Preland, Landing, Success) ───
    driver.get(f"{BASE_URL}/preview/preland?template=OneDrive")
    time.sleep(1.5)
    snap("manual_16_template_onedrive_preland.png", "OneDrive: Pre-land Lure")

    driver.get(f"{BASE_URL}/preview/landing?template=OneDrive&mode=S")
    time.sleep(1.5)
    snap("manual_17_template_onedrive_landing.png", "OneDrive: Device Code Landing")

    driver.get(f"{BASE_URL}/preview/success?template=OneDrive")
    time.sleep(1.5)
    snap("manual_18_template_onedrive_success.png", "OneDrive: Document Unlocked Success State")

    # ── 12. Templates: Adobe & DocuSign Prelands ──────────────
    driver.get(f"{BASE_URL}/preview/preland?template=Adobe")
    time.sleep(1.5)
    snap("manual_19_template_adobe_preland.png", "Adobe Sign: Pre-land Lure")

    driver.get(f"{BASE_URL}/preview/preland?template=DocuSign")
    time.sleep(1.5)
    snap("manual_20_template_docusign_preland.png", "DocuSign: Pre-land Lure")

    # Return to Dashboard for remaining modules
    driver.get(f"{BASE_URL}/dashboard")
    time.sleep(2)

    # ── 13. Mailbox Intelligence & Modals ─────────────────────
    driver.execute_script("showPage('mailbox')")
    time.sleep(2.5)
    snap("manual_21_mailbox_suite_explorer.png", "Mailbox Explorer & Message Viewer")

    # Mailbox Compose Modal
    try:
        driver.execute_script("if (typeof openComposeModal === 'function') openComposeModal(); else document.querySelector('.ribbon-split-btn').click();")
        time.sleep(1.5)
        snap("manual_22_mailbox_compose_modal.png", "Mailbox Compose Email Modal")
        driver.execute_script("if (typeof closeComposeModal === 'function') closeComposeModal();")
    except Exception as e:
        print("Mailbox compose error:", e)

    # Mailbox Rules Modal
    try:
        driver.execute_script("if (typeof openSettingsModal === 'function') openSettingsModal(); else document.getElementById('suite-btn-settings').click();")
        time.sleep(1.2)
        driver.execute_script("let t = document.getElementById('tab-nav-rules'); if (t) t.click(); if (typeof openNewRuleForm === 'function') openNewRuleForm();")
        time.sleep(1.5)
        snap("manual_23_mailbox_stealth_rules.png", "Mailbox Stealth Inbox Rules Engine")
        driver.execute_script("let m = document.getElementById('settingsModal') || document.querySelector('.modal'); if (m) m.style.display='none';")
    except Exception as e:
        print("Mailbox rules error:", e)

    # ── 14. Keyword Alerts & Modals ───────────────────────────
    driver.execute_script("showPage('keyword-alerts')")
    time.sleep(2)
    snap("manual_24_keyword_alerts_ledger.png", "Keyword Surveillance & Hit Ledger")

    try:
        driver.execute_script("if (typeof openNewRuleModal === 'function') openNewRuleModal(); else if (typeof openAddRuleModal === 'function') openAddRuleModal();")
        time.sleep(1.5)
        snap("manual_25_keyword_new_rule_modal.png", "Keyword Surveillance New Rule Creator")
        driver.execute_script("let m = document.getElementById('newRuleModal') || document.querySelector('.modal'); if (m) m.style.display='none';")
    except Exception as e:
        print("Keyword rule modal error:", e)

    # ── 15. Extractor & Sorter ────────────────────────────────
    driver.execute_script("showPage('extractor')")
    time.sleep(1.5)
    # Put sample data in extractor to show realistic working screenshot!
    driver.execute_script("""
        let ta = document.getElementById('ext-input') || document.querySelector('#page-extractor textarea');
        if (ta) {
            ta.value = "admin@victim-corp.com:P@ssword2026!\\njohn.doe@victim-corp.com:Winter2026!\\nhttps://login.microsoftonline.com/common/oauth2/v2.0/token\\nsarah.connor@cyberdyne.org:Skynet#991\\neyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token_payload\\nadmin@victim-corp.com:P@ssword2026!";
            ta.dispatchEvent(new Event('input'));
        }
        let btn = document.getElementById('btn-extract-emails') || document.querySelector('#page-extractor button');
        if (btn) btn.click();
    """)
    time.sleep(1.5)
    snap("manual_26_extractor_sorter_suite.png", "Extractor & Sorter Suite with Loaded Input & Results")

    # ── 16. B2B Campaign Sender ───────────────────────────────
    driver.execute_script("showPage('b2b')")
    time.sleep(1.5)
    # Fill in sample campaign details to show realistic operation
    driver.execute_script("""
        let cName = document.getElementById('b2b-campaign-name') || document.querySelector('#page-b2b input[type=\"text\"]');
        if (cName) { cName.value = "Q4 Executive Security Review - Internal Phish"; cName.dispatchEvent(new Event('input')); }
        let cSub = document.getElementById('b2b-subject') || document.querySelectorAll('#page-b2b input[type=\"text\"]')[1];
        if (cSub) { cSub.value = "Urgent: Microsoft Teams Executive Briefing Access Required"; cSub.dispatchEvent(new Event('input')); }
        let cRec = document.getElementById('b2b-recipients') || document.querySelector('#page-b2b textarea');
        if (cRec) { cRec.value = "david.vance@targetcorp.com, David Vance, VP Operations\\nellen.ripley@targetcorp.com, Ellen Ripley, Dir Security"; cRec.dispatchEvent(new Event('input')); }
    """)
    time.sleep(1.5)
    snap("manual_27_b2b_campaign_sender.png", "B2B Targeted Spear-Phishing Campaign Builder")

    # ── 17. Live Sessions Vault ───────────────────────────────
    driver.execute_script("showPage('sessions')")
    time.sleep(2)
    snap("manual_28_live_sessions_vault.png", "Captured Victim OAuth Sessions & PRT Vault")

    # ── 18. Operators Management & Modal ──────────────────────
    driver.execute_script("showPage('operators')")
    time.sleep(2)
    snap("manual_29_operators_rbac_ledger.png", "Role-Based Access Control & Operators Ledger")

    try:
        driver.execute_script("if (typeof openAddOperatorModal === 'function') openAddOperatorModal(); else document.querySelector('#page-operators button').click();")
        time.sleep(1.5)
        snap("manual_30_add_operator_modal.png", "Operator Provisioning & Telegram Binding Modal")
        driver.execute_script("let m = document.getElementById('operatorModal') || document.querySelector('.modal'); if (m) m.style.display='none';")
    except Exception as e:
        print("Operator modal error:", e)

    # ── 19. Platform Settings ─────────────────────────────────
    driver.execute_script("showPage('settings')")
    time.sleep(2)
    snap("manual_31_platform_settings.png", "Enterprise Azure Entra ID & Infrastructure Settings")

finally:
    driver.quit()

print("\n=== ALL MANUAL VISUAL PROOFS SUCCESSFULLY HARVESTED ===")
