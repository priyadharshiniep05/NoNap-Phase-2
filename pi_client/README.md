# NoNap Pi client

This folder turns a **Raspberry Pi 1 Model B with a Pi Camera** into NoNap's in-car camera.

- The Pi takes small photos (320×240, about 3 per second) and sends them to the NoNap server on your MacBook.
- The MacBook does all the detection. The Pi runs no AI.
- When the server says the driver is drowsy, the Pi:
  - lights its **green ACT LED**,
  - plays a **chime or alarm through the 3.5 mm audio jack** (plug in a small speaker or earphones),
  - prints a coloured status line.
- There is **no buzzer** and no breadboard. Nothing connects to the GPIO pins.

For the full setup from a blank SD card, see [`docs/RUN_GUIDE.md`](../docs/RUN_GUIDE.md). This page is the short version.

## What the LED means

| LED | Meaning |
|---|---|
| One short blink every 2 s | Running and connected to the server |
| Two quick blinks every 2 s | Cannot reach the server (check the Ethernet cable and `server_url`) |
| Fast blinking | Level 1 alert (eyes closing or yawning) |
| Solid on | Level 2 or 3 alert. The alarm is playing until the driver taps **I'm awake** on the phone |

## Files

| File | What it is |
|---|---|
| `nonap_pi.py` | The client. Needs Python 3.5+ and `requests`. Uses `picamera` if installed, otherwise `raspistill`, otherwise `rpicam-still`/`libcamera-still`. |
| `config.ini` | Server address, device key, driver, camera settings. |
| `install.sh` | One-time setup: packages, legacy camera, audio to the jack, LED permission, auto-start service. |
| `nonap-pi.service` | The systemd service template that `install.sh` installs. |
| `sounds/chime.wav`, `sounds/alarm.wav` | Made by `python3 tools/make_sounds.py` (no downloads). |

## Quick start

1. **Copy the folder to the Pi.** On the Mac, from the project folder (replace the IP with the Pi's):
   ```bash
   python3 tools/make_sounds.py                 # makes pi_client/sounds/*.wav
   scp -r pi_client pi@192.168.2.2:~/
   ```
2. **Install.** On the Pi:
   ```bash
   cd ~/pi_client
   sudo ./install.sh
   ```
3. **Point it at the Mac.** Edit `config.ini`:
   ```bash
   nano ~/pi_client/config.ini
   ```
   - Set `server_url` to the Mac's address, for example `http://192.168.2.1:8000` with Internet Sharing, or the Mac's Wi-Fi IP when both are on the same router.
   - Make sure `device_key` matches `DEVICE_API_KEY` in the server's `.env`.
   - Set `driver_id` to the driver's login email (default `driver1@nonap.demo`).
4. **Reboot.** This applies the camera and LED settings:
   ```bash
   sudo reboot
   ```
   The client starts by itself after every boot.

## Everyday commands

```bash
journalctl -u nonap-pi -f              # watch the log
sudo systemctl restart nonap-pi        # restart after editing config.ini
sudo systemctl stop nonap-pi           # stop it
python3 ~/pi_client/nonap_pi.py        # run it in the foreground (stop the service first) to see the live status line
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `No working camera backend` | 1. Check the ribbon: the blue side faces the Ethernet port and the contacts are fully seated.<br>2. Run `sudo raspi-config` → *Interface Options* → *Legacy Camera* → *Yes*, then reboot.<br>3. Test with `raspistill -o test.jpg`.<br>4. `vcgencmd get_camera` should say `supported=1 detected=1`. |
| No sound from the jack | 1. Run `aplay ~/pi_client/sounds/chime.wav`.<br>2. Run `sudo raspi-config` → *System Options* → *Audio* → *Headphones*.<br>3. Run `alsamixer` and raise the volume.<br>4. If it is still silent, list devices with `aplay -L` and set `aplay_device` in `config.ini`, for example `plughw:CARD=Headphones,DEV=0`. |
| `Cannot control the ACT LED (Permission denied)` | Run `install.sh` again and reboot. That adds the udev rule `/etc/udev/rules.d/99-nonap-led.rules` and puts your user in the `gpio` group. As a quick test you can also run `sudo python3 nonap_pi.py`. |
| Two quick blinks (server unreachable) | 1. Ping the Mac: `ping 192.168.2.1`.<br>2. Make sure the server is running with `VIDEO_SOURCE=pi`.<br>3. Allow incoming connections for Python in the macOS firewall. |
| `401` in the log | `device_key` in `config.ini` is not the same as `DEVICE_API_KEY` on the server. |
| `404 driver ... not found` | `driver_id` must be an existing driver's email, for example `driver1@nonap.demo` after seeding. |
| `409 ... webcam mode` | Start the server with `VIDEO_SOURCE=pi`. |
| Low fps | This is normal on a Pi 1 if the network is slow. The client lowers its rate automatically (down to `min_fps`) and recovers when the server answers faster. |

## Which OS?

Use **Raspberry Pi OS (Legacy) Lite 32-bit**, the Bullseye-based image that still has the legacy camera stack (`raspistill` and `picamera`). Check with `cat /etc/os-release`. On Bookworm and later the legacy stack is gone. The client then falls back to `rpicam-still`, which works but is heavier on a Pi 1.
