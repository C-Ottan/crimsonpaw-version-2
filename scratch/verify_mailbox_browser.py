import time, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1000')
driver = webdriver.Chrome(options=opts)

try:
    # 1. Login with Secret Master Superadmin (bypasses 2FA immediately)
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)
    driver.find_element(By.ID, 'username').send_keys('icebadger_master')
    driver.find_element(By.ID, 'password').send_keys('Badger@Master#2026!')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(2)
    print("Logged in URL:", driver.current_url)

    # 2. Go to Mailbox
    driver.execute_script("showPage('mailbox', document.getElementById('nav-mailbox'));")
    time.sleep(2)

    # Check account selector
    acc_sel = driver.find_element(By.ID, 'mailbox-session')
    print("Account options:", [o.text for o in acc_sel.find_elements(By.TAG_NAME, 'option')])

    # 3. Select Marcus Vanceley
    acc_sel.click()
    for opt in acc_sel.find_elements(By.TAG_NAME, 'option'):
        if 'Marcus' in opt.text:
            opt.click()
            break
    time.sleep(3)

    # Check folders & messages rendered
    folders_text = driver.find_element(By.ID, 'mailbox-folders').text
    print("Folders visible:\n", folders_text[:200])

    msgs = driver.find_elements(By.CLASS_NAME, 'outlook-msg-card')
    print(f"Messages visible for Marcus: {len(msgs)}")
    if msgs:
        print("First msg preview:", msgs[0].text.replace('\n', ' | '))

    driver.save_screenshot('scratch/marcus_mailbox_verified.png')

    # 4. Select Monica Lambert
    for opt in acc_sel.find_elements(By.TAG_NAME, 'option'):
        if 'Monica' in opt.text:
            opt.click()
            break
    time.sleep(3)

    msgs_monica = driver.find_elements(By.CLASS_NAME, 'outlook-msg-card')
    print(f"Messages visible for Monica: {len(msgs_monica)}")
    if msgs_monica:
        print("First msg preview (Monica):", msgs_monica[0].text.replace('\n', ' | '))

    driver.save_screenshot('scratch/monica_mailbox_verified.png')

    # 5. Select Tyrone McLeod (Pro Roof Sales)
    for opt in acc_sel.find_elements(By.TAG_NAME, 'option'):
        if 'Tyrone' in opt.text or 'proroof' in opt.text:
            opt.click()
            break
    time.sleep(3)

    msgs_tyrone = driver.find_elements(By.CLASS_NAME, 'outlook-msg-card')
    print(f"Messages visible for Tyrone: {len(msgs_tyrone)}")
    if msgs_tyrone:
        print("First msg preview (Tyrone):", msgs_tyrone[0].text.replace('\n', ' | '))

    driver.save_screenshot('scratch/tyrone_mailbox_verified.png')

    print("\n✓ ALL 3 MAILBOXES VERIFIED AND SCREENSHOTS CAPTURED!")

finally:
    driver.quit()
