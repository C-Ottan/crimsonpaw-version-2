import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1600,1000')

driver = webdriver.Chrome(options=options)
try:
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)
    driver.find_element(By.ID, 'username').send_keys('admin')
    driver.find_element(By.ID, 'password').send_keys('admin')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(1.5)

    # Click Keyword Alerts nav item in sidebar
    driver.execute_script("showPage('keyword-alerts')")
    time.sleep(2)
    driver.save_screenshot('scratch/dashboard_page_keyword_alerts.png')
    print('Screenshot saved!')
finally:
    driver.quit()
