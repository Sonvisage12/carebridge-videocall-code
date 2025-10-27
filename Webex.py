import RPi.GPIO as GPIO
import time, serial, sys, termios, tty, select, os
from shutil import which
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

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
# 🎥 WEBEX JOIN FUNCTION
# ----------------------------------------------------------------------
def join_webex(meeting_url="https://meet1492.webex.com/meet/pr23680413308"):
    print("🌐 Launching Webex Meeting…")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    chrome_options.add_argument("--kiosk")  # fullscreen
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--noerrdialogs")
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--use-fake-ui-for-media-stream")  # auto allow mic/cam
    chrome_options.add_argument("--enable-features=UseOzonePlatform")
    chrome_options.add_argument("--ozone-platform=wayland")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    chromedriver_path = which("chromedriver") or "/usr/bin/chromedriver"
    print(f"🧭 Using Chromedriver at: {chromedriver_path}")

    driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
    driver.get(meeting_url)
    print("✅ Chromium opened — waiting for Webex pre-join screen…")

    try:
        # Wait for name input or Join button to appear
        WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.XPATH, "//input[contains(@placeholder,'name') or contains(@aria-label,'name')]") or
                      d.find_elements(By.XPATH, "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join')]")
        )

        # Enter name if prompted
        try:
            name_box = driver.find_element(By.XPATH, "//input[contains(@placeholder,'name') or contains(@aria-label,'name')]")
            name_box.clear()
            name_box.send_keys("CareBridge")
            print("✏️ Entered name: CareBridge")
        except NoSuchElementException:
            print("ℹ️ No name field found (maybe saved or skipped).")

        time.sleep(2)

        # Try to click the Join Meeting button
        join_btn = None
        selectors = [
            "//button[normalize-space(text())='Join meeting']",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join')]",
            "//button[contains(@class,'join')]",
            "//button[contains(@data-dojo-attach-point,'joinButton')]"
        ]
        for sel in selectors:
            try:
                join_btn = driver.find_element(By.XPATH, sel)
                break
            except NoSuchElementException:
                continue

        if join_btn:
            driver.execute_script("arguments[0].scrollIntoView(true);", join_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", join_btn)
            print("🟢 Clicked Join Meeting — waiting to connect…")
        else:
            print("⚠️ Join Meeting button not found — may already be joined.")

    except Exception as e:
        print(f"⚠️ Error during join: {e}")

    print("🔴 Press ESC to close browser.")

    # --- ESC key to exit ---
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
                print("🛑 ESC pressed — closing browser.")
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
print("  • GPIO 13 → Join Webex Meeting")
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
            print("\n🎥 Button 13 pressed — join Webex conference")
            join_webex()
            time.sleep(1)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n🛑 Exiting")
finally:
    GPIO.cleanup()
    ser.close()
