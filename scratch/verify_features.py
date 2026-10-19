import sys
sys.stdout.reconfigure(encoding='utf-8')
from itsdangerous import URLSafeTimedSerializer
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

signer = URLSafeTimedSerializer('crimson_paw_obsidian_ruby_key_2026', salt='cookie-session', signer_kwargs={'key_derivation': 'hmac', 'digest_method': 'sha1'})
session_val = signer.dumps({'authenticated': True, 'role': 'admin', 'username': 'admin'})

chrome_options = Options()
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--window-size=1600,1050')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')

driver = webdriver.Chrome(options=chrome_options)

try:
    print("[1] Opening Crimson Paw...")
    driver.get("http://127.0.0.1:5000/login")
    time.sleep(1)

    print("[2] Setting session cookie...")
    driver.add_cookie({
        'name': 'session',
        'value': session_val,
        'path': '/',
        'httpOnly': True
    })

    print("[3] Loading Dashboard...")
    driver.get("http://127.0.0.1:5000/dashboard")
    time.sleep(1.5)

    # 1. Test Dashboard Captured Table
    print("[4] Checking Dashboard Captured Table...")
    driver.execute_script("loadSessions();")
    time.sleep(1.5)

    dash_html = driver.execute_script("return document.getElementById('sessions-table').innerHTML;")
    has_pending_prt = "PENDING PRT" in dash_html
    has_registering = "REGISTERING" in dash_html
    print(f"Contains 'PENDING PRT': {has_pending_prt} (expected False)")
    print(f"Contains 'REGISTERING': {has_registering} (expected False)")
    assert not has_pending_prt, "Error: Dashboard still shows PENDING PRT"
    assert not has_registering, "Error: Dashboard still shows REGISTERING"

    # Count COOKIE buttons
    cookie_btns = driver.find_elements(By.CSS_SELECTOR, ".ab-action-cookie-btn")
    print(f"Found {len(cookie_btns)} active COOKIE buttons across captured victims.")
    assert len(cookie_btns) >= 4, f"Expected at least 4 cookie buttons, found {len(cookie_btns)}"

    driver.save_screenshot("scratch/verify_dashboard_clean_cookie.png")
    print("Screenshot saved: scratch/verify_dashboard_clean_cookie.png")

    # 2. Switch to Templates (Link Generator)
    print("[5] Switching to Templates / Link Generator...")
    driver.execute_script("showPage('templates');")
    time.sleep(1)
    driver.execute_script("loadDeploymentsTable();")
    time.sleep(1.5)

    # Scroll Active Deployments into view
    driver.execute_script("document.querySelector('.lg-deployments-box').scrollIntoView();")
    time.sleep(0.5)

    dep_tbody = driver.find_element(By.ID, "lg-deployments-tbody")
    # Verify no <a> tags with javascript:void(0) exist in deployed link cells
    links_with_js_void = dep_tbody.find_elements(By.CSS_SELECTOR, "a[href*='javascript']")
    print(f"Found javascript:void(0) links: {len(links_with_js_void)} (expected 0)")
    assert len(links_with_js_void) == 0, "Error: Still found <a> tag with javascript link"

    # Click on the first link span to test click-to-copy
    first_link = driver.find_element(By.CSS_SELECTOR, "#lg-deployments-tbody .lg-link-txt")
    print(f"First link element tag name: {first_link.tag_name} (expected span)")
    assert first_link.tag_name.lower() == "span", f"Expected span tag, got {first_link.tag_name}"

    driver.execute_script("arguments[0].scrollIntoView(true);", first_link)
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", first_link)
    time.sleep(0.5)

    toast_txt = driver.execute_script("return document.getElementById('toast').innerText;")
    print(f"Toast notification after clicking link: '{toast_txt}'")
    assert "link copied successfully" in toast_txt.lower(), f"Unexpected toast: {toast_txt}"

    driver.save_screenshot("scratch/verify_deployments_link_copied.png")
    print("Screenshot saved: scratch/verify_deployments_link_copied.png")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

finally:
    driver.quit()
