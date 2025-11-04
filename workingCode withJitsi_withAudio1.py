# ============================================================
# CareBridge Raspberry Pi Control Panel
# Buttons:
#   GPIO 5  → Send SMS
#   GPIO 6  → Make Call
#   GPIO 13 → Join Jitsi Meeting
#   GPIO 19 → End Meeting / Return to Main Menu
# ============================================================

import RPi.GPIO as GPIO
import time, serial, sys, termios, tty, select, os
from shutil import which
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----------------------------------------------------------------------
# ⚙️ GPIO & MODEM SETUP
# ----------------------------------------------------------------------
PIN_SMS   = 5
PIN_CALL  = 6
PIN_CONF  = 13
PIN_EXIT  = 19   # 🆕 new Exit button

GPIO.setmode(GPIO.BCM)
for pin in [PIN_SMS, PIN_CALL, PIN_CONF, PIN_EXIT]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# SIM800L serial interface
ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)

def send_at(cmd, delay=1):
    """Send an AT command to the modem and print the response."""
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    resp = ser.read_all().decode(errors='ignore')
    print(f">>> {cmd}\n{resp.strip()}\n")
    return resp

def modem_init():
    """Initialise SIM800L with common settings."""
    print("📡 Initialising SIM800L modem …")
    for c in ["AT", "ATE0", "AT+CMEE=2", "AT+CSQ",
              "AT+CREG?", "AT+CLVL=90", "AT+CMIC=0,15", "AT+CHFA=0"]:
        send_at(c, 0.5)

# ----------------------------------------------------------------------
# 📱 SMS & CALL FUNCTIONS
# ----------------------------------------------------------------------
def send_sms():
    modem_init()
    number = "+2348143042627"
    msg = "Hello from Raspberry Pi button!"
    print("📤 Sending SMS …")
    send_at("AT+CMGF=1")
    send_at('AT+CSCS="GSM"')
    ser.write((f'AT+CMGS="{number}"\r').encode())
    time.sleep(1)
    ser.write((msg + "\x1A").encode())   # CTRL-Z terminator
    time.sleep(5)
    print(ser.read_all().decode(errors='ignore'))
    print("✅ SMS sent\n")

def make_call():
    modem_init()
    number = "+2348143042627"
    print(f"📞 Dialling {number} …")
    send_at(f"ATD{number};", 3)
    try:
        while True:
            line = ser.readline().decode(errors='ignore').strip()
            if line:
                print(line)
                if "NO CARRIER" in line:
                    print("📴 Call ended")
                    break
            time.sleep(0.2)
    except KeyboardInterrupt:
        send_at("ATH")
    print("✅ Call done\n")

# ----------------------------------------------------------------------
# 🎥 JITSI MEET JOIN LOGIC
# ----------------------------------------------------------------------
def safe_find(driver, by, selector, timeout=5):
    """Return element if found within timeout, else None."""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None

def dismiss_auth_or_recover_modal(driver):
    """Close 'Recover Password' or similar dialogs if present."""
    try:
        modal = None
        try:
            modal = driver.find_element(By.XPATH,
                "//*[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'recover password')]")
        except NoSuchElementException:
            try:
                modal = driver.find_element(By.XPATH,
                    "//*[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'reset your password')]")
            except NoSuchElementException:
                pass
        if modal:
            print("⚠️ Auth modal found — closing …")
            for txt in ["cancel", "close"]:
                try:
                    b = modal.find_element(
                        By.XPATH, f".//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{txt}')]"
                    )
                    driver.execute_script("arguments[0].click();", b)
                    print(f"✅ Clicked '{txt}'")
                    return
                except Exception:
                    pass
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception as e:
        print(f"⚠️ Modal dismiss error: {e}")

def join_meeting(meeting_url="https://meet.jit.si/FollowingWavesSupposeAcross"):
    """Launch Chromium and join a Jitsi meeting; exit via GPIO 19."""
    print("🌐 Launching Jitsi Meet …")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"
    os.system("amixer -c 1 sset 'Speaker' 100% unmute")

    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    chrome_options.add_argument("--kiosk")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--noerrdialogs")
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--use-fake-ui-for-media-stream")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    chromedriver_path = which("chromedriver") or "/usr/bin/chromedriver"
    print(f"🧭 Using Chromedriver: {chromedriver_path}")

    driver = webdriver.Chrome(service=Service(chromedriver_path),
                              options=chrome_options)
    driver.get(meeting_url)
    print("✅ Chromium opened — waiting for UI …")
    time.sleep(6)
    dismiss_auth_or_recover_modal(driver)

    # Try iframe switch (if present)
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        if frames:
            driver.switch_to.frame(frames[0])
            print(f"🧭 Switched into iframe (count={len(frames)})")
    except Exception as e:
        print(f"⚠️ Frame switch error: {e}")

    dismiss_auth_or_recover_modal(driver)

    # --- Enter display name ---
    try:
        name_box = safe_find(
            driver, By.XPATH,
            "//input[contains(@placeholder,'name') or @aria-label='Your name' or @name='userName']",
            timeout=5)
        if name_box:
            name_box.clear()
            name_box.send_keys("CareBridge")
            print("✏️ Entered name CareBridge")
    except Exception as e:
        print(f"⚠️ Name entry error: {e}")

    # --- Click Join button if found ---
    join_btn = None
    selectors = [
        "//button[normalize-space(text())='Join']",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join')]",
        "button[data-testid='prejoin.joinMeeting']",
        "button[aria-label*='Join']",
        "button[class*='join']",
        "div[role='button'][class*='join']",
        "div[role='button'][aria-label*='Join']",
    ]
    for sel in selectors:
        try:
            join_btn = (driver.find_element(By.XPATH, sel)
                        if sel.startswith("//")
                        else driver.find_element(By.CSS_SELECTOR, sel))
            print(f"🔍 Found Join selector: {sel}")
            break
        except NoSuchElementException:
            continue
    if join_btn:
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", join_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", join_btn)
            print("🟢 Joined meeting successfully.")
        except Exception as e:
            print(f"⚠️ Join click failed: {e}")
    else:
        print("⚠️ Join button not found — listing buttons:")
        for b in driver.find_elements(By.TAG_NAME, "button"):
            print(" ▶", b.text.strip())

    # --- Wait until Exit button (GPIO 19) is pressed ---
    print("🔴 Press Exit button (GPIO 19) to end meeting.")
    try:
        while True:
            if GPIO.input(PIN_EXIT) == GPIO.LOW:
                print("🛑 Exit button pressed — closing meeting …")
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        driver.quit()
        print("✅ Browser closed — returning to main menu.\n")

# ----------------------------------------------------------------------
# 🕹️ MAIN BUTTON LOOP
# ----------------------------------------------------------------------
print("🚀 Ready. Press:")
print("  • GPIO 5 → Send SMS")
print("  • GPIO 6 → Make Call")
print("  • GPIO 13 → Start Conference")
print("  • GPIO 19 → End Meeting (if active)")
print("Press Ctrl + C to exit program.\n")

try:
    while True:
        if GPIO.input(PIN_SMS) == GPIO.LOW:
            print("\n📩 Button 5 pressed — send SMS")
            send_sms()
            time.sleep(1)
        elif GPIO.input(PIN_CALL) == GPIO.LOW:
            print("\n📞 Button 6 pressed — make call")
            make_call()
            time.sleep(1)
        elif GPIO.input(PIN_CONF) == GPIO.LOW:
            print("\n🎥 Button 13 pressed — join conference")
            join_meeting()
            time.sleep(1)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n🛑 Exiting program.")
finally:
    GPIO.cleanup()
    ser.close()
    print("✅ GPIO and serial closed cleanly.")
