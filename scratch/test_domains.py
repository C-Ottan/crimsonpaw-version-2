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
driver = webdriver.Chrome(options=chrome_options)

try:
    print("[1] Opening Crimson Paw...")
    driver.get('http://127.0.0.1:5000/login')
    driver.add_cookie({'name': 'session', 'value': session_val, 'path': '/'})
    driver.get('http://127.0.0.1:5000/dashboard')
    time.sleep(1)

    print("[2] Navigating to Templates...")
    driver.execute_script("showPage('templates');")
    time.sleep(1)

    # 1. Click "Buy domains" subnav tab
    print("[3] Clicking 'Buy domains' tab...")
    buy_tab = driver.find_element(By.XPATH, "//div[contains(@class, 'lg-nav-tab') and contains(., 'Buy domains')]")
    buy_tab.click()
    time.sleep(1)

    buy_modal = driver.find_element(By.ID, "buyDomainsModal")
    print(f"Buy domains modal active: {buy_modal.is_displayed()}")
    assert buy_modal.is_displayed(), "Error: buyDomainsModal is not displayed!"

    # 2. Search for domains
    print("[4] Searching domains for 'cloud-auth'...")
    kw_input = driver.find_element(By.ID, "dm-search-keyword")
    kw_input.clear()
    kw_input.send_keys("cloud-auth")
    search_btn = driver.find_element(By.CSS_SELECTOR, ".dm-search-bar button")
    search_btn.click()
    time.sleep(2)

    results_tbody = driver.find_element(By.ID, "dm-search-results-tbody")
    results_text = results_tbody.text
    print("Search results preview:\n", results_text[:200])
    driver.save_screenshot('scratch/verify_buy_domains_open.png')
    print("Saved scratch/verify_buy_domains_open.png")

    # 3. Click Buy Now on the first available domain
    print("[5] Purchasing first domain...")
    buy_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Buy Now')]")
    assert len(buy_btns) > 0, "Error: No Buy Now buttons found in search results"
    driver.execute_script("arguments[0].click();", buy_btns[0])
    time.sleep(0.5)

    # Confirm via in-app confirm modal
    confirm_btn = driver.find_element(By.ID, "appConfirmBtn")
    driver.execute_script("arguments[0].click();", confirm_btn)
    time.sleep(1.5)

    # Verify owned domains table has the new domain
    owned_tbody = driver.find_element(By.ID, "dm-owned-domains-tbody")
    print("Owned domains table:\n", owned_tbody.text)
    assert "cloud-auth" in owned_tbody.text, "Error: Newly bought domain not in Owned Domains table!"
    driver.save_screenshot('scratch/verify_domain_bought.png')
    print("Saved scratch/verify_domain_bought.png")

    # 4. Remove / Retire the domain
    print("[6] Retiring domain to archive...")
    del_domain_btn = driver.find_element(By.XPATH, "//button[contains(@title, 'Delete Domain')]")
    driver.execute_script("arguments[0].click();", del_domain_btn)
    time.sleep(0.5)
    confirm_btn = driver.find_element(By.ID, "appConfirmBtn")
    driver.execute_script("arguments[0].click();", confirm_btn)
    time.sleep(1)

    # Close buy modal
    driver.execute_script("closeBuyDomainsModal();")
    time.sleep(0.5)

    # 5. Open Deleted Domain modal
    print("[7] Opening 'Deleted Domain' modal...")
    del_tab = driver.find_element(By.XPATH, "//div[contains(@class, 'lg-nav-tab') and contains(., 'Deleted Domain')]")
    driver.execute_script("arguments[0].click();", del_tab)
    time.sleep(1)

    del_modal = driver.find_element(By.ID, "deletedDomainsModal")
    print(f"Deleted domains modal active: {del_modal.is_displayed()}")
    assert del_modal.is_displayed(), "Error: deletedDomainsModal is not displayed!"

    del_tbody = driver.find_element(By.ID, "dm-deleted-tbody")
    print("Deleted archive table:\n", del_tbody.text)
    assert "cloud-auth" in del_tbody.text, "Error: Retired domain not found in Deleted Domains archive!"
    driver.save_screenshot('scratch/verify_deleted_domains_modal.png')
    print("Saved scratch/verify_deleted_domains_modal.png")

    # 6. Click Restore on the retired domain
    print("[8] Restoring domain from archive...")
    restore_btn = driver.find_element(By.CSS_SELECTOR, "#dm-deleted-tbody button")
    driver.execute_script("arguments[0].click();", restore_btn)
    time.sleep(1)

    toast_txt = driver.execute_script("return document.getElementById('toast').innerText;")
    print(f"Toast notification after restore: '{toast_txt}'")
    assert "restored" in toast_txt.lower(), f"Unexpected toast: {toast_txt}"
    driver.save_screenshot('scratch/verify_restored_domain.png')
    print("Saved scratch/verify_restored_domain.png")

    print("\n>>> ALL DOMAIN STORE & ARCHIVE TESTS PASSED SUCCESSFULLY! <<<")

finally:
    driver.quit()
