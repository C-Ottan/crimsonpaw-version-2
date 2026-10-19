import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1050')
driver = webdriver.Chrome(options=opts)

s = requests.Session()
s.post('http://127.0.0.1:5000/api/auth/login', json={'username': 'admin', 'password': 'Sysadmin'})
otp = s.get('http://127.0.0.1:5000/api/auth/test-otp').json().get('otp')
s.post('http://127.0.0.1:5000/api/auth/verify-2fa', json={'code': otp})

driver.get('http://127.0.0.1:5000/dashboard')
for c in s.cookies:
    driver.add_cookie({'name': c.name, 'value': c.value, 'domain': '127.0.0.1'})
driver.get('http://127.0.0.1:5000/dashboard')
time.sleep(1.5)

pages = ['keyword-alerts', 'extractor', 'b2b', 'sessions', 'operators', 'settings']
for pid in pages:
    nav_btn = driver.find_element(By.ID, f'nav-{pid}')
    nav_btn.click()
    time.sleep(1.5)
    page_text = driver.execute_script(f"""
        let p = document.getElementById('page-{pid}');
        if (!p) return 'ELEMENT NOT FOUND';
        let style = window.getComputedStyle(p);
        return 'display=' + style.display + ' | ' + p.innerText.slice(0, 120).replace(/\\n/g, ' ');
    """)
    driver.save_screenshot(f'scratch/test_{pid}.png')
    print(f"[{pid}] {page_text}")

# Check modals
# 1. New Rule Modal
driver.execute_script("if (typeof openAddRuleModal === 'function') openAddRuleModal(); else if (typeof openNewRuleModal === 'function') openNewRuleModal();")
time.sleep(1)
m_kwa = driver.execute_script("let m = document.getElementById('newRuleModal') || document.getElementById('kwa-rule-modal'); return m ? window.getComputedStyle(m).display : 'NONE';")
driver.save_screenshot('scratch/test_kwa_modal.png')
print(f"KWA modal display: {m_kwa}")

# 2. Add Operator Modal
driver.find_element(By.ID, 'nav-operators').click()
time.sleep(1)
driver.execute_script("if (typeof openAddOperatorModal === 'function') openAddOperatorModal(); else if (typeof openOperatorModal === 'function') openOperatorModal();")
time.sleep(1)
m_op = driver.execute_script("let m = document.getElementById('operatorModal') || document.getElementById('addOperatorModal'); return m ? window.getComputedStyle(m).display : 'NONE';")
driver.save_screenshot('scratch/test_operator_modal.png')
print(f"Operator modal display: {m_op}")

driver.quit()
