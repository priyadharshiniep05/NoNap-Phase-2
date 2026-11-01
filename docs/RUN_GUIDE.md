# NoNap — Run Guide

This guide covers every step from a blank SD card to a full demo:

- **Raspberry Pi 1 + Pi Camera** in the car, plugged in by **Ethernet**
- the **MacBook** running the detection backend
- the **iPhone 16 Pro** running the app

Follow the steps in order. Each command is meant to be copied exactly.

> **Throughout this guide:**
> - **"On the Mac"** means in Terminal, inside the project folder (`cd ~/Desktop/"Nonap Phase 2"`).
> - **"On the Pi"** means in an SSH session to the Pi (step 2.4).

---

## 1. Prepare the SD card and the Pi

You need a 16 GB microSD card, a card reader, and the Pi Camera ribbon cable.

### 1.1 Flash the card
1. Install **Raspberry Pi Imager** on the Mac from <https://www.raspberrypi.com/software/>.
2. Open it and choose:
   - **Device:** Raspberry Pi 1
   - **OS:** *Raspberry Pi OS (other)* → **Raspberry Pi OS (Legacy, 32-bit) Lite**. Pick the **Bullseye**-based legacy image. It still has the legacy camera stack (`raspistill`, `picamera`).
   - **Storage:** your SD card
3. Click **Next** → **Edit settings**, then:
   - **General:**
     - hostname `nonap-pi`
     - username `pi`
     - choose a password
     - set the locale/time zone to `Asia/Kolkata`
   - **Services:** turn on **Enable SSH** (password authentication).
   - Leave Wi-Fi empty. The Pi 1 has no Wi-Fi.
4. Write the card, then put it in the Pi.

### 1.2 Connect the camera (Pi switched off)
1. Lift the black clip of the CSI connector, between the HDMI and Ethernet ports.
2. Insert the ribbon with the **blue side facing the Ethernet port**.
3. Press the clip down.

### 1.3 Speaker
Plug a small speaker or earphones into the **3.5 mm jack**. There is no buzzer and nothing goes on the GPIO pins.

---

## 2. Connect the Pi by Ethernet and find its IP

Choose **A** or **B**.

**A. Pi into your router** (simplest, when the Mac and iPhone use the same router's Wi-Fi)
1. Plug the Pi's Ethernet cable into the router, then plug in power.
2. Wait about 90 s for the first boot.

**B. Pi straight into the MacBook** (USB-C Ethernet adapter, no router needed)
1. Plug the adapter into the Mac and run the cable from it to the Pi.
2. On the Mac, open **System Settings → General → Sharing → Internet Sharing**:
   - *Share your connection from:* **Wi-Fi**
   - *To computers using:* your **USB 10/100/1000 LAN** adapter
   - Switch it **on**.
3. Power the Pi. The Mac becomes `192.168.2.1` and the Pi gets an address like `192.168.2.x`.

### 2.1 Find the Pi's IP
1. On the Mac, try:
   ```bash
   ping -c 2 nonap-pi.local
   ```
2. If that fails, run:
   ```bash
   arp -a | grep -i "b8:27:eb"
   ```
   `b8:27:eb` is the Raspberry Pi Foundation's hardware prefix.
3. In option A, you can also look in your router's "connected devices" page.

### 2.2 Find the Mac's IP
The Pi and the iPhone both need this address.
- Option A (router): run `ipconfig getifaddr en0` on the Mac.
- Option B (direct cable): use `192.168.2.1`.

### 2.3 Copy the client to the Pi
On the Mac (replace the address with your Pi's):
```bash
make pi-deploy PI_HOST=pi@nonap-pi.local
```
This generates the sounds and copies `pi_client/` to the Pi.

### 2.4 Install on the Pi
1. Log in:
   ```bash
   ssh pi@nonap-pi.local
   ```
2. Run the installer and open the config:
   ```bash
   cd ~/pi_client
   sudo ./install.sh
   nano config.ini
   ```
3. In `config.ini`, set:
   - `server_url = http://<Mac IP>:8000`
   - `device_key` to the same value as `DEVICE_API_KEY` in the Mac's `.env` (the default is `nonap-dev-device-key`)
   - `driver_id = driver1@nonap.demo`
4. Save with `Ctrl+O`, `Enter`, `Ctrl+X`.
5. Reboot:
   ```bash
   sudo reboot
   ```

After the reboot the client starts by itself. Its green LED shows one short blink every 2 s when connected, or a double blink while it can't reach the Mac. Watch the log with:
```bash
ssh pi@nonap-pi.local journalctl -u nonap-pi -f
```

---

## 3. Start the backend on the Mac

1. First time only:
   ```bash
   make setup                                         # Python venvs + Flutter packages
   cp -n .env.example .env                            # then edit DEVICE_API_KEY if you like
   server/.venv/bin/python server/scripts/seed_demo.py  # demo users, fleet, devices (resets demo data)
   ```
2. Every time:
   ```bash
   make server                    # VIDEO_SOURCE=pi (frames come from the Pi)
   # or, for the original MacBook-webcam demo:
   make server-webcam             # VIDEO_SOURCE=webcam
   ```
3. Check it from another terminal:
   ```bash
   curl http://localhost:8000/health
   ```
   The answer includes `"video_source":"pi"`.

The first start upgrades `server/data/ops.db` automatically (Alembic migration `0001_alert_levels`). Existing data is kept.

**No Pi with you?** Pretend to be one using the Mac webcam. It runs the Pi client's own code:
```bash
make simulate-pi          # or: model/.venv/bin/python tools/simulate_pi.py --video clip.mp4
```

---

## 4. Run the app on the iPhone (USB-C)

1. Connect the iPhone with a USB-C cable and tap **Trust** on the phone.
2. Enable **Developer Mode** on the phone: **Settings → Privacy & Security → Developer Mode**, then restart it.
3. First time only, set up signing in Xcode:
   1. Open the workspace:
      ```bash
      open app/ios/Runner.xcworkspace
      ```
   2. Select **Runner → Signing & Capabilities**.
   3. Choose your **Team**. A free Apple ID works for 7 days at a time.
   4. If the bundle id `com.nonap.app` is taken, change it to something unique, such as `com.<yourname>.nonap`.
4. Run:
   ```bash
   cd app
   flutter run --release --dart-define=API_BASE_URL=http://<Mac IP>:8000
   ```
5. On the phone, open **Settings → General → VPN & Device Management** and trust your developer certificate.
6. In the app:
   1. If you didn't pass `--dart-define`, tap the **server chip** (top right) and enter `http://<Mac IP>:8000`.
   2. Tap **Test**. It should say *Connected*.
   3. Allow **Local Network** access when iOS asks.
   4. Sign in with **driver1@nonap.demo / NoNap@123** (or tap the *Priyadarshini* demo card).
   5. Tap **Start driving** and allow notifications.

Fleet view: sign in on a second phone, or sign out and use **manager@nonap.demo / NoNap@123**.

---

## 5. Run the full demo

1. Check that the Pi LED shows a single blink every 2 s.
2. Check the app chips: **Backend**, **Pi Camera · 3.0 fps · 48°C** and **Live** are all green.
3. Sit in front of the Pi camera.
4. Optional: **Calibrate**. Look normally for 10 s and your personal EAR/MAR thresholds are saved.
5. Run through the alert levels:

   | Do this | What happens |
   |---|---|
   | Close your eyes for about 1 s | **Level 1:** Pi chime + fast LED blink. On the phone, an amber banner and a soft haptic. |
   | Close your eyes for about 2 s | **Level 2:** Pi alarm through the jack + solid LED. On the phone, the full-screen red alert with looping alarm, vibration, flashlight strobe, and a spoken warning ("Priyadarshini, you seem drowsy…"). |
   | Tap **I'm awake** | Everything stops on the phone and the Pi within about 1 s. History shows "Acknowledged in x.x s". |
   | Ignore level 2 for 10 s | **Level 3:** "Your fleet manager has been notified". The fleet dashboard shows the driver at the top with a pulsing red border and an *Unacknowledged* badge. |
   | Unplug the Pi's Ethernet | Within about 12 s the app shows **Pi Camera offline** and the LED double-blinks. Plug it back in and it recovers by itself. |

6. Afterwards, summarise the latency data:
   ```bash
   make latency-report        # reads logs/latency_<date>.csv
   ```

**Automated check (no hardware):**
```bash
server/.venv/bin/python scripts/e2e_alert_flow.py
```
This runs the whole alert flow over real HTTP and WebSockets with a scripted eye state, in about 45 s.

All tests:
```bash
make test
cd app && flutter test
```

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| **Camera not detected** (`No working camera backend`) | 1. Check that the ribbon is seated with the blue side towards Ethernet.<br>2. Run `sudo raspi-config` → *Interface Options* → *Legacy Camera* → *Yes*, then reboot.<br>3. Run `vcgencmd get_camera`. It should say `detected=1`.<br>4. Test with `raspistill -o t.jpg`. |
| **No sound from the jack** | 1. Run `aplay ~/pi_client/sounds/chime.wav`.<br>2. Run `sudo raspi-config` → *System Options* → *Audio* → *Headphones*.<br>3. Raise the volume in `alsamixer`.<br>4. Still silent? Set `aplay_device` in `config.ini` using a name from `aplay -L`. |
| **LED permission errors** | Run `sudo ./install.sh` again (it adds a udev rule and the `gpio` group), then reboot. For a quick test, run `sudo python3 nonap_pi.py`. |
| **Pi LED double-blinks** (backend unreachable) | 1. Check the Mac's IP in `config.ini`.<br>2. Run `ping <Mac IP>` from the Pi.<br>3. Make sure the server is running with `VIDEO_SOURCE=pi`.<br>4. A log line with `401` means the device key doesn't match. `409` means the server is in webcam mode. |
| **Phone can't reach the backend** | 1. The iPhone and Mac must share a network (or use option B plus the Mac's Wi-Fi IP).<br>2. Use the Mac's IP, not `localhost`.<br>3. Allow **Local Network** for NoNap: iPhone **Settings → Privacy & Security → Local Network**.<br>4. Tap **Test** in the server sheet. |
| **Mac firewall** blocks connections | Open **System Settings → Network → Firewall → Options**. Allow incoming connections for `python3.11` (or turn the firewall off while demoing). |
| **No alarm sound on the phone** | The alarm uses the playback audio session, so the silent switch doesn't mute it. Check the media volume and that **Start driving** was tapped. |
| **App shows "Camera offline" with the webcam** | In webcam mode the camera starts when the driver taps **Start driving**. On macOS, allow camera access for Terminal or Python. |
| **Alerts while the app is in the background** | Local notifications are a backup while the app is open in the background. True push to a locked or killed app needs APNs and a paid Apple Developer account. Keep NoNap in the foreground while driving; it keeps the screen on. |
