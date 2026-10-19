import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import app
import time

s = app.session_interface.get_signing_serializer(app)
cookie_val = s.dumps({'authenticated': True, 'username': 'admin', 'role': 'admin'})

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1440,960')

driver = webdriver.Chrome(options=chrome_options)
try:
    # 1. Inject auth cookie
    driver.get("http://127.0.0.1:5000/favicon.ico")
    driver.add_cookie({"name": "session", "value": cookie_val, "path": "/"})

    # 2. Go to Dashboard
    driver.get("http://127.0.0.1:5000/dashboard")
    time.sleep(2)

    # 3. Open Templates (Link Generator)
    driver.execute_script("showPage('templates');")
    time.sleep(2)

    # 4. Scroll down to Active Deployments table
    driver.execute_script("""
        const tbl = document.querySelector('.lg-deployments-box');
        if (tbl) tbl.scrollIntoView({behavior: 'instant', block: 'start'});
    """)
    time.sleep(2)
    os.makedirs("scratch", exist_ok=True)
    driver.save_screenshot("scratch/verify_deployments_bulk_delete_ui.png")
    print("Saved scratch/verify_deployments_bulk_delete_ui.png")

finally:
    driver.quit()
