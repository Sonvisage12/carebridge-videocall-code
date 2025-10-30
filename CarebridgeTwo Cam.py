# ============================================================
# CareBridge Raspberry Pi Control Panel (Dual-Camera Jitsi)
# Buttons:
#   GPIO 5  → Send SMS
#   GPIO 6  → Make Call
#   GPIO 13 → Join TWO Jitsi meetings (each on a separate camera)
#   GPIO 19 → Pick Call / End Meetings
# ============================================================

import RPi.GPIO as GPIO
import time, serial, os, threading
from shutil import which
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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

# Adjust serial if needed (/dev/ttyAMA0 for Pi 3 / 5)
ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)

# ----------------------------------------------------------------------
# 📱 SIM800L HELPERS
# ----------------------------------------------------------------------
def send_at(cmd, delay=1):
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    resp = ser.read_all().decode(errors="ignore")
    print(f">>> {cmd}\n{resp.strip()}\n")
    return resp

def modem_init():
    for c in ["AT","ATE0","AT+CMEE=2","AT+CSQ","AT+CREG?","AT+CLVL=90","AT+CMIC=0,15","AT+CHFA=0"]:
        send_at(c,0.5)

def send_sms():
    modem_init()
    num="+2348143042627"
    msg="Hello from Raspberry Pi!"
    send_at("AT+CMGF=1")
    send_at('AT+CSCS="GSM"')
    ser.write((f'AT+CMGS="{num}"\r').encode()); time.sleep(1)
    ser.write((msg+"\x1A").encode()); time.sleep(4)
    print("✅ SMS sent\n")

def make_call():
    modem_init(); num="+2348143042627"
    send_at(f"ATD{num};",3)
    try:
        while True:
            line=ser.readline().decode(errors="ignore").strip()
            if line:
                print(line)
                if "NO CARRIER" in line: break
            time.sleep(0.2)
    except KeyboardInterrupt:
        send_at("ATH")
    print("✅ Call done\n")

def listen_for_calls():
    print("👂 Listening for incoming calls …")
    while True:
        try:
            line=ser.readline().decode(errors="ignore").strip()
            if not line: continue
            if "RING" in line:
                print("📲 Incoming call! Press GPIO 19 to answer.")
                while GPIO.input(PIN_EXIT)==GPIO.HIGH: time.sleep(0.1)
                send_at("ATA",1)
                while True:
                    resp=ser.readline().decode(errors="ignore").strip()
                    if resp:
                        print(resp)
                        if "NO CARRIER" in resp: break
        except Exception as e:
            print("⚠️ Call listener error:",e); time.sleep(1)

# ----------------------------------------------------------------------
# 🎥 JITSI MEETING HANDLER
# ----------------------------------------------------------------------
def join_meeting_instance(meeting_url, camera, name):
    """Launch Chromium, select specific camera via WebRTC, join Jitsi, wait for Exit."""
    print(f"🌐 Launching {meeting_url} on {camera}")
    os.environ["SELENIUM_MANAGER_DISABLE"]="1"

    opts=Options()
    opts.binary_location="/usr/bin/chromium-browser"
    for a in [
        "--start-fullscreen","--disable-infobars","--disable-extensions",
        "--noerrdialogs","--autoplay-policy=no-user-gesture-required",
        "--use-fake-ui-for-media-stream","--alsa-output-device=default",
        "--enable-webrtc-pipewire-capturer","--no-sandbox"
    ]: opts.add_argument(a)
    opts.add_experimental_option("excludeSwitches",["enable-automation"])
    opts.add_experimental_option("useAutomationExtension",False)

    driver=webdriver.Chrome(service=Service(which("chromedriver") or "/usr/bin/chromedriver"),options=opts)
    driver.get(meeting_url)
    print("✅ Page loaded")

    time.sleep(8)

    # --- Force specific camera via WebRTC API and mute mic/cam ---
    try:
        js=f"""
        async function pickCam() {{
          const devs=await navigator.mediaDevices.enumerateDevices();
          const cams=devs.filter(d=>d.kind==='videoinput');
          console.log('🎥 Available cams:',cams.map(c=>c.label));
          let target=cams.find(c=>c.label.includes('{camera}'))||cams[0];
          if(target){{
            const stream=await navigator.mediaDevices.getUserMedia({{video:{{deviceId:{{exact:target.deviceId}}}},audio:false}});
            window._chosenCam=target.label;
            // Mute mic/cam to avoid feedback
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
        print("⚠️ JS camera select failed:",e)

    # --- Enter name ---
    try:
        for sel in [
            "//input[contains(@placeholder,'name')]",
            "//input[@aria-label='Your name']",
            "//input[@name='userName']"
        ]:
            try:
                box=WebDriverWait(driver,5).until(EC.presence_of_element_located((By.XPATH,sel)))
                box.clear(); box.send_keys(name)
                print(f"✏️ Name entered: {name}")
                break
            except TimeoutException: continue
    except Exception as e: print("⚠️ Name entry error:",e)

    # --- Click Join ---
    for sel in [
        "//button[normalize-space()='Join']",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'join meeting')]",
        "button[data-testid='prejoin.joinMeeting']",
        "//div[@role='button' and contains(.,'Join')]"
    ]:
        try:
            btn=driver.find_element(By.XPATH,sel)
            driver.execute_script("arguments[0].scrollIntoView(true);",btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();",btn)
            print(f"🟢 Clicked Join button [{name}]")
            break
        except Exception: pass

    print(f"🔴 Press GPIO 19 to leave meeting [{name}] …")
    try:
        while GPIO.input(PIN_EXIT)==GPIO.HIGH: time.sleep(0.2)
    finally:
        print(f"🛑 Closing meeting [{name}] ({camera})")
        driver.quit()

def join_two_meetings():
    """Launch two Jitsi sessions in parallel (one per camera)."""
    url1="https://meet.jit.si/FollowingWavesSupposeAcross"
    url2="https://meet.jit.si/FollowingWavesSupposeAcross"
    print("🎥 Starting dual Jitsi sessions …")

    t1=threading.Thread(target=join_meeting_instance,args=(url1,"/dev/video0","CareBridge Cam 1"),daemon=True)
    t2=threading.Thread(target=join_meeting_instance,args=(url2,"/dev/video2","CareBridge Cam 2"),daemon=True)
    t1.start(); t2.start()
    print("✅ Both Jitsi instances launched.")
    t1.join(); t2.join()
    print("✅ Meetings ended.\n")

# ----------------------------------------------------------------------
# 🕹️ MAIN LOOP
# ----------------------------------------------------------------------
print("🚀 Ready — Buttons:")
print("  • GPIO 5 → Send SMS")
print("  • GPIO 6 → Make Call")
print("  • GPIO 13 → Join TWO Jitsi meetings (dual camera)")
print("  • GPIO 19 → Pick Call / End Meetings\n")

threading.Thread(target=listen_for_calls,daemon=True).start()

try:
    while True:
        if GPIO.input(PIN_SMS)==GPIO.LOW:
            print("\n📩 Button 5 → Send SMS"); send_sms(); time.sleep(1)
        elif GPIO.input(PIN_CALL)==GPIO.LOW:
            print("\n📞 Button 6 → Make Call"); make_call(); time.sleep(1)
        elif GPIO.input(PIN_CONF)==GPIO.LOW:
            print("\n🎥 Button 13 → Join dual meetings"); join_two_meetings(); time.sleep(1)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n🛑 Exiting program.")
finally:
    GPIO.cleanup(); ser.close(); print("✅ GPIO and serial closed.")
