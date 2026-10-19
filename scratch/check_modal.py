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
    driver.execute_script("showPage('templates');")
    time.sleep(1)

    info = driver.execute_script("""
        const m = document.getElementById('buyDomainsModal');
        if (!m) return 'Modal not found in DOM!';
        m.classList.add('active');
        const style = window.getComputedStyle(m);
        return {
            display: style.display,
            visibility: style.visibility,
            opacity: style.opacity,
            zIndex: style.zIndex,
            width: style.width,
            height: style.height,
            position: style.position,
            parentTag: m.parentElement ? m.parentElement.tagName : null,
            parentId: m.parentElement ? m.parentElement.id : null,
            parentDisplay: m.parentElement ? window.getComputedStyle(m.parentElement).display : null
        };
    """)
    print('Modal info:', info)
finally:
    driver.quit()
