import RPi.GPIO as GPIO
import time
import serial
import sys
import termios
import tty
import select
import os
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
PIN_SMS  = 5
PIN_CALL = 6
PIN_CONF = 13

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_SMS,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PIN_CALL, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PIN_CONF, GPIO.IN, pull_up_down=GPIO.PUD_UP)

ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)

def send_at(cmd, delay=1):
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    resp = ser.read_all().decode(errors='ignore')
    print(f">>> {cmd}\n{resp.strip()}\n")
    return resp

def modem_init():
    print("📡 Initializing SIM800L...")
    for c in ["AT", "ATE0", "AT+CMEE=2", "AT+CSQ", "AT+CREG?", "AT+CLVL=90", "AT+CMIC=0,15", "AT+CHFA=0"]:
        send_at(c, 0.5)

# ----------------------------------------------------------------------
# 📱  SMS & CALL FUNCTIONS
# ----------------------------------------------------------------------
def send_sms():
    modem_init()
    number = "+2348143042627"
    msg = "Hello from Raspberry Pi button!"
    print("📤 Sending SMS…")
    send_at("AT+CMGF=1")
    send_at('AT+CSCS="GSM"')
    ser.write((f'AT+CMGS="{number}"\r').encode())
    time.sleep(1)
    ser.write((msg + "\x1A").encode())
    time.sleep(5)
    print(ser.read_all().decode(errors='ignore'))
    print("✅ SMS sent\n")

def make_call():
    modem_init()
    number = "+2348143042627"
    print(f"📞 Dialing {number}…")
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
# 🎥  JITSI MEET — FULLY ROBUST JOIN LOGIC
# ----------------------------------------------------------------------
def safe_find(driver, by, selector, timeout=5):
    """Return element if found within timeout, else None."""
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except TimeoutException:
        return None

def dismiss_auth_or_recover_modal(driver):
    """Dismisses 'Recover password' or similar modals if detected."""
    found = False
    try:
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
            print("⚠️ Detected password recovery/auth modal — dismissing...")

            for text in ["cancel", "close"]:
                try:
                    btn = modal_el.find_element(By.XPATH, f".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]")
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"✅ Clicked '{text}' in modal.")
                    return True
                except Exception:
                    pass

            # fallback: ESC
            try:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                print("✅ Pressed ESC to dismiss modal.")
                return True
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ Modal dismissal error: {e}")

    return found

def join_meeting(meeting_url="https://meet.jit.si/PremierFamiliesFundNevertheless"):
    print("🌐 Launching Jitsi Meet…")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

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
    print(f"🧭 Using Chromedriver at: {chromedriver_path}")

    driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
    driver.get(meeting_url)
    print("✅ Chromium opened — waiting for pre-join UI…")

    time.sleep(6)
    dismiss_auth_or_recover_modal(driver)

    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            driver.switch_to.frame(iframes[0])
            print(f"🧭 Switched into iframe (count={len(iframes)})")
    except Exception as e:
        print(f"⚠️ Frame switch error: {e}")

    dismiss_auth_or_recover_modal(driver)

    # --- enter display name ---
    try:
        name_box = safe_find(driver, By.XPATH, "//input[contains(@placeholder,'name') or @aria-label='Your name' or @name='userName']", timeout=5)
        if name_box:
            name_box.clear()
            name_box.send_keys("CareBridge")
            print("✏️ Entered name: CareBridge")
    except Exception as e:
        print(f"⚠️ Name entry error: {e}")

    time.sleep(1)

    # --- find and click 'Join' ---
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
            join_btn = driver.find_element(By.XPATH, sel) if sel.startswith("//") else driver.find_element(By.CSS_SELECTOR, sel)
            print(f"🔍 Found Join control with selector: {sel}")
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
            print(f"⚠️ Could not click join: {e}")
    else:
        print("⚠️ Join button not found — listing all visible buttons:")
        for b in driver.find_elements(By.TAG_NAME, "button"):
            print("  ▶", b.text.strip())

    print("🔴 Press ESC to exit browser.")

    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return None

    try:
        while True:
            if getch() == '\x1b':  # ESC
                print("🛑 ESC pressed — closing")
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        driver.quit()
        print("✅ Browser closed\n")

# ----------------------------------------------------------------------
# 🕹️ MAIN LOOP
# ----------------------------------------------------------------------
print("🚀 Ready. Press:")
print("  • GPIO 5 → Send SMS")
print("  • GPIO 6 → Make Call")
print("  • GPIO 13 → Start Conference")
print("Press Ctrl+C to exit\n")

try:
    while True:
        if GPIO.input(PIN_SMS) == GPIO.LOW:
            print("\n📩 Button 5 pressed — send SMS")
            send_sms()
            time.sleep(1)
        elif GPIO.input(PIN_CALL) == GPIO.LOW:
            print("\n📞 Button 6 pressed — call")
            make_call()
            time.sleep(1)
        elif GPIO.input(PIN_CONF) == GPIO.LOW:
            print("\n🎥 Button 13 pressed — join conference")
            join_meeting()
            time.sleep(1)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n🛑 Exiting")
finally:
    GPIO.cleanup()
    ser.close()
