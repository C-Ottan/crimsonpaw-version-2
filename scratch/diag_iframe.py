from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1000')
driver = webdriver.Chrome(options=opts)

driver.get('http://127.0.0.1:5000/login')
driver.find_element(By.ID, 'username').send_keys('admin')
driver.find_element(By.ID, 'password').send_keys('admin')
driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
time.sleep(1.5)

driver.execute_script("""
window._resizeLogs = [];
window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'outlook-frame-resize') {
        window._resizeLogs.push(e.data);
    }
});
showPage('mailbox');
""")
time.sleep(2.5)

cards = driver.find_elements(By.CSS_SELECTOR, '.outlook-msg-card')
print(f"Cards found: {len(cards)}")
if cards:
    cards[0].click()
    time.sleep(2.5)

    logs = driver.execute_script('return window._resizeLogs;')
    print('Resize logs:', logs)

    iframes = driver.find_elements(By.CSS_SELECTOR, '.email-body-iframe')
    if iframes:
        print('iframe style.height:', iframes[0].get_attribute('style'))
        driver.switch_to.frame(iframes[0])
        body_h = driver.execute_script('return document.body.scrollHeight;')
        doc_h = driver.execute_script('return document.documentElement.scrollHeight;')
        root = driver.execute_script('return document.getElementById("email-body-root") ? document.getElementById("email-body-root").offsetHeight : null;')
        print(f'Inside iframe: body_scrollHeight={body_h}, doc_scrollHeight={doc_h}, root_offsetHeight={root}')
        driver.switch_to.default_content()

driver.quit()
