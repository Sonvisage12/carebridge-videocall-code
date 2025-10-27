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

# === Setup Chromium for Raspberry Pi ===
chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium-browser"
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--start-maximized")
# Uncomment if running without GUI
# chrome_options.add_argument("--headless=new")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)


def safe_find(by, selector, timeout=10):
    """Find element with timeout; return None if missing."""
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
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'join from your browser')]",
        timeout=WAIT_MED,
    )
    if browser_btn:
        driver.execute_script("arguments[0].click();", browser_btn)
        print("✅ Clicked 'Join from your browser'.")
        time.sleep(WAIT_MED)
    else:
        print("ℹ️ No 'Join from your browser' link found — continuing...")

    # STEP 2 — Switch into the correct iframe (the one containing our input)
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"🧭 Found {len(iframes)} iframe(s). Searching for target input...")
    name_input = None
    for idx, iframe in enumerate(iframes):
        driver.switch_to.default_content()
        driver.switch_to.frame(iframe)
        print(f"🔍 Checking iframe {idx+1}/{len(iframes)}...")
        try:
            # Try to find the known ID first, or a similar field
            name_input = safe_find(
                By.XPATH,
                "//input[@id='react-aria736893866-1' or contains(@id, 'react-aria') or contains(@placeholder,'Name')]",
                timeout=3,
            )
            if name_input:
                print(f"✅ Found Name field in iframe {idx+1}")
                break
        except Exception:
            pass

    if name_input:
        name_input.clear()
        name_input.send_keys(GUEST_NAME)
        print(f"✏️ Entered name '{GUEST_NAME}'")
    else:
        print("❌ Could not find name field in any iframe.")
        return

    # STEP 3 — Try to find a “Join” button near that field
    join_btn = safe_find(
        By.XPATH,
        "//button[contains(.,'Join') or contains(.,'Continue') or contains(.,'Next')]",
        timeout=5,
    )
    if join_btn:
        driver.execute_script("arguments[0].click();", join_btn)
        print("🚀 Clicked Join button.")
    else:
        print("⚠️ Join button not found; perhaps it appears after typing name.")

    print("🎥 Waiting for meeting to start...")
    time.sleep(WAIT_LONG)
    print("✅ Joined meeting successfully (browser will stay open).")
    time.sleep(300)
    driver.quit()


try:
    join_webex_meeting()
except KeyboardInterrupt:
    print("🛑 Interrupted by user.")
    driver.quit()

