# VideoCall.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# === CONFIG ===
#url = "https://meet.jit.si/CareBridgeRoom"  # change meeting name as needed
url = "https://meet.jit.si/PremierFamiliesFundNevertheless"
WAIT_SHORT = 2
WAIT_MED = 6
WAIT_LONG = 15

# Chrome options - auto-allow mic/camera
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--use-fake-ui-for-media-stream")  # auto-allow mic/camera

driver = webdriver.Chrome(service=Service(), options=chrome_options)
driver.get(url)

def safe_find(by, selector, timeout=5):
    """Return element if found within timeout, else None."""
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except TimeoutException:
        return None

def dismiss_auth_or_recover_modal():
    """
    Detects typical 'Recover password' or auth modals and dismisses them.
    Strategies:
      - Click visible 'Cancel' or 'Close' button,
      - Click close (aria-label close) icons,
      - Press ESC as last resort.
    Returns True if a modal was found and we attempted to dismiss it.
    """
    found = False
    # Look for obvious text indicating recover-password modal
    try:
        # Search for any element containing the phrase 'Recover password' or 'Recover' or 'Reset your password'
        modal_el = None
        try:
            modal_el = driver.find_element(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'recover password')]")
        except NoSuchElementException:
            try:
                modal_el = driver.find_element(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reset your password')]")
            except NoSuchElementException:
                modal_el = None

        if modal_el:
            found = True
            print("⚠️ Detected a password-recover/auth modal — attempting to dismiss it...")

            # Try to click 'Cancel' buttons inside modal
            try:
                cancel_btn = modal_el.find_element(By.XPATH, ".//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') = 'cancel' or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cancel')]")
                driver.execute_script("arguments[0].scrollIntoView(true);", cancel_btn)
                time.sleep(0.2)
                cancel_btn.click()
                print("✅ Clicked 'Cancel' inside modal.")
                return True
            except Exception:
                pass

            # Try global 'Cancel' button
            try:
                global_cancel = driver.find_element(By.XPATH, "//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') = 'cancel']")
                driver.execute_script("arguments[0].click();", global_cancel)
                print("✅ Clicked global 'Cancel' button.")
                return True
            except Exception:
                pass

            # Try Close icon buttons often with aria-label 'Close' or class containing 'close'
            try:
                close_btn = modal_el.find_element(By.XPATH, ".//button[contains(@aria-label, 'Close') or contains(@class, 'close') or contains(@aria-label, 'close')]")
                driver.execute_script("arguments[0].click();", close_btn)
                print("✅ Clicked modal close button.")
                return True
            except Exception:
                pass

            # Try any visible button with text 'Send' or 'Cancel' as a fallback
            try:
                send_btn = modal_el.find_element(By.XPATH, ".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send')]")
                print("ℹ️ Modal shows 'Send' — clicking Cancel instead if present.")
            except Exception:
                pass

            # Fallback: press ESC key to close
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ESCAPE)
                print("✅ Pressed ESC to dismiss modal.")
                return True
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ Error while trying to dismiss modal: {e}")

    # Another defensive approach: try to click any visible overlay close btn
    try:
        overlay_close = safe_find(By.CSS_SELECTOR, "button[aria-label*='close'], button[class*='close'], button[title*='Close']", timeout=2)
        if overlay_close:
            try:
                driver.execute_script("arguments[0].click();", overlay_close)
                print("✅ Clicked overlay close button.")
                return True
            except Exception:
                pass
    except Exception:
        pass

    if not found:
        # No modal text found — nothing to dismiss
        return False

    return False

def join_meeting():
    print("🎥 Waiting for Jitsi pre-join screen...")
    time.sleep(WAIT_MED)  # let UI render

    # If page shows some site-level auth flow, try to dismiss it
    dismissed = dismiss_auth_or_recover_modal()
    if dismissed:
        # small pause after dismissing
        time.sleep(1)

    # --- switch into iframe if exists ---
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            driver.switch_to.frame(iframes[0])
            print(f"🧭 Switched into iframe (count={len(iframes)})")
    except Exception as e:
        print(f"⚠️ Error switching to iframe: {e}")

    # Re-run modal dismissal inside iframe (some sites render modals inside)
    try:
        dismissed_iframe = dismiss_auth_or_recover_modal()
        if dismissed_iframe:
            time.sleep(1)
    except Exception:
        pass

    # --- enter display name ---
    try:
        name_box = None
        # Wait up to a short time for name input (some flows skip it)
        try:
            name_box = WebDriverWait(driver, WAIT_SHORT).until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'name') or @aria-label='Your name' or @name='userName']"))
            )
        except TimeoutException:
            name_box = safe_find(By.XPATH, "//input[contains(@placeholder, 'name') or @aria-label='Your name' or @name='userName']", timeout=2)

        if name_box:
            try:
                name_box.clear()
                name_box.send_keys("CareBridge")
                print("✏️ Entered name: CareBridge")
            except Exception as e:
                print(f"⚠️ Could not type into name field: {e}")
        else:
            print("ℹ️ Name input not found (maybe pre-join is skipped).")
    except Exception as e:
        print(f"⚠️ Error locating name input: {e}")

    time.sleep(1)

    # --- find and click 'Join' button explicitly ---
    join_btn = None
    try:
        # Prefer an exact 'Join' visible button
        try:
            join_btn = driver.find_element(By.XPATH, "//button[normalize-space(text())='Join']")
            print("🔍 Found 'Join' button by exact text.")
        except NoSuchElementException:
            # Fallback: any button with 'join' in text (case-insensitive)
            try:
                join_btn = driver.find_element(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join')]")
                print("🔍 Found button with 'join' in text.")
            except NoSuchElementException:
                join_btn = None

        # If still not found, try data-testid or class-based selectors Jitsi commonly uses
        if not join_btn:
            selectors = [
                "button[data-testid='prejoin.joinMeeting']",
                "button[aria-label*='Join']",
                "button[class*='join']",
                "div[role='button'][class*='join']",
                "div[role='button'][aria-label*='Join']",
            ]
            for sel in selectors:
                try:
                    join_btn = driver.find_element(By.CSS_SELECTOR, sel)
                    print(f"🔍 Found join control using selector: {sel}")
                    break
                except NoSuchElementException:
                    join_btn = None
    except Exception as e:
        print(f"⚠️ Error while searching for join button: {e}")
        join_btn = None

    # click it if found
    if join_btn:
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", join_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", join_btn)
            print("✅ Clicked 'Join' button successfully.")
        except Exception as e:
            print(f"⚠️ Failed to click join button: {e}")
    else:
        print("⚠️ Could not find a Join button. Printing all buttons for debugging:")
        for b in driver.find_elements(By.TAG_NAME, "button"):
            # print short info about each button (text and attributes)
            try:
                txt = b.text.strip()
                outer = b.get_attribute("outerHTML")
                snippet = outer[:200].replace("\n", " ")
            except Exception:
                txt = "<could not read text>"
                snippet = "<could not read outerHTML>"
            print(f"   ▶ Button text: '{txt}' | html snippet: {snippet}")

    print("🎉 Join attempt complete.")

def handle_reconnect():
    try:
        el = driver.find_element(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reconnecting')]")
        print("🔄 Reconnecting detected — waiting...")
        time.sleep(WAIT_MED)
        return True
    except NoSuchElementException:
        return False

def handle_disconnect():
    try:
        el = driver.find_element(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'you have been disconnected')]")
        print("⚠️ Disconnected — refreshing and rejoining...")
        driver.refresh()
        time.sleep(WAIT_MED)
        join_meeting()
        return True
    except NoSuchElementException:
        return False

# === MAIN ===
try:
    join_meeting()

    while True:
        recovered = handle_reconnect() or handle_disconnect()
        if recovered:
            time.sleep(3)
        time.sleep(8)

except KeyboardInterrupt:
    print("🛑 Stopped by user.")
    driver.quit()
