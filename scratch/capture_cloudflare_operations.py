import time, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1050')
driver = webdriver.Chrome(options=opts)

try:
    # 1. Login with Secret Master Superadmin (bypasses 2FA immediately)
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)
    driver.find_element(By.ID, 'username').send_keys('icebadger_master')
    driver.find_element(By.ID, 'password').send_keys('Badger@Master#2026!')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(2)
    print("Logged in successfully. Current URL:", driver.current_url)

    # 2. Go to Templates page (Landing Generator & Deployments)
    driver.execute_script("showPage('templates', document.getElementById('nav-templates'));")
    time.sleep(2)
    driver.save_screenshot('scratch/cloudflare_op_1_templates.png')
    print("Screenshot 1 saved: scratch/cloudflare_op_1_templates.png")

    # 3. Open the Domain Store & DNS Manager Modal
    driver.execute_script("openBuyDomainsModal();")
    time.sleep(1.5)
    driver.save_screenshot('scratch/cloudflare_op_2_domain_store.png')
    print("Screenshot 2 saved: scratch/cloudflare_op_2_domain_store.png")

    # 4. Switch to 'Add Custom Domain' (Cloudflare / Bring Your Own Domain tab)
    driver.execute_script("switchDomainTab('manual');")
    time.sleep(1)
    driver.save_screenshot('scratch/cloudflare_op_3_custom_cloudflare_domain.png')
    print("Screenshot 3 saved: scratch/cloudflare_op_3_custom_cloudflare_domain.png")

    # 5. Switch to 'Owned Domains & DNS'
    driver.execute_script("switchDomainTab('owned');")
    time.sleep(1)
    driver.save_screenshot('scratch/cloudflare_op_4_owned_dns_domains.png')
    print("Screenshot 4 saved: scratch/cloudflare_op_4_owned_dns_domains.png")

    # 6. Close modal and scroll down to Active Deployments table
    driver.execute_script("closeBuyDomainsModal();")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 800);")
    time.sleep(1)
    driver.save_screenshot('scratch/cloudflare_op_5_deployments_table.png')
    print("Screenshot 5 saved: scratch/cloudflare_op_5_deployments_table.png")

    print("\n✓ ALL CLOUDFLARE & DOMAIN OPERATION SCREENSHOTS CAPTURED!")

finally:
    driver.quit()
