# NoNap Project Assumptions & Design Decisions

This document records the sensible assumptions made during development to maintain autonomy and velocity without blocking on decisions, per the project master prompt.

### 1. Workspace & Path
- **Assumption:** Development takes place directly in the open workspace `/Users/priyadharshiniprasanna/Desktop/Nonap Phase 2`. All references to `NoNap/` in scripts and documentation represent this project root.
- **Brand Assets:** The two provided image files (`nonap_icon.jpg` and `nonap_logo.jpg`) are verified SVG vector graphics. They are normalized to `brand/nonap_icon.svg` and `brand/nonap_logo.svg`, and rasterized to `brand/nonap_icon_1024.png` for iOS icon and splash generation.

### 2. Detection & Model Architecture
- **In-Memory Frame Processing:** As strictly mandated, no video or raw camera frames are ever written to disk or recorded. Frames exist exclusively in memory buffers (OpenCV / numpy / bytes) during inference and are immediately discarded.
- **Dual-Engine Strategy:** 
  - `Baseline (MediaPipe Face Mesh)`: Computes Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR) with micro-blink filtering and rolling PERCLOS. Operates seamlessly on Apple Silicon M4 and CPU without requiring heavy pre-trained weights.
  - `Hybrid (YOLOv8 + ViT)`: Face detection via YOLOv8 face detector, splitting into Eye ROI and Mouth ROI, passed to a Vision Transformer (timm ViT-tiny / MobileViT). Engine auto-switches to Hybrid if weights exist; otherwise runs Baseline and explicitly labels itself as Baseline in API `/health` and UI.
- **Temporal Windows & Thresholds:**
  - Rolling window: 30 seconds per driver session.
  - Drowsy: continuous eye closure $\ge 1.5$ seconds or PERCLOS $\ge 0.40$.
  - Yawning: MAR $> 0.60$ for $\ge 1.0$ second.
  - Micro-blink filtering: Blinks $< 0.4$ seconds are considered normal and not flagged.
  - Alert cooldown: 30 seconds per alert type to prevent notification spamming.

### 3. Dual Database Architecture & Synchronization
- **Engines:** SQLAlchemy 2.0 with separate database connections:
  - `auth_db` (`server/data/auth.db`): Identity, users (`driver` or `fleet_manager`), fleets, and fleet memberships.
  - `ops_db` (`server/data/ops.db`): Operational thresholds, real-time alert logs, and aggregated session statistics.
- **Sync & Integrity (`db/sync.py`):**
  - Application-level referential integrity: Before any alert log is written to `ops_db`, `auth_db` is queried to confirm the driver exists and holds the `driver` role.
  - Fleet ID denormalization: Current fleet membership is denormalized onto alert logs at write time. If a driver leaves a fleet, historical alerts retain context while future alerts set `fleet_id = NULL`.
  - Automated threshold bootstrapping: User-scoped thresholds row created upon driver signup; fleet-scoped thresholds row created upon fleet creation.
  - Startup & periodic background reconcile task (every 5 minutes) identifies and heals orphan records and missing defaults.

### 4. Strict Three-Tier Role Separation
- **Layer 1 (FastAPI Route Guards):** `require_role(Role.driver)` and `require_role(Role.fleet_manager)` enforce access control at the HTTP handler level. Cross-role attempts immediately abort with HTTP 403 Forbidden.
- **Layer 2 (WebSocket Token Enforcement):** Role and user ID are derived strictly from validated JWT claims, never from client-supplied payload parameters. Drivers receive only their own real-time events; fleet managers receive only events from drivers enrolled in their fleet.
- **Layer 3 (Flutter Client Navigation):** GoRouter redirect guards inspect the authenticated user's role and route drivers to the Driver Dashboard and fleet managers to the Fleet Dashboard. Neither role can navigate to or render screens from the opposing role.

### 5. Mobile & Push Notification Strategy
- **Platform:** Flutter targeting iOS on physical iPhone 16 Pro (connected via USB-C) and iOS Simulator.
- **Local Notifications:** Because Apple APNs push notifications require a paid Apple Developer Account ($99/year), real-time alerts on the iPhone are triggered via local notifications (`flutter_local_notifications`) driven by the live WebSocket connection while the app is active or in background session.
- **FCM Service:** Backend includes a complete FCM notification service stub (`notify_service.py`) that remains inactive unless `FCM_ENABLED=true` is set.

### 6. Raspberry Pi Client
- **Pi 1 Model B Constraints:** The Pi 1 has 256 MB RAM and an ARMv6 single-core processor. It performs zero ML inference.
- **Role:** Pure sensor and actuator client: captures low-resolution JPEG frames (320x240) in memory at ~1 fps, transmits them via HTTP POST to `/detect/frame`, and activates the hardware buzzer on GPIO17 based on the server's boolean response.
