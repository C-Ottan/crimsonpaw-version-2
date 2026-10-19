import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"

print("\n[1] Testing Web UI via Headless Chrome...")
opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1050')
opts.add_argument('--disable-gpu')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=opts)
try:
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("admin")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(2)

    # Switch to Mailbox tab
    driver.execute_script("showPage('mailbox')")
    time.sleep(2)
    print("Switched to Mailbox page.")

    # Select Info@proroofsales.com (DVWRHR76J)
    uc = "DVWRHR76J"
    driver.execute_script(f"""
        const sel = document.getElementById('mailbox-session');
        if (sel) {{
            sel.value = '{uc}';
            sel.dispatchEvent(new Event('change'));
        }}
    """)
    time.sleep(4)

    # Find the cards in the list
    cards = driver.find_elements(By.CLASS_NAME, "outlook-msg-card")
    print(f"Total message cards rendered for {uc}: {len(cards)}")
    assert len(cards) > 0, "No message cards rendered!"

    target_card = None
    for c in cards:
        txt = c.text
        if "FreshBooks" in txt or "Quote" in txt or "INV" in txt:
            target_card = c
            break

    if not target_card:
        target_card = cards[0]

    print(f"Clicking target email card: {target_card.text[:60].replace(chr(10), ' | ')}...")
    target_card.click()
    time.sleep(3)

    # Check for .owa-attachments-bar
    bars = driver.find_elements(By.CLASS_NAME, "owa-attachments-bar")
    print(f"Attachment bars found: {len(bars)}")
    assert len(bars) > 0, "Attachment bar not found!"

    # Check attachment cards
    att_cards = driver.find_elements(By.CLASS_NAME, "owa-attachment-card")
    print(f"Attachment cards rendered: {len(att_cards)}")
    assert len(att_cards) > 0, "No attachment cards rendered!"

    for idx, ac in enumerate(att_cards):
        print(f"Card {idx}: {ac.text.replace(chr(10), ' | ')}")

    # Take screenshot of reading pane with attachment bar
    screenshot_bar_path = r"C:\Users\IT-ADMIN\.gemini\antigravity-ide\brain\9c1c5fe9-439d-41a6-9fe9-389c0d6f9518\mailbox_attachment_card.png"
    driver.save_screenshot(screenshot_bar_path)
    print("Saved screenshot:", screenshot_bar_path)

    # Click the attachment card to open preview
    print("Clicking attachment card to trigger Preview...")
    att_cards[0].click()
    time.sleep(2)

    modal = driver.find_element(By.ID, "outlookAttachmentPreviewModal")
    assert "active" in modal.get_attribute("class"), "Preview modal did not activate!"
    print("Preview modal activated successfully!")

    title_text = driver.find_element(By.ID, "preview-file-name").text
    size_text = driver.find_element(By.ID, "preview-file-size").text
    print(f"Modal Header: {title_text} ({size_text})")

    # Take screenshot of preview modal
    screenshot_prev_path = r"C:\Users\IT-ADMIN\.gemini\antigravity-ide\brain\9c1c5fe9-439d-41a6-9fe9-389c0d6f9518\mailbox_attachment_preview.png"
    driver.save_screenshot(screenshot_prev_path)
    print("Saved screenshot:", screenshot_prev_path)

    # Test clicking Download button inside preview
    dl_btn = driver.find_element(By.ID, "preview-modal-download-btn")
    dl_btn.click()
    time.sleep(1)
    print("Download button in preview clicked successfully!")

    # Close modal
    close_btn = driver.find_element(By.CSS_SELECTOR, "#outlookAttachmentPreviewModal .owa-win-btn.close")
    close_btn.click()
    time.sleep(1)
    assert "active" not in modal.get_attribute("class"), "Modal failed to close!"
    print("Preview modal closed cleanly.")

    print("\n✓✓✓ ALL ATTACHMENT TESTS PASSED WITH 100% SUCCESS! ✓✓✓")

finally:
    driver.quit()
