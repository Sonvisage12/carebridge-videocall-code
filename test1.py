from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

WEBEX_URL = "https://meet1492.webex.com/meet/pr23680413308"
GUEST_NAME = "CareBridge"

WAIT_SHORT, WAIT_MED, WAIT_LONG = 3, 8, 15

chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium-browser"
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--start-maximized")
# Uncomment if no GUI:
# chrome_options.add_argument("--headless=new")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)

def safe_find(by, selector, timeout=8):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except TimeoutException:
        return None

def join_webex_meeting():
    print("🌐 Opening Webex meeting page...")
    driver.get(WEBEX_URL)
    time.sleep(WAIT_MED)

    # STEP 1 — Click “Join from your browser” if present
    browser_btn = safe_find(
        By.XPATH,
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join from your browser')]",
        timeout=WAIT_MED,
    )
    if browser_btn:
        driver.execute_script("arguments[0].click();", browser_btn)
        print("✅ Clicked 'Join from your browser'.")
        time.sleep(WAIT_MED)
    else:
        print("ℹ️ No 'Join from your browser' link found — continuing...")

    # STEP 2 — Try each iframe to find the name field
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"🧭 Found {len(iframes)} iframes. Searching for name field...")

    found_name = False
    for i, iframe in enumerate(iframes):
        driver.switch_to.default_content()
        driver.switch_to.frame(iframe)
        print(f"🔍 Checking iframe {i+1}/{len(iframes)}")

        name_box = safe_find(
            By.XPATH,
            "//input[contains(@placeholder,'Name') or contains(@aria-label,'Name') or @required]",
            timeout=3,
        )
        if name_box:
            print(f"✅ Found name field inside iframe {i+1}")
            name_box.clear()
            name_box.send_keys(GUEST_NAME)
            print(f"✏️ Entered name '{GUEST_NAME}'")
            found_name = True
            # Try to click a Join or Continue button nearby
            join_btn = safe_find(
                By.XPATH,
                "//button[contains(., 'Join') or contains(., 'Continue') or contains(., 'Next')]",
                timeout=3,
            )
            if join_btn:
                driver.execute_script("arguments[0].click();", join_btn)
                print("🚀 Clicked Join button.")
            else:
                print("⚠️ Join button not found in this iframe.")
            break

    if not found_name:
        print("❌ Could not find any name field in available iframes.")

    print("🎥 Waiting for meeting room to load...")
    time.sleep(WAIT_LONG)
    print("✅ Finished (browser will stay open).")
    time.sleep(300)
    driver.quit()

try:
    join_webex_meeting()
except KeyboardInterrupt:
    print("🛑 Interrupted by user.")
    driver.quit()
