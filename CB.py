# ============================================================
# CareBridge Raspberry Pi Control Panel (Dual Jitsi Version — Full)
# Buttons:
#   GPIO 5  → Send SMS
#   GPIO 6  → Make Call
#   GPIO 13 → Join TWO Jitsi Meetings (each on separate camera)
#   GPIO 19 → Pick Incoming Call / End Meetings
# ============================================================

import RPi.GPIO as GPIO
import time, serial, os, threading
from shutil import which
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ----------------------------------------------------------------------
# ⚙️ GPIO & MODEM SETUP
# ----------------------------------------------------------------------
PIN_SMS   = 5
PIN_CALL  = 6
PIN_CONF  = 13
PIN_EXIT  = 19

GPIO.setmode(GPIO.BCM)
for pin in [PIN_SMS, PIN_CALL, PIN_CONF, PIN_EXIT]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)

# ----------------------------------------------------------------------
# 📱 MODEM / SMS / CALL FUNCTIONS
# ----------------------------------------------------------------------
def send_at(cmd, delay=1):
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    resp = ser.read_all().decode(errors='ignore')
    print(f">>> {cmd}\n{resp.strip()}\n")
    return resp

def modem_init():
    print("📡 Initialising SIM800L modem …")
    for c in ["AT", "ATE0", "AT+CMEE=2", "AT+CSQ",
              "AT+CREG?", "AT+CLVL=90", "AT+CMIC=0,15", "AT+CHFA=0"]:
        send_at(c, 0.5)

def send_sms():
    modem_init()
    number = "+2348143042627"
    msg = "Hello from Raspberry Pi!"
    print("📤 Sending SMS …")
    send_at("AT+CMGF=1")
    send_at('AT+CSCS="GSM"')
    ser.write((f'AT+CMGS="{number}"\r').encode())
    time.sleep(1)
    ser.write((msg + "\x1A").encode())
    time.sleep(4)
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

def listen_for_calls():
    print("👂 Listening for incoming calls …")
    while True:
        try:
            line = ser.readline().decode(errors='ignore').strip()
            if not line:
                continue
            if "RING" in line:
                print("\n📲 Incoming call detected! Press GPIO 19 to answer.")
                while True:
                    if GPIO.input(PIN_EXIT) == GPIO.LOW:
                        print("✅ Answering call …")
                        send_at("ATA", 1)
                        break
                    time.sleep(0.1)
                while True:
                    resp = ser.readline().decode(errors='ignore').strip()
                    if resp:
                        print(resp)
                        if "NO CARRIER" in resp:
                            print("📴 Call ended.")
                            break
            time.sleep(0.1)
        except Exception as e:
            print(f"⚠️ Call listener error: {e}")
            time.sleep(1)

# ----------------------------------------------------------------------
# 🎥 JITSI MEETING HANDLERS
# ----------------------------------------------------------------------
def join_meeting_instance(meeting_url, camera, name):
    """Launch Chromium, join Jitsi, and stay until Exit is pressed."""
    print(f"🌐 Launching Jitsi: {meeting_url}  with camera {camera}")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    chrome_options.add_argument("--start-fullscreen")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--noerrdialogs")
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--use-fake-ui-for-media-stream")
    chrome_options.add_argument("--alsa-output-device=default")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument(f"--video-input-device={camera}")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    chromedriver_path = which("chromedriver") or "/usr/bin/chromedriver"
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
    driver.get(meeting_url)
    print(f"✅ Page loaded: {meeting_url}")

    # Wait for pre-join UI to appear
    time.sleep(8)

    # Switch into iframe if needed
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        if frames:
            driver.switch_to.frame(frames[0])
            print(f"🧭 Switched into iframe (found {len(frames)})")
    except Exception as e:
        print(f"⚠️ Frame switch error: {e}")

    # --- Enter display name ---
    try:
        name_box = None
        for selector in [
            "//input[contains(@placeholder,'name')]",
            "//input[@aria-label='Your name']",
            "//input[@name='userName']"
        ]:
            try:
                name_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if name_box:
                    name_box.clear()
                    name_box.send_keys(name)
                    print(f"✏️ Entered display name: {name}")
                    break
            except TimeoutException:
                continue
    except Exception as e:
        print(f"⚠️ Name entry error: {e}")

    # --- Click Join button ---
    join_selectors = [
        "//button[normalize-space()='Join']",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join meeting')]",
        "button[data-testid='prejoin.joinMeeting']",
        "//button[contains(.,'Join')]",
        "//div[@role='button' and contains(.,'Join')]"
    ]
    joined = False
    for sel in join_selectors:
        try:
            btn = driver.find_element(By.XPATH, sel)
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", btn)
            print(f"🟢 Clicked Join using selector: {sel}")
            joined = True
            break
        except Exception:
            continue
    if not joined:
        print("⚠️ Join button not found — meeting may auto-join or require manual click.")

    # --- Stay in meeting until Exit pressed ---
    print(f"🔴 Press Exit (GPIO 19) to leave meeting [{name}] …")
    try:
        while GPIO.input(PIN_EXIT) == GPIO.HIGH:
            time.sleep(0.2)
    finally:
        print(f"🛑 Closing meeting for {name} ({camera}) …")
        driver.quit()

def join_two_meetings():
    """Start two Jitsi sessions in parallel, one per camera."""
    url1 = "https://meet.jit.si/FollowingWavesSupposeAcross"
    url2 = "https://meet.jit.si/FollowingWavesSupposeAcross"
    print("🎥 Starting dual Jitsi sessions …")

    t1 = threading.Thread(
        target=join_meeting_instance, args=(url1, "/dev/video0", "CareBridge Cam 1"), daemon=True
    )
    t2 = threading.Thread(
        target=join_meeting_instance, args=(url2, "/dev/video2", "CareBridge Cam 2"), daemon=True
    )

    t1.start()
    t2.start()

    print("✅ Both Jitsi instances launched.")
    print("🔴 Press Exit (GPIO 19) to close browsers.")
    t1.join()
    t2.join()
    print("✅ Meetings ended, returning to main loop.\n")

# ----------------------------------------------------------------------
# 🕹️ MAIN LOOP
# ----------------------------------------------------------------------
print("🚀 Ready. Press:")
print("  • GPIO 5 → Send SMS")
print("  • GPIO 6 → Make Call")
print("  • GPIO 13 → Join TWO Jitsi meetings (dual camera)")
print("  • GPIO 19 → Pick Call / End Meetings")
print("Press Ctrl + C to exit program.\n")

threading.Thread(target=listen_for_calls, daemon=True).start()

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
            print("\n🎥 Button 13 pressed — join dual meetings")
            join_two_meetings()
            time.sleep(1)

        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n🛑 Exiting program.")
finally:
    GPIO.cleanup()
    ser.close()
    print("✅ GPIO and serial closed cleanly.")
