from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

WEBEX_URL = "https://meet1492.webex.com/meet/pr23680413308"

chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium-browser"
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--start-maximized")
# Uncomment if using without GUI
# chrome_options.add_argument("--headless=new")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)

def list_elements_recursively(driver, depth=0):
    """Recursively print buttons and inputs in all iframes."""
    prefix = "  " * depth
    try:
        inputs = driver.find_elements(By.TAG_NAME, "input")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        print(f"{prefix}🧭 Depth {depth}: Found {len(inputs)} input(s), {len(buttons)} button(s)")

        for el in inputs:
            try:
                print(f"{prefix}  🟦 INPUT → id='{el.get_attribute('id')}', "
                      f"name='{el.get_attribute('name')}', "
                      f"placeholder='{el.get_attribute('placeholder')}', "
                      f"aria-label='{el.get_attribute('aria-label')}'")
            except Exception:
                pass

        for el in buttons:
            try:
                text = el.text.strip()
                print(f"{prefix}  🟩 BUTTON → text='{text}', id='{el.get_attribute('id')}', "
                      f"class='{el.get_attribute('class')}'")
            except Exception:
                pass

        frames = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"{prefix}🔍 Found {len(frames)} iframe(s) at this level")
        for idx, frame in enumerate(frames):
            try:
                driver.switch_to.frame(frame)
                print(f"{prefix}➡️ Entering iframe {idx+1}/{len(frames)}")
                list_elements_recursively(driver, depth + 1)
                driver.switch_to.parent_frame()
            except Exception as e:
                print(f"{prefix}⚠️ Error switching to iframe {idx+1}: {e}")
                try:
                    driver.switch_to.parent_frame()
                except Exception:
                    pass
                continue
    except Exception as e:
        print(f"{prefix}⚠️ Error at depth {depth}: {e}")

print("🌐 Opening Webex meeting page...")
driver.get(WEBEX_URL)
time.sleep(10)  # wait for everything to load

print("\n=== STARTING FIELD & BUTTON SCAN ===")
driver.switch_to.default_content()
list_elements_recursively(driver)

print("\n✅ Scan complete. Browser will stay open for inspection.")
time.sleep(600)
driver.quit()
