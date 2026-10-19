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
    time.sleep(1)
    driver.execute_script("showPage('linkgen');")
    time.sleep(1)
    driver.execute_script("loadDeploymentsTable();")
    time.sleep(1)
    html = driver.execute_script("return document.getElementById('lg-deployments-tbody').innerHTML;")
    print("HTML LENGTH:", len(html))
    print("HTML:", html)
finally:
    driver.quit()
