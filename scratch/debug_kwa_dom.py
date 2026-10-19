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

    driver.execute_script("showPage('keyword-alerts')")
    time.sleep(1)

    page = driver.find_element(By.ID, 'page-keyword-alerts')
    print("Page class:", page.get_attribute('class'))
    print("Page displayed:", page.is_displayed())
    print("Page size:", page.size)
    print("Parent class:", driver.execute_script("return arguments[0].parentElement.className;", page))
    print("Parent size:", driver.execute_script("return {w: arguments[0].parentElement.offsetWidth, h: arguments[0].parentElement.offsetHeight};", page))

    # Check for console errors
    logs = driver.get_log('browser')
    print("Browser logs:")
    for l in logs:
        print(f"[{l['level']}] {l['message']}")
finally:
    driver.quit()
