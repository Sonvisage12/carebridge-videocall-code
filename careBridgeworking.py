# ============================================================
# CareBridge Raspberry Pi Control Panel (Voice + MP3 Ringtone)
# Buttons:
#   GPIO 5  → Send SMS
#   GPIO 6  → Make Call
#   GPIO 13 → Join Jitsi Meeting
#   GPIO 19 → End Call / End Meeting
#   GPIO 26 → Answer Incoming Call
# ============================================================

import RPi.GPIO as GPIO
import time, serial, os, threading, re, subprocess
from shutil import which
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----------------------------------------------------------------------
# ⚙️ GPIO & MODEM SETUP
# ----------------------------------------------------------------------
PIN_SMS    = 5
PIN_CALL   = 6
PIN_CONF   = 13
PIN_EXIT   = 19
PIN_ANSWER = 26   # dedicated Answer Incoming Call button

GPIO.setmode(GPIO.BCM)
for pin in [PIN_SMS, PIN_CALL, PIN_CONF, PIN_EXIT, PIN_ANSWER]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# SIM800L serial interface
ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)
active_call = False

# ----------------------------------------------------------------------
# 🗣️ VOICE FEEDBACK FUNCTION
# ----------------------------------------------------------------------
def speak(message):
    """Speak text aloud using espeak."""
    print(f"🔊 {message}")
    os.system(f"espeak -ven+f3 -s150 '{message}' >/dev/null 2>&1")

# ----------------------------------------------------------------------
# 🔔 RINGTONE CONTROL
# ----------------------------------------------------------------------
def play_ringtone():
    """Play ringtone MP3 in loop until stopped."""
    try:
        return subprocess.Popen(
            ["mpg123", "-q", "--loop", "-1", "/home/pi/ringtone.mp3"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        speak("Ringtone file not found")
        return None

def stop_ringtone(proc):
    """Stop ringtone playback."""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()

# ----------------------------------------------------------------------
# 📡 MODEM UTILITIES
# ----------------------------------------------------------------------
def send_at(cmd, delay=1):
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    resp = ser.read_all().decode(errors='ignore')
    print(f">>> {cmd}\n{resp.strip()}\n")
    return resp

def modem_init():
    print("📡 Initialising SIM800L modem …")
    speak("Initializing modem")
    for c in ["AT", "ATE0", "AT+CMEE=2", "AT+CSQ", "AT+CREG?",
              "AT+CLIP=1", "AT+CLVL=100", "AT+CMIC=0,15", "AT+CHFA=0"]:
        send_at(c, 0.5)

# ----------------------------------------------------------------------
# 📱 SMS FUNCTION
# ----------------------------------------------------------------------
def send_sms():
    modem_init()
    number = "+2348143042627"
    msg = "Hello from Raspberry Pi button!"
    speak("Sending message")
    print("📤 Sending SMS …")
    send_at("AT+CMGF=1")
    send_at('AT+CSCS="GSM"')
    ser.write((f'AT+CMGS="{number}"\r').encode())
    time.sleep(1)
    ser.write((msg + "\x1A").encode())
    time.sleep(5)
    print(ser.read_all().decode(errors='ignore'))
    print("✅ SMS sent\n")
    speak("Message sent")

# ----------------------------------------------------------------------
# 📞 CALL MANAGEMENT
# ----------------------------------------------------------------------
def handle_active_call():
    """Monitor ongoing call; end on GPIO 19 press."""
    global active_call
    speak("Call in progress")
    print("🔊 Call active — press GPIO 19 to hang up.")
    try:
        while active_call:
            if ser.in_waiting:
                line = ser.readline().decode(errors='ignore').strip()
                if line:
                    print(line)
                    if any(k in line for k in ["NO CARRIER", "BUSY", "ERROR"]):
                        print("📴 Call ended by remote or network.")
                        speak("Call ended")
                        active_call = False
                        break
            if GPIO.input(PIN_EXIT) == GPIO.LOW:
                print("🛑 End button pressed — hanging up call …")
                speak("Ending call")
                send_at("ATH", 1)
                active_call = False
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        send_at("ATH")
    finally:
        active_call = False
        print("✅ Call finished.\n")
        speak("Call finished")

def monitor_incoming_calls():
    """Monitor SIM800L for incoming calls, play ringtone, allow GPIO 26 to answer."""
    global active_call
    print("👂 Listening for incoming calls …")
    ringtone_proc = None
    try:
        while True:
            if ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                # Detect incoming call
                if "RING" in line:
                    print("📲 Incoming call ringing …")
                    speak("Incoming call")
                    if ringtone_proc is None or ringtone_proc.poll() is not None:
                        ringtone_proc = play_ringtone()

                # Detect caller ID
                elif "+CLIP:" in line:
                    match = re.search(r'\+CLIP:\s*\"(\+?\d+)\"', line)
                    if match:
                        caller = match.group(1)
                        print(f"📞 Caller number: {caller}")
                        spoken_number = " ".join(list(caller))
                        speak(f"Incoming call from {spoken_number}")

                # Wait for answer / reject
                if "RING" in line or "+CLIP:" in line:
                    print("👉 Press GPIO 26 to answer, or GPIO 19 to reject.")
                    while True:
                        if GPIO.input(PIN_ANSWER) == GPIO.LOW:
                            stop_ringtone(ringtone_proc)
                            ringtone_proc = None
                            print("✅ Answering call …")
                            speak("Answering call")
                            send_at("ATA", 1)
                            active_call = True
                            handle_active_call()
                            break
                        elif GPIO.input(PIN_EXIT) == GPIO.LOW:
                            stop_ringtone(ringtone_proc)
                            ringtone_proc = None
                            print("❌ Call rejected.")
                            speak("Call rejected")
                            send_at("ATH", 1)
                            break
                        time.sleep(0.1)
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_ringtone(ringtone_proc)

def make_call():
    """Place an outgoing call."""
    global active_call
    modem_init()
    number = "+2348143042627"
    speak("Dialing number")
    print(f"📞 Dialling {number} …")
    send_at(f"ATD{number};", 3)
    active_call = True
    handle_active_call()

# ----------------------------------------------------------------------
# 🎥 JITSI MEETING JOIN (WORKING VERSION)
# ----------------------------------------------------------------------
def join_meeting_instance(meeting_url, camera, name):
    """Launch Chromium, select specific camera via WebRTC, join Jitsi, wait for Exit."""
    print(f"🌐 Launching {meeting_url} on {camera}")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

    opts = Options()
    opts.binary_location = "/usr/bin/chromium-browser"
    for a in [
        "--start-fullscreen", "--disable-infobars", "--disable-extensions",
        "--noerrdialogs", "--autoplay-policy=no-user-gesture-required",
        "--use-fake-ui-for-media-stream", "--alsa-output-device=default",
        "--enable-webrtc-pipewire-capturer", "--no-sandbox"
    ]:
        opts.add_argument(a)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(which("chromedriver") or "/usr/bin/chromedriver"), options=opts)
    driver.get(meeting_url)
    print("✅ Page loaded")

    time.sleep(8)

    # --- Force specific camera via WebRTC API and mute mic/cam ---
    try:
        js = f"""
        async function pickCam() {{
          const devs=await navigator.mediaDevices.enumerateDevices();
          const cams=devs.filter(d=>d.kind==='videoinput');
          console.log('🎥 Available cams:',cams.map(c=>c.label));
          let target=cams.find(c=>c.label.includes('{camera}'))||cams[0];
          if(target){{
            const stream=await navigator.mediaDevices.getUserMedia({{video:{{deviceId:{{exact:target.deviceId}}}},audio:false}});
            window._chosenCam=target.label;
            const tracks=stream.getVideoTracks();
            tracks.forEach(t=>t.enabled=false);
            console.log('✅ Using camera '+target.label);
          }}else console.log('⚠️ No match for {camera}');
        }}
        pickCam();
        """
        driver.execute_script(js)
        print(f"🎥 Camera selection script injected for {camera}")
    except Exception as e:
        print("⚠️ JS camera select failed:", e)

    # --- Enter name ---
    try:
        for sel in [
            "//input[contains(@placeholder,'name')]",
            "//input[@aria-label='Your name']",
            "//input[@name='userName']"
        ]:
            try:
                box = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, sel)))
                box.clear()
                box.send_keys(name)
                print(f"✏️ Name entered: {name}")
                break
            except TimeoutException:
                continue
    except Exception as e:
        print("⚠️ Name entry error:", e)

    # --- Click Join ---
    for sel in [
        "//button[normalize-space()='Join']",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join meeting')]",
        "button[data-testid='prejoin.joinMeeting']",
        "//div[@role='button' and contains(.,'Join')]"
    ]:
        try:
            btn = driver.find_element(By.XPATH, sel)
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", btn)
            print(f"🟢 Clicked Join button [{name}]")
            break
        except Exception:
            pass

    print(f"🔴 Press GPIO 19 to leave meeting [{name}] …")
    try:
        while GPIO.input(PIN_EXIT) == GPIO.HIGH:
            time.sleep(0.2)
    finally:
        print(f"🛑 Closing meeting [{name}] ({camera})")
        driver.quit()

def join_meeting():
    """Wrapper to start single Jitsi meeting."""
    url = "https://meet.jit.si/FollowingWavesSupposeAcross"
    camera = "/dev/video0"
    name = "CareBridge"
    join_meeting_instance(url, camera, name)

# ----------------------------------------------------------------------
# 🕹️ MAIN LOOP
# ----------------------------------------------------------------------
print("🚀 Ready. Press:")
print("  • GPIO 5 → Send SMS")
print("  • GPIO 6 → Make Call")
print("  • GPIO 26 → Answer Incoming Call")
print("  • GPIO 13 → Join Conference")
print("  • GPIO 19 → End Call / End Meeting")
print("Press Ctrl + C to exit.\n")
speak("System ready")

# ✅ Start background incoming call monitor
threading.Thread(target=monitor_incoming_calls, daemon=True).start()

try:
    while True:
        if GPIO.input(PIN_SMS) == GPIO.LOW:
            print("\n📩 Button 5 pressed — send SMS")
            send_sms()
            time.sleep(1)
        elif GPIO.input(PIN_CALL) == GPIO.LOW:
            print("\n📞 Button 6 pressed — make outgoing call")
            make_call()
            time.sleep(1)
        elif GPIO.input(PIN_CONF) == GPIO.LOW:
            print("\n🎥 Button 13 pressed — join conference")
            join_meeting()
            time.sleep(1)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n🛑 Exiting program.")
    speak("Shutting down system")
finally:
    GPIO.cleanup()
    ser.close()
    print("✅ GPIO and serial closed cleanly.")
    speak("System stopped")
