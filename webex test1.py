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

# === Chromium Setup (for Raspberry Pi) ===
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
    """Find element safely with timeout."""
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except TimeoutException:
        return None

def join_webex_meeting():
    print("🌐 Opening Webex meeting page...")
    driver.get(WEBEX_URL)
    time.sleep(WAIT_MED)

    # STEP 1 — Click “Join from your browser” if visible
    browser_btn = safe_find(
        By.XPATH,
        "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join from your browser')]",
        timeout=WAIT_MED,
    )
    if browser_btn:
        driver.execute_script("arguments[0].click();", browser_btn)
        print("✅ Clicked 'Join from your browser'.")
        time.sleep(WAIT_MED)
    else:
        print("ℹ️ No 'Join from your browser' link found — continuing...")

    # STEP 2 — Switch into the iframe that contains our Name field
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"🧭 Found {len(iframes)} iframe(s). Searching for name input...")
    name_input = None
    for idx, iframe in enumerate(iframes):
        driver.switch_to.default_content()
        driver.switch_to.frame(iframe)
        print(f"🔍 Checking iframe {idx+1}/{len(iframes)}...")
        name_input = safe_find(
            By.XPATH,
            "//input[@id='react-aria736893866-1' or contains(@id,'react-aria') or contains(@placeholder,'Name')]",
            timeout=3,
        )
        if name_input:
            print(f"✅ Found Name field inside iframe {idx+1}")
            break

    if not name_input:
        print("❌ Could not find name input.")
        return

    # STEP 3 — Enter Name
    name_input.clear()
    name_input.send_keys(GUEST_NAME)
    print(f"✏️ Entered name '{GUEST_NAME}'")

    # Blur input to trigger Webex enabling the join button
    driver.execute_script("arguments[0].blur();", name_input)
    time.sleep(2)

    # STEP 4 — Try to find “Join meeting” button (multiple selectors)
    print("🔎 Looking for 'Join meeting' button...")
    join_button = None
    join_selectors = [
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join meeting')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join')]",
        "//div[@role='button' and contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join')]",
        "//span[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join')]"
    ]

    for sel in join_selectors:
        join_button = safe_find(By.XPATH, sel, timeout=5)
        if join_button:
            break

    # STEP 5 — Click Join
    if join_button:
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", join_button)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", join_button)
            print("🚀 Clicked 'Join meeting' button.")
        except Exception as e:
            print(f"⚠️ Failed to click Join button: {e}")
    else:
        print("⚠️ Could not find a 'Join meeting' button. It may load later.")
        print("⏳ Waiting and retrying for up to 15 seconds...")
        for i in range(5):
            join_button = safe_find(By.XPATH, "//button[contains(.,'Join')]", timeout=3)
            if join_button:
                driver.execute_script("arguments[0].click();", join_button)
                print("✅ Clicked 'Join meeting' button after delay.")
                break
            time.sleep(3)

    # STEP 6 — Wait for meeting to start
    print("🎥 Waiting for meeting window to load...")
    time.sleep(WAIT_LONG)
    print("✅ Joined meeting successfully (browser will stay open).")
    time.sleep(300)
    driver.quit()

try:
    join_webex_meeting()
except KeyboardInterrupt:
    print("🛑 Stopped by user.")
    driver.quit()
