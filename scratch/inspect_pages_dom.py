import requests
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

print("Current URL:", driver.current_url)
print("Title:", driver.title)

# Check all sidebar links or buttons
sidebar_items = driver.execute_script("""
    return Array.from(document.querySelectorAll('a, button, [onclick]')).map(el => ({
        tag: el.tagName,
        id: el.id,
        text: el.innerText.trim(),
        onclick: el.getAttribute('onclick')
    })).filter(x => x.onclick && x.onclick.includes('showPage'));
""")
print(f"Sidebar showPage items ({len(sidebar_items)}):")
for item in sidebar_items:
    print(f"[{item['id']}] -> onclick={item['onclick']}")

# Check all elements with id starting with page-
pages = driver.execute_script("""
    return Array.from(document.querySelectorAll('[id^="page-"]')).map(el => ({
        id: el.id,
        display: el.style.display,
        classList: Array.from(el.classList)
    }));
""")
print("\nAll page containers:")
for p in pages:
    print(p)

driver.quit()
