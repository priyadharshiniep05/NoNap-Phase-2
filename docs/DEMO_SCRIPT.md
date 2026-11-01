# NoNap — End-to-End Live Demonstration Script (Phase 2 Upgrade)

This walkthrough guides you through demonstrating all upgraded core requirements of **NoNap** using your MacBook Pro M4 and your connected iPhone 16 Pro.

---

### Prerequisites & Setup
1. **MacBook & iPhone Connection**:
   - iPhone 16 Pro connected via USB-C cable.
   - App installed and running via `com.nonap.app`.

2. **Start the NoNap Server**:
   ```bash
   ./scripts/dev.sh
   ```
   Or start directly:
   ```bash
   server/.venv/bin/uvicorn server.app.main:app --host 0.0.0.0 --port 8000
   ```
   - Server discovers your Mac's LAN IP (e.g. `http://192.168.1.7:8000`).
   - All demo data and accounts use Indian names and **Asia/Kolkata (IST)** time:
     - **Fleet Manager**: `manager@nonap.demo` (Ananya Iyer) / `NoNap@123`
     - **Driver 1 (Live)**: `driver1@nonap.demo` (Priyadarshini Prasanna) / `NoNap@123`
     - **Simulated Drivers**: Nishant Sharma, Namrata Rao, Rohan Gupta

---

### Step 1: Real-Time EAR & MAR (No Fake Values)
1. Log in as **Priyadarshini Prasanna** on the iPhone app (`driver1@nonap.demo`).
2. The MacBook webcam activates automatically via MediaPipe Face Mesh:
   - 468 landmarks are extracted each frame.
   - **EAR** = $(\|p_2-p_6\| + \|p_3-p_5\|) / (2 \cdot \|p_1-p_4\|)$ averaged across both eyes.
   - **MAR** = $(\|p_2-p_8\| + \|p_3-p_7\| + \|p_4-p_6\|) / (2 \cdot \|p_1-p_5\|)$ using inner-lip landmarks.
   - Values are smoothed with a 5-frame moving average to eliminate jitter.
3. Observe live numbers on the driver dashboard:
   - Blink naturally: notice EAR dip momentarily.
   - Open mouth wide or yawn: notice MAR rise immediately.
   - All metrics are 100% computed from the actual video feed.

---

### Step 2: Per-Person Baseline Calibration
1. On the Driver Dashboard, tap the **Calibrate** button on the "Personalized Baseline (DB2)" card.
2. A calibration session runs for 10 seconds:
   - Prompt: *"Look directly at the camera with eyes open and mouth relaxed."*
   - Real-time progress bar and countdown timer appear on the iPhone dashboard.
3. The server collects baseline frames and computes:
   - Baseline mean & standard deviation for open-eye EAR and relaxed MAR.
   - Personalized $\text{EAR}_{\text{drowsy}} = \min(0.75 \times \text{mean}, \text{mean} - 2\sigma)$.
   - Personalized $\text{MAR}_{\text{yawn}} = \text{mean} + 3\sigma$ (minimum floor 0.55).
4. The thresholds are automatically stored in **DB2** (`ops.db`, `thresholds` table with `scope='user'`).
5. The live dashboard updates instantly to reflect your personal baseline thresholds.

---

### Step 3: Real Drowsiness Alerts & Laptop Audible Alarm
1. In front of the camera, close your eyes continuously for $\ge 1.5$ seconds (or simulate a sustained yawn $\ge 1$s).
2. **Instant Multi-Channel Reaction**:
   - **Audible Alarm**: MacBook laptop speaker immediately plays an alarm tone (`afplay /System/Library/Sounds/Sosumi.aiff`).
   - **iPhone Full-Screen Red Alert**: Pulsating crimson modal covers the driver screen with:
     - *"DROWSINESS DETECTED!"*
     - Notification text with IST timestamp: e.g. *"You were drowsy at 22:24 IST."*
     - Reason tag: `EYES CLOSED`, `YAWN`, or `PERCLOS`.
     - Live EAR and personal threshold triggering metrics.
   - **Database Logged**: Saved to DB2 `alert_logs` with severity, timestamp in IST, EAR, and MAR.
   - **10-Second Cooldown**: Drowsiness continues? Alerts are not spammed, but severity escalates from `medium` $\to$ `high` $\to$ `critical`.
   - Tap **I AM AWAKE** to dismiss the warning overlay.

---

### Step 4: Testing with Video Source (`--source` flag)
You can test drowsiness detection using a video file or secondary camera instead of the default webcam:
```bash
# Start monitoring with a pre-recorded test video
curl -X POST http://localhost:8000/monitor/start \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/driver_drowsy.mp4", "driver_id": "510899aa-a068-492c-9b1b-b8da81b4c1c2"}'
```
The video loops seamlessly in memory, MediaPipe processes each frame, and real alerts fire whenever the person in the video closes their eyes.

---

### Step 5: Fleet Management Live Dashboard
1. Log out from the driver dashboard and log in as **Ananya Iyer** (`manager@nonap.demo`).
2. Notice the Fleet Dashboard:
   - **Real-Time Push Updates**: No polling is used; incoming WebSocket events mutate state directly.
   - **Monitored Drivers**:
     - **Priyadarshini Prasanna**: Marked with a green **[LIVE]** badge.
     - **Nishant Sharma, Namrata Rao, Rohan Gupta**: Marked with amber **[SIMULATED]** badges.
   - **Live Alert Cards**:
     - Show driver name, severity badge, IST timestamp (e.g. `22:24 IST`), triggering EAR & MAR values.
     - Driver's status tile updates live between **ALERT** and **DROWSY**.
3. **Strict Role Separation**:
   - Fleet managers cannot access driver mode.
   - Drivers cannot access fleet management.

---

### Step 6: Automated Test Verification
Run the verification test suite anytime to prove correctness:
```bash
# 1. Real-time pipeline formulas, calibration, DB2, timezone & escalation
server/.venv/bin/python scripts/verify_realtime_pipeline.py

# 2. Complete backend test suite (37 unit & integration tests)
server/.venv/bin/pytest server/tests

# 3. Flutter static analysis
cd app && flutter analyze
```
All tests pass cleanly with 0 errors!
