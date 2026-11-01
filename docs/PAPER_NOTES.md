# NoNap — Notes for the IEEE paper: alerting architecture and latency method

This file describes what the system does and how to measure it. It contains **no results**. Every number in the paper must come from `logs/latency_*.csv` and from trials you run yourself.

## 1. Multi-modal alerting on commodity devices

NoNap alerts the driver without any dedicated actuator: no buzzer, no relay, no added electronics. It uses only outputs that a Raspberry Pi 1 and a smartphone already have.

| Channel | Device | Modality | Trigger |
|---|---|---|---|
| On-board ACT LED | Raspberry Pi 1 | Visual (in-cabin) | Fast blink at level 1, solid at levels 2–3. Separate "connected" and "backend unreachable" patterns. |
| 3.5 mm audio jack | Raspberry Pi 1 | Auditory | Chime at level 1. Looping alarm at levels 2–3 until acknowledged. |
| Speaker (playback audio session, works on silent) | iPhone | Auditory | Chime at level 1. Looping alarm at levels 2–3. |
| Taptic engine | iPhone | Haptic | Double tap at level 1. Continuous pulses at levels 2–3. |
| Full-screen UI + flashlight strobe | iPhone | Visual | Banner at level 1. Pulsing red takeover and torch strobe at levels 2–3. |
| Text-to-speech | iPhone | Spoken | "<Name>, you seem drowsy. Please pull over and take a break." Repeated every 8 s at levels 2–3. |
| Fleet dashboard + local notification | Manager's phone | Remote / supervisory | Every alert live. Level 3 (unacknowledged) is highlighted. |

### Pipeline
```
Pi camera ─(320×240 JPEG, ~3 fps, HTTP multipart, Ethernet)─▶ FastAPI /api/v1/frames
   ▲                                                              │ CLAHE → face landmarks (EAR/MAR)
   │ {state, severity 0-3, alert_id} in the HTTP response         │ (→ YOLOv8 + ViT when weights present)
   │ + 1 s poll of /api/v1/alerts/{id} while alerting             ▼
 LED + aplay                                       time-window alert policy (per driver)
                                                                  │ DB2 alert_logs (level, ack time)
                                                                  ▼
                                     WebSocket fan-out (role-scoped): driver phone, fleet manager
```

The Pi gets its alert level in the **same HTTP response** as the frame it sent. Local alerting therefore needs no extra round trip, and the Pi stays a thin client: capture, send, react. No ML runs on the ARMv6 CPU.

### Alert policy (time-based, because the frame rate is low)
At ~3 fps a frame-count rule would turn into a different duration whenever the rate drops. The policy uses timestamps instead (`server/app/services/alert_levels.py`):

- **Level 1:** EAR below the driver's calibrated threshold for ≥ 1.0 s, or MAR above the yawn threshold for ≥ 1.0 s.
- **Level 2:** EAR low for ≥ 2.0 s, or the third level-1 episode within 60 s.
- **Level 3:** a level-2 alert not acknowledged within 10 s. A watchdog checks every 0.5 s.
- **One episode, one alert.** The alert row is upgraded in place. An episode ends after 1.5 s without any condition. A 5 s cooldown suppresses new level-1 alerts but never a level 2.
- **Gaps are not "closed eyes".** If two frames are more than 1.5 s apart, the timers reset.
- **Decisions use unsmoothed EAR/MAR.** The 5-frame moving average used for display would add about 1.7 s of lag at 3 fps.
- **Frame quantisation.** Because frames are about 333 ms apart, a level is reached between 0 and one frame interval after the threshold duration. Report this as part of the method.

### Acknowledgement
- `POST /api/v1/alerts/{id}/ack` stores `acknowledged_at` and `response_time_ms`.
- **Response time** runs from the moment the alert first required acknowledgement (when it reached level 2) to the tap, or from raise time if a level-1 alert is acknowledged. It is measured on the server clock only.
- The phone stops all outputs **before** the request returns. The Pi stops when its next frame response or its 1 s poll shows the acknowledgement.

## 2. Latency instrumentation

Every processed frame produces a row in `logs/latency_<YYYY-MM-DD>.csv` (IST date):

| Column | Clock | Meaning |
|---|---|---|
| `pi_capture_ms` | Pi | Capture time (picamera return / stills file mtime) |
| `server_receive_ms` | Mac | Request body received by FastAPI |
| `inference_done_ms` | Mac | Model + landmark extraction finished |
| `ws_sent_ms` | Mac | Telemetry or alert pushed on the WebSocket (empty if that frame was not broadcast; telemetry is sent at 2 Hz) |
| `app_received_ms` | iPhone | WebSocket message received; the app echoes the `frame_id` back |
| `pi_rtt_ms` | Pi | Send → response of the *previous* frame, measured on the Pi alone |
| `inference_ms`, `server_to_ws_ms` | Mac | Derived from same-clock pairs only |
| `level`, `alert_id` | — | Set on frames that raised or changed an alert |

Missing stages stay empty. Nothing is interpolated.

### How to collect a run
1. Put all three devices on NTP:
   - Mac: System Settings → Date & Time → automatic.
   - iPhone: automatic.
   - Pi: `timedatectl status` should show `System clock synchronized: yes`. With Internet Sharing the Pi gets time through the Mac's connection.
2. Before and after the run, record each device's offset (run on the Pi):
   ```bash
   sntp time.apple.com
   ```
   (or `chronyc tracking` / `timedatectl timesync-status`). Report it next to every cross-clock figure.
3. Start the server with `VIDEO_SOURCE=pi`, the Pi client, and the app with **Start driving**.
4. Run trials following a fixed protocol, for example N trials of "close eyes 3 s, open, wait 20 s". Note lighting, distance and glasses.
5. Summarise:
   ```bash
   python3 tools/latency_report.py --source pi
   python3 tools/latency_report.py --source pi --alerts-only
   python3 tools/latency_report.py --csv > results/latency_summary.csv
   ```

### Which numbers you can claim directly
- **Single-clock, safe to report as-is:**
  - `inference_ms`
  - `server_to_ws_ms`
  - `pi_rtt_ms`
  - `response_time_ms` (in DB2)
- **Cross-clock**, which include device clock offset:
  - uplink (`server_receive − pi_capture`)
  - downlink (`app_received − ws_sent`)
  - end-to-end (`app_received − pi_capture`)

  Report these with the measured offset, or bound them using `pi_rtt_ms`.
- **Detection-to-alert delay** from eye closure to alarm also includes the policy's 1.0 s / 2.0 s windows. Those are design parameters, not processing latency, so state them separately.
- **Exclude** rows with `source = simulated` (`tools/simulate_pi.py`, `scripts/e2e_alert_flow.py`) and all seeded demo history from results. Seeded alert rows are marked `source = simulated` and carry no response times.

## 3. Reproducibility pointers
- Policy timings are in `.env` (`L1_EYES_LOW_SECONDS`, `L2_EYES_LOW_SECONDS`, `ACK_TIMEOUT_SECONDS`, …) and are reported by `GET /api/v1/system`.
- Unit tests for the policy timing: `server/tests/test_alert_levels.py`. Integration tests: `server/tests/test_alerting_flow.py`. Full-stack check: `scripts/e2e_alert_flow.py`.
- The detector backend in use (`baseline` MediaPipe landmarks, or `hybrid` YOLOv8 + ViT when weights are present) is reported per frame in telemetry (`metrics.backend`) and at `/health`. State which one produced your numbers.
