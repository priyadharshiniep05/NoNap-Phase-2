# NoNap: exhibition quick start (about 5 minutes)

## Before you leave home
- Charge the Mac and the iPhone.
- Pack:
  - Pi with the SD card (tape the card's lock slider up)
  - camera
  - wall charger for the Pi
  - the **new** LAN cable (not the yellow one)
  - grey USB-C hub
  - iPhone cable
- The iPhone app is signed until about **6 Nov**. After that, reinstall it with `flutter run --release` from `app/`.

## Network at the venue
Venue Wi-Fi often blocks devices from talking to each other. The most reliable option is the **iPhone's Personal Hotspot**:
1. iPhone: **Settings → Personal Hotspot → Allow Others to Join**.
2. Mac: join the iPhone's hotspot over Wi-Fi.

The phone and the Mac are then on the same network wherever you are. The Mac's address will look like `172.20.10.x`.

## Start
1. Hardware, in this order:
   1. Camera ribbon in, with the Pi switched off.
   2. LAN cable from the Pi to the grey hub, and the hub into the Mac.
   3. Pi power from the wall charger.
2. On the Mac, in Terminal:
   ```bash
   cd ~/Desktop/"Nonap Phase 2"
   bash scripts/exhibition_start.sh
   ```
   The script:
   - prints the address to type into the app;
   - checks Internet Sharing and the cable;
   - starts the backend;
   - waits until the Pi camera is streaming (about 90 s after the Pi powers on).
3. iPhone:
   1. Open **NoNap** and tap the **server chip** (top right).
   2. Enter the address the script printed, then **Test** → **Save**.
   3. Sign in as **driver1@nonap.demo / NoNap@123**.
   4. Tap **Start driving**.
   5. Open the **Camera view** card to see the live Pi picture.

## Demo script
| Do this | Visitors see |
|---|---|
| Close your eyes for about 1 s | Level 1: amber banner and haptic |
| Close your eyes for about 2 s | Level 2: red full-screen alarm, vibration, flashlight, voice |
| Tap **I'm awake** | Everything stops. History shows the response time. |
| Yawn widely | Level 1 (yawn) |

## If something fails
| Symptom | Fix |
|---|---|
| Script waits forever for the Pi | Check the LNK light on the Pi. Reseat the LAN cable. Make sure Internet Sharing is on (System Settings → General → Sharing). |
| Pi streams but the app says "Waiting for the camera" | The camera isn't detected. Power the Pi off, reseat the ribbon at both ends, and press the small gold connector on the camera board. To check, put the SD card in the Mac and read `nonap/stream.log`. |
| App can't connect | The address in the app must match the one the script printed. The phone and the Mac must be on the same Wi-Fi or hotspot. |
| Port 8000 busy | The script stops the old server by itself. Run it again. |
