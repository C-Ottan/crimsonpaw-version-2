import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

driver = None
try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    print('Chrome failed, trying Edge:', e)
    edge_options = EdgeOptions()
    edge_options.add_argument('--headless=new')
    edge_options.set_capability('ms:loggingPrefs', {'browser': 'ALL'})
    try:
        driver = webdriver.Edge(options=edge_options)
    except Exception as e2:
        print('Edge failed too:', e2)
        sys.exit(1)

try:
    print('Opening http://127.0.0.1:5000/login...')
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)

    # Login
    user_inp = driver.find_element(By.ID, 'username')
    pwd_inp = driver.find_element(By.ID, 'password')
    user_inp.send_keys('admin')
    pwd_inp.send_keys('admin')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(1.5)
    print('Current URL after login:', driver.current_url)

    # Navigate to templates
    driver.execute_script("showPage('templates')")
    time.sleep(1.5)

    # Dump any console logs so far
    print('--- Console logs after opening templates ---')
    for entry in driver.get_log('browser'):
        print(f"[{entry['level']}] {entry['message']}")

    # Click Landing preview tab or Landing editor
    print('Clicking btn-prev-landing...')
    btn_land = driver.find_element(By.ID, 'btn-prev-landing')
    btn_land.click()
    time.sleep(1)

    iframe = driver.find_element(By.ID, 'lg-preview-iframe')
    srcdoc_before = iframe.get_attribute('srcdoc') or ''
    print(f'Landing initial srcdoc length: {len(srcdoc_before)}')

    # Change landing template dropdown to Dropbox
    print('Changing lg-landing-template to Dropbox...')
    select_land = Select(driver.find_element(By.ID, 'lg-landing-template'))
    select_land.select_by_value('Dropbox')
    time.sleep(2)

    # Dump console logs after change
    print('--- Console logs after selecting Dropbox ---')
    for entry in driver.get_log('browser'):
        print(f"[{entry['level']}] {entry['message']}")

    srcdoc_after = iframe.get_attribute('srcdoc') or ''
    print(f'Landing srcdoc length after Dropbox: {len(srcdoc_after)}')
    print(f'Did srcdoc change? {srcdoc_before != srcdoc_after}')
    if srcdoc_after:
        print('Is Dropbox in srcdoc?', 'Dropbox' in srcdoc_after)

    # Now test Success
    print('\nClicking btn-prev-success...')
    btn_succ = driver.find_element(By.ID, 'btn-prev-success')
    btn_succ.click()
    time.sleep(1)

    srcdoc_succ_before = iframe.get_attribute('srcdoc') or ''
    print(f'Success initial srcdoc length: {len(srcdoc_succ_before)}')

    print('Changing lg-success-template to Adobe...')
    select_succ = Select(driver.find_element(By.ID, 'lg-success-template'))
    select_succ.select_by_value('Adobe')
    time.sleep(2)

    print('--- Console logs after selecting Adobe Success ---')
    for entry in driver.get_log('browser'):
        print(f"[{entry['level']}] {entry['message']}")

    srcdoc_succ_after = iframe.get_attribute('srcdoc') or ''
    print(f'Success srcdoc length after Adobe: {len(srcdoc_succ_after)}')
    print(f'Did success srcdoc change? {srcdoc_succ_before != srcdoc_succ_after}')
    if srcdoc_succ_after:
        print('Is Adobe in success srcdoc?', 'Adobe' in srcdoc_succ_after)

finally:
    driver.quit()
