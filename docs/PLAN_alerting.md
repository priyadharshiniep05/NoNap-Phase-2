# PLAN — Pi Camera + App-Based Alerting + Premium UI

Status legend: `[x]` done and verified · `[~]` done, needs on-device check · `[ ]` not done

## 1. What exists today (audit, 21 Oct 2026)

| Area | Reality in the repo | Notes for this plan |
|---|---|---|
| Backend | FastAPI, `server/app/…`, routes at `/auth`, `/driver`, `/fleet`, `/monitor`, `/detect`, `/alerts`, `/dev`, `/ws` | No `/api/v1` prefix yet. 37 tests passing. |
| Databases | **SQLite**, not PostgreSQL: `server/data/auth.db` (DB1) and `server/data/ops.db` (DB2), created with `create_all` | `alembic` is in requirements but was never initialised. SQLAlchemy URLs come from env, so Postgres still works by changing `OPS_DB_URL`/`AUTH_DB_URL`. |
| Detection | `model/nonap_model`: CLAHE → MediaPipe FaceMesh EAR/MAR (5-frame smoothing) → optional YOLOv8+ViT if weights exist → per-driver temporal tracker | The engine already returns real EAR/MAR. The per-frame smoothing adds about 1.7 s of lag at 3 fps, so alert timing uses `raw_ear`/`raw_mar`. |
| Calibration | `calibration_service.py`: 10 s capture → per-person EAR/MAR thresholds saved to DB2 | Kept as is. Works with any frame source. |
| Alerts | `alert_service.create_and_broadcast_alert` (low/medium/high/critical), no levels, ack only sets a boolean, **no ownership check on acknowledge** | Replace frame-driven alerting with a level engine. Keep this path for SOS and `/dev/simulate`. |
| WebSocket | `/ws?token=` with `ConnectionManager`. **Bug:** fleet managers get `fleet_id=None`, which matches every driver in every fleet | Fix the scoping. Add `/ws/driver/{id}` and `/ws/fleet/{id}`. |
| Webcam | `webcam_worker` thread runs its own asyncio loop and sends on sockets owned by the main loop | Send work to the main loop with `run_coroutine_threadsafe`. |
| Fallback | `detection_service` returns **hard-coded EAR 0.28 / MAR 0.15** when inference fails | Remove it. Errors are reported as `error`, never as made-up metrics. |
| Pi client | `pi-client/` is empty. Docs mention a GPIO17 buzzer | Build a new `pi_client/`. No buzzer code anywhere (a disabled flag only). |
| Flutter | Riverpod + go_router + dio. Role guard works. Theme is minimal. `flutter analyze` is clean | Add design system, redesigned screens and the full alert experience. |

## 2. Design decisions

1. **Alert levels run on time windows, not frame counts** (`server/app/services/alert_levels.py`, pure and unit-tested):
   - L1: raw EAR < personal threshold for ≥ 1.0 s, **or** MAR > threshold for ≥ 1.0 s (a yawn, not a word).
   - L2: EAR low for ≥ 2.0 s, **or** the 3rd L1 episode within 60 s.
   - L3: an L2 that is not acknowledged within 10 s (a watchdog task, `alerting_service.check_escalations`).
   - One episode gives one alert. The alert is upgraded in place (L1→L2→L3). The episode ends after 1.5 s with no condition. A 5 s cooldown suppresses new L1s but never an L2. While an L2/L3 is unacknowledged, new episodes attach to it and do not create new alerts.
   - A gap of more than 1.5 s between frames resets the run timers, so a dropped-frame gap is never counted as "eyes closed".
2. **Ack:** `POST /api/v1/alerts/{id}/ack` (owning driver only). It stores `acknowledged_at` and `response_time_ms` (from when the alert was first raised) and closes the current episode. The Pi stops when its 1 s poll of `GET /api/v1/alerts/{id}` shows `acknowledged`.
3. **Device auth:** the Pi has no user account. It sends `X-Device-Key` (`DEVICE_API_KEY` in `.env`). `driver_id` in `config.ini` can be the driver's **email** or UUID.
4. **Liveness:** heartbeat every 5 s, and frames also count. A device is offline after `DEVICE_OFFLINE_SECONDS=12` (below the 15 s acceptance bound). A watchdog broadcasts online↔offline changes.
5. **Latest frame only:** per-device sequence numbers. A frame that waited behind a newer one returns `dropped: true` without inference. Inference runs in a worker thread behind a global lock, because MediaPipe is not re-entrant.
6. **Latency CSV** `logs/latency_YYYY-MM-DD.csv`: `pi_capture_ms, server_receive_ms, inference_done_ms, ws_sent_ms, app_received_ms, pi_rtt_ms`. The app echoes `frame_id` back over the WebSocket. Columns from different clocks are labelled. Only real measurements are written, and missing values stay empty.
7. **Migrations:** Alembic env under `server/migrations/` for DB2. It is idempotent (it inspects columns first), so existing `ops.db` files upgrade on startup.
8. **Times:** stored as IST wall-clock (as in the existing seed), serialised with an explicit `+05:30`. The app formats everything in IST, whatever the phone's time zone.

## 3. Phases

### Phase A — Backend
- [x] Config: `VIDEO_SOURCE`, `DEVICE_API_KEY`, level timings, `DEVICE_OFFLINE_SECONDS`, `LATENCY_LOG_DIR`
- [x] DB2: `alert_logs` + level, status, reason, acknowledged_at, response_time_ms, escalated_at, device_id, frame_id; new `devices` table
- [x] Alembic env + idempotent migration, run on startup
- [x] `alert_levels.py` (pure policy) + `alerting_service.py` (persist, broadcast, ack, L3 watchdog)
- [x] `device_service.py` (heartbeat, online/offline watchdog)
- [x] `latency_logger.py` + `tools/latency_report.py`
- [x] `/api/v1/frames`, `/api/v1/devices/heartbeat`, `/api/v1/devices/{id}`, `/api/v1/alerts/{id}`, `/api/v1/alerts/{id}/ack`, driver session start/end
- [x] `/ws/driver/{id}`, `/ws/fleet/{id}`, telemetry throttled to 2 Hz, snapshot on connect, fleet scoping fix
- [x] `VIDEO_SOURCE=webcam` path through the same pipeline. Webcam worker uses the main loop
- [x] Remove the fake-metric fallback
- [x] Seed: Indian names, IST, devices/vehicles, no invented response times
- [x] Tests: escalation timing, ack/timeout, frames endpoint, device online/offline, WS role scoping

### Phase B — Pi client
- [x] `pi_client/nonap_pi.py` (picamera → raspistill fallback, Python 2.7/3.x-safe syntax), `config.ini`
- [x] ACT LED patterns thread, restores the trigger on exit
- [x] `aplay` chime/alarm, no overlapping sounds, stops on ack
- [x] ANSI status line + banner
- [x] `tools/make_sounds.py`, `install.sh`, `nonap-pi.service`, `README.md`
- [x] `tools/simulate_pi.py` (webcam or video file → `/frames`, same protocol)

### Phase C — Flutter
- [x] Design tokens in `lib/theme/` (colours, type, spacing, radii, glows, motion)
- [x] Packages: flutter_animate, lucide_icons, flutter_tts, torch_light, wakelock_plus, audio_session, vibration
- [x] Reconnecting WebSocket with role-specific endpoint, connection indicator, latency echo
- [x] Alert controller: L1 banner, L2/L3 takeover (loop audio, vibration, TTS, torch strobe), countdown ring, ack
- [x] Splash, login, signup with role cards
- [x] Driver dashboard: greeting, IST clock, chips, status ring, EAR/MAR sparklines, session card, Start/End
- [x] History timeline + by-hour chart. Calibration flow
- [x] Fleet dashboard: summary tiles, sorted driver cards, live feed, driver detail
- [x] Empty/skeleton/error states
- [x] Info.plist keys, launcher icons, native splash
- [x] `flutter analyze` clean, unit tests pass

### Phase D — Docs
- [x] `docs/RUN_GUIDE.md`, `docs/PAPER_NOTES.md`, `pi_client/README.md`, `scripts/e2e_alert_flow.py`

## 4. Verification log (21 Oct 2026)
- Server: 60 pytest tests pass (37 existing + 10 policy timing + 13 alerting/devices/WS). Model: 12 pass.
- `scripts/e2e_alert_flow.py`: 17/17 checks over real HTTP + WebSockets (scripted eye state):
  - L1 at 1.36 s and L2 at 2.40 s after the eyes close (includes up to one 333 ms frame interval)
  - Pi stops 0.19 s after the ack
  - L3 on the fleet socket
  - Pi offline shown after 12.2 s
- Flutter: `flutter analyze` clean, 19 unit tests pass, `flutter build ios --no-codesign` succeeds.
- UI tour on the iPhone 16 Pro Max simulator (`integration_test/ui_tour_test.dart`) passes and was inspected by screenshot:
  - login
  - driving dashboard
  - level 1 banner
  - level 2 takeover with countdown
  - acknowledgement card
  - fleet dashboard
- Bugs found and fixed during verification:
  - the notification-permission prompt blocked the first frame;
  - icon PNG had white corners on the launch screen;
  - duplicate ack handling hid the "Stay safe" card;
  - fonts needed internet access.
- **Not verified here** (needs your hardware): real Pi 1 camera/LED/jack, real-face detection timing, iPhone haptics/torch/TTS on device.
