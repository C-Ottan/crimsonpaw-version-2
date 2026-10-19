import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"

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

    # Select Info@proroofsales.com (DVWRHR76J)
    driver.execute_script("""
        const sel = document.getElementById('mailbox-session');
        if (sel) {
            sel.value = 'DVWRHR76J';
            sel.dispatchEvent(new Event('change'));
        }
    """)
    time.sleep(4)

    cards = driver.find_elements(By.CLASS_NAME, "outlook-msg-card")
    for c in cards:
        if "Quote" in c.text:
            c.click()
            break
    time.sleep(3)

    att_cards = driver.find_elements(By.CLASS_NAME, "owa-attachment-card")
    print(f"Attachment cards count: {len(att_cards)}")
    
    # Click the PDF card (second card)
    pdf_card = None
    for ac in att_cards:
        if "pdf" in ac.text.lower():
            pdf_card = ac
            break
    if not pdf_card and len(att_cards) > 1:
        pdf_card = att_cards[1]
        
    print(f"Clicking PDF attachment card: {pdf_card.text.replace(chr(10), ' | ')}...")
    pdf_card.click()
    time.sleep(2)

    modal = driver.find_element(By.ID, "outlookAttachmentPreviewModal")
    assert "active" in modal.get_attribute("class"), "PDF modal did not activate!"
    title_text = driver.find_element(By.ID, "preview-file-name").text
    print(f"PDF Preview Modal active for: {title_text}")

    # Verify iframe exists in preview modal body
    iframes = driver.find_elements(By.CSS_SELECTOR, "#preview-modal-body iframe")
    print(f"PDF iframes in preview body: {len(iframes)}")
    assert len(iframes) > 0, "PDF iframe preview not rendered!"

    driver.save_screenshot(r"C:\Users\IT-ADMIN\.gemini\antigravity-ide\brain\9c1c5fe9-439d-41a6-9fe9-389c0d6f9518\mailbox_attachment_pdf_preview.png")
    print("Saved screenshot: mailbox_attachment_pdf_preview.png")

    print("[SUCCESS] PDF preview modal verified cleanly!")
finally:
    driver.quit()
