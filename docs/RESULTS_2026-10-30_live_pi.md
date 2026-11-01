# NoNap: live hardware run, 30 Oct 2026 (for the PPT and paper)

All numbers below come from real measurements:
- `logs/latency_2026-10-30.csv` (rows with `source = pi`)
- `server/data/ops.db` → `alert_logs` (`source = pi`, from 30 Oct)

Nothing is estimated or simulated. To regenerate:
```bash
server/.venv/bin/python tools/latency_report.py logs/latency_2026-10-30.csv --source pi
sqlite3 -header -column server/data/ops.db "select * from alert_logs where source='pi' and detected_at >= '2026-10-30'"
```

## Setup

| Part | What was used |
|---|---|
| Camera node | Raspberry Pi 1 Model B Rev 2 (ARMv6, 700 MHz, 512 MB). Raspberry Pi Camera Rev 1.3 (OV5647). Raspberry Pi OS Bullseye Legacy Lite. |
| Pi software | `camera_stream.py`: `raspivid` hardware MJPEG at 320×240, posted over HTTP. Standard library only, no ML on the Pi. |
| Link | Ethernet from the Pi to the MacBook (USB-C LAN adapter, macOS Internet Sharing, 100 Mbit/s full duplex) |
| Backend | MacBook, FastAPI, MediaPipe face landmarks → EAR/MAR, time-window alert policy |
| Driver app | Flutter app on iPhone 16 Pro (iOS 27.0.1), over Wi-Fi WebSocket |

## Session

- **Duration:** 44.0 min (12:42–13:26 IST)
- **Frames processed:** 7,870
- **Average frame rate:** 2.98 fps (target 3 fps)

## Latency (ms)

| Stage | Clock | n | Median | Mean | p95 |
|---|---|---|---|---|---|
| Pi round trip (send → response) | Pi only | 7,811 | **32.6** | 33.3 | 40.5 |
| Inference on the server | Mac only | 7,812 | **10.0** | 10.4 | 15.5 |
| Server receive → WebSocket sent | Mac only | 532 | **10.9** | 11.8 | 17.0 |
| Downlink (WebSocket sent → app received)* | Mac → iPhone | 465 | 162.1 | 179.9 | 324.3 |
| End to end (Pi capture → app received)* | Pi → iPhone | 465 | **225.0** | 229.4 | 428.6 |

Rows marked * cross two device clocks, so their values include the clock offset between those devices (all three were on NTP; the offset was not separately measured this session). Present these as approximate, and give the median: the uplink mean is skewed by frames sent before the Pi's clock had synced after boot.

On frames that raised or changed an alert (n = 20):
- inference median 13.3 ms
- receive → WebSocket median 18.2 ms
- end to end median 222 ms (n = 18)

## Alerts raised by real eye closures and yawns (12 alerts)

| Level | Reason | Count | Outcome |
|---|---|---|---|
| 1 | Yawn (MAR > threshold ≥ 1 s) | 4 | Resolved on their own |
| 1 | Eyes closed ≥ 1 s | 2 | Resolved on their own |
| 2 | Eyes closed ≥ 2 s | 5 | All acknowledged in the app |
| 2 | 3rd level-1 alert within 60 s | 1 | Acknowledged |

**Driver response time (level 2 → "I'm awake" tap), n = 6:**

| Statistic | Value |
|---|---|
| Mean | 1.85 s |
| Median | 1.73 s |
| Min | 0.94 s |
| Max | 3.49 s |

Values: 2.11, 1.34, 1.09, 2.15, 0.94, 3.49 s.

- **Level 3 escalations:** 0 (every level-2 alert was acknowledged within the 10 s timeout).
- **EAR at alert:** eyes-closed alerts 0.058–0.154. Yawn MAR 1.20–1.59.

## Talking points
- The Pi does no ML. It is a camera and nothing else (about 100 lines of Python). All detection and alerting happens on the backend and the phone.
- Detection compute is small next to the policy's design windows: about 10 ms of inference, against 1 s (level 1) and 2 s (level 2) of required eye closure.
- Camera to phone in about 0.23 s median.
- Privacy: frames are held in memory only. No image is written to disk on the Pi, the Mac or the phone. Only numeric EAR/MAR values and timings are stored.
- Limitations to state:
  - single participant;
  - one indoor session;
  - frame quantisation of up to 333 ms at 3 fps;
  - cross-clock figures include NTP offset.
