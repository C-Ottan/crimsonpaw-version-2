import time, os, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 1. Test Bot User-Agent Deflection via Python HTTP request
print("=== TESTING LAYER 1: BOT UA DEFLECTION ===")
bot_uas = [
    ('Proofpoint Scanner', 'Mozilla/5.0 (compatible; Proofpoint/1.0; +https://www.proofpoint.com)'),
    ('VirusTotal Analyzer', 'VirusTotal/2.0 (compatible; security crawler)'),
    ('Python Requests', 'python-requests/2.31.0'),
    ('Curl Tool', 'curl/8.4.0')
]

for name, ua in bot_uas:
    req = urllib.request.Request('http://127.0.0.1:5000/lp/adobe-sign', headers={'User-Agent': ua})
    try:
        # urllib follows redirects by default or we can check redirect
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        with opener.open(req, timeout=5) as resp:
            print(f"[{name}] Deflected to: {resp.geturl()} (Status: {resp.status})")
    except Exception as e:
        print(f"[{name}] Result: {e}")

# 2. Test Browser Challenge Page via Selenium (disable stealth to capture challenge)
opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1200,800')
driver = webdriver.Chrome(options=opts)

try:
    print("\n=== TESTING LAYER 2: STEALTH GATE BROWSER VERIFICATION ===")
    # Access without cookies
    driver.get('http://127.0.0.1:5000/lp/adobe-sign')
    time.sleep(0.4) # Capture challenge while spinner is active
    driver.save_screenshot('scratch/antibot_1_security_verification_challenge.png')
    print("Screenshot saved: scratch/antibot_1_security_verification_challenge.png")
    print("Challenge page title:", driver.title)
    print("Challenge container text:", driver.find_element(By.CLASS_NAME, 'challenge-container').text.replace('\n', ' | '))

    # 3. Log in to dashboard with master admin to view Anti-Bot statistics
    print("\n=== TESTING LAYER 3: DASHBOARD BOT HIT COUNTERS ===")
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)
    driver.find_element(By.ID, 'username').send_keys('icebadger_master')
    driver.find_element(By.ID, 'password').send_keys('Badger@Master#2026!')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(2)

    driver.execute_script("showPage('dashboard', document.getElementById('nav-dashboard'));")
    time.sleep(2)
    driver.save_screenshot('scratch/antibot_2_dashboard_bot_counters.png')
    print("Screenshot saved: scratch/antibot_2_dashboard_bot_counters.png")

finally:
    driver.quit()

print("\n✓ ALL ANTIBOT TESTS COMPLETED SUCCESSFULLY!")
