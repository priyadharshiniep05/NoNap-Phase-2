# NoNap — End-to-End Live Demonstration Script

This walkthrough guides you through demonstrating all 6 core requirements of **NoNap** using your MacBook Pro M4 and your connected iPhone 16 Pro.

---

### Prerequisites & Setup
1. **MacBook & iPhone Connection**:
   - Connect the iPhone 16 Pro to your MacBook using the USB-C cable.
   - Verify the connection in terminal:
     ```bash
     flutter devices
     ```
     You will see `Priya’s IPhone (mobile) • 00008140-0015789C0AF3001C`.

2. **Start the NoNap Server**:
   ```bash
   ./scripts/dev.sh
   ```
   Note your Mac's LAN IP address printed in the terminal (e.g. `http://192.168.1.15:8000`).

---

### Step 1: Launch the Mobile App on iPhone 16 Pro
1. In Xcode (or via Flutter CLI after signing):
   ```bash
   cd app
   flutter run -d 00008140-0015789C0AF3001C
   ```
2. When the app launches on your iPhone:
   - Tap the **Gear Icon** in the top right of the Login screen.
   - Enter your MacBook's LAN IP (e.g. `http://192.168.1.15:8000`) and tap **Save**.
   - Tap **Test Connection** to verify `/health` returns OK.

---

### Step 2: Driver Dashboard & Real-Time Drowsiness Demo
1. **Log in as Driver**:
   - Tap the quick-fill chip **Driver 1** (`driver1@nonap.demo` / `NoNap@123`).
   - Tap **Sign In**.
2. **Observe Driver Dashboard**:
   - The top banner shows `DRIVER MODE` in cyan with a live connection status chip (`Connected`).
   - The status hero card displays `ALERT & ATTENTIVE` with green glowing accents.
   - Real-time gauge metrics show:
     - **EAR** (Eye Aspect Ratio, threshold: 0.21)
     - **MAR** (Mouth Aspect Ratio, threshold: 0.60)
     - **PERCLOS** (Percentage of Eye Closure, threshold: 40%)
3. **Start Live Webcam Monitoring**:
   - Tap the large **Start Live Monitoring** button.
   - The MacBook webcam starts analyzing your face in real time (frames stay strictly in memory; no video is ever saved to disk).
4. **Trigger Drowsiness Alert**:
   - Close your eyes for ~2 seconds in front of the MacBook webcam.
   - **Immediate Response on iPhone**:
     - Status card changes to pulsating crimson **DROWSY**.
     - Local notification pops up with the exact timestamp:
       > *"You were drowsy at 14:32"*
     - Haptic feedback pulses on the iPhone, accompanied by an alert audio tone.
     - The alert is recorded in the Driver's personal timeline under the **Alerts** tab.
5. **View Driver Stats**:
   - Tap the **Stats** tab at the bottom to view the today's Alertness Score (0–100), the alerts-per-hour histogram, and the PERCLOS trend.

---

### Step 3: Verify Strict Role Separation (Driver cannot access Fleet)
- While in Driver mode, notice there are **zero** fleet management tabs, drivers lists, or company metrics accessible.
- Even if a direct route navigation is attempted, the `GoRouter` guard blocks and redirects back to `/driver`.
- Server APIs strictly return `403 Forbidden` if a driver token requests `/fleet/*` endpoints.

---

### Step 4: Fleet Management Dashboard Demo
1. **Log Out & Log In as Fleet Manager**:
   - Tap **Profile** tab -> **Log Out**.
   - Tap the quick-fill chip **Fleet Manager** (`manager@nonap.demo` / `NoNap@123`).
   - Tap **Sign In**.
2. **Observe Fleet Overview**:
   - App automatically navigates to `/fleet`.
   - The top banner shows `FLEET MANAGEMENT` with KPI summary cards:
     - **Active Drivers**
     - **Total Alerts Today**
     - **Critical Incidents**
     - **Fleet Alertness Average**
3. **Real-Time Driver Grid**:
   - Shows all drivers in the fleet: Alex Rivera, Brenda Vance, and Carlos Diaz.
   - Whenever any driver triggers a drowsiness alert, their card pulses red in real time without refreshing or reloading.
4. **Driver Detail & Acknowledge**:
   - Tap on **Alex Rivera** to inspect individual history, current metrics, and contact information.
   - Tap **Acknowledge Alert** to confirm fleet oversight.
5. **Verify Role Separation (Fleet Manager cannot access Driver Mode)**:
   - Fleet managers cannot access personal driver monitoring or personal driver dashboards. Attempting to navigate to `/driver` automatically redirects back to `/fleet`.

---

### Step 5: Dual Database Synchronization Verification
1. Open a browser on your MacBook: `http://localhost:8000/health`
2. Notice the response verifies:
   - `auth_db`: Stores user credentials, hashed passwords, roles, and fleet assignments.
   - `ops_db`: Stores threshold configurations, alert logs, and session statistics.
   - `orphans`: 0 (synchronized data flow guaranteed by `db/sync.py`).
