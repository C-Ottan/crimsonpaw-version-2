import sys
sys.stdout.reconfigure(encoding='utf-8')
from itsdangerous import URLSafeTimedSerializer
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

signer = URLSafeTimedSerializer('crimson_paw_obsidian_ruby_key_2026', salt='cookie-session', signer_kwargs={'key_derivation': 'hmac', 'digest_method': 'sha1'})
session_val = signer.dumps({'authenticated': True, 'role': 'admin', 'username': 'admin'})

chrome_options = Options()
chrome_options.add_argument('--headless=new')
driver = webdriver.Chrome(options=chrome_options)
try:
    driver.get('http://127.0.0.1:5000/login')
    driver.add_cookie({'name': 'session', 'value': session_val, 'path': '/'})
    driver.get('http://127.0.0.1:5000/dashboard')
    time.sleep(2)
    logs = driver.get_log('browser')
    print('Console logs:')
    for l in logs:
        print(l)
    print('Current URL:', driver.current_url)
    print('Has showPage:', driver.execute_script("return typeof showPage;"))
finally:
    driver.quit()
