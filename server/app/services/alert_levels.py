"""Time-window alert level policy (pure logic, no I/O).

Frames arrive at only ~3 fps from the Raspberry Pi, so every rule is expressed
in seconds measured on frame timestamps, never in frame counts.

Level 1: EAR below the driver's threshold for >= L1 seconds, or MAR above the
         yawn threshold for >= YAWN_MIN seconds.
Level 2: EAR low for >= L2 seconds, or the Nth level-1 episode inside the
         repeat window.
Level 3: is not decided here. It is time-based on an unacknowledged level-2
         alert and lives in alerting_service.

One drowsiness episode produces one alert, upgraded in place. An episode ends
after EPISODE_END seconds without any condition; a cooldown then suppresses new
level-1 episodes (never level 2).
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

# Tolerance for timestamp arithmetic (three 1/3 s frame intervals sum to 0.999...).
EPS = 1e-6


@dataclass
class LevelConfig:
    l1_eyes_low_s: float = 1.0
    l2_eyes_low_s: float = 2.0
    yawn_min_s: float = 1.0
    l1_repeat_count: int = 3
    l1_repeat_window_s: float = 60.0
    episode_end_s: float = 1.5
    cooldown_s: float = 5.0
    max_frame_gap_s: float = 1.5

    @classmethod
    def from_settings(cls, s) -> "LevelConfig":
        return cls(
            l1_eyes_low_s=s.L1_EYES_LOW_SECONDS,
            l2_eyes_low_s=s.L2_EYES_LOW_SECONDS,
            yawn_min_s=s.YAWN_MIN_SECONDS,
            l1_repeat_count=s.L1_REPEAT_COUNT,
            l1_repeat_window_s=s.L1_REPEAT_WINDOW_SECONDS,
            episode_end_s=s.EPISODE_END_SECONDS,
            cooldown_s=s.ALERT_COOLDOWN_SECONDS,
            max_frame_gap_s=s.MAX_FRAME_GAP_SECONDS,
        )


@dataclass
class Observation:
    ts: float  # seconds, server clock
    has_face: bool
    ear: float
    mar: float
    ear_threshold: float
    mar_threshold: float


@dataclass
class Decision:
    state: str  # awake | drowsy | no_face
    level: int  # level of the current episode (0 when none)
    event: Optional[str] = None  # None | "new" | "upgrade"
    reason: Optional[str] = None  # eyes_closed | yawn | repeated_l1
    eyes_low_s: float = 0.0
    yawn_s: float = 0.0


@dataclass
class AlertLevelPolicy:
    cfg: LevelConfig = field(default_factory=LevelConfig)

    _last_ts: Optional[float] = None
    _eyes_low_since: Optional[float] = None
    _yawn_since: Optional[float] = None

    _episode_level: int = 0
    _episode_reason: Optional[str] = None
    _last_condition_ts: Optional[float] = None
    _last_episode_end: Optional[float] = None
    _rearm_required: bool = False
    _l1_events: Deque[float] = field(default_factory=deque)

    @property
    def episode_active(self) -> bool:
        return self._episode_level > 0

    def acknowledge(self, ts: float) -> None:
        """The driver confirmed they are awake: close the episode.

        A new episode can only start after the conditions clear once, so a
        driver who acknowledges while still looking down is not re-alerted on
        the very next frame.
        """
        self._end_episode(ts)
        self._rearm_required = True

    def observe(self, obs: Observation) -> Decision:
        cfg = self.cfg

        # A long gap (network drop, Pi stall) means we did not see the eyes in
        # between; never count unseen time as "eyes closed".
        if self._last_ts is not None and obs.ts - self._last_ts > cfg.max_frame_gap_s:
            self._eyes_low_since = None
            self._yawn_since = None
        self._last_ts = obs.ts

        if not obs.has_face:
            self._eyes_low_since = None
            self._yawn_since = None
            eyes_low = yawning = False
        else:
            eyes_low = obs.ear < obs.ear_threshold
            yawning = obs.mar > obs.mar_threshold

        if eyes_low:
            if self._eyes_low_since is None:
                self._eyes_low_since = obs.ts
        else:
            self._eyes_low_since = None
        if yawning:
            if self._yawn_since is None:
                self._yawn_since = obs.ts
        else:
            self._yawn_since = None

        eyes_low_s = obs.ts - self._eyes_low_since if self._eyes_low_since is not None else 0.0
        yawn_s = obs.ts - self._yawn_since if self._yawn_since is not None else 0.0

        desired, reason = 0, None
        if eyes_low_s + EPS >= cfg.l2_eyes_low_s:
            desired, reason = 2, "eyes_closed"
        elif eyes_low_s + EPS >= cfg.l1_eyes_low_s:
            desired, reason = 1, "eyes_closed"
        elif yawn_s + EPS >= cfg.yawn_min_s:
            desired, reason = 1, "yawn"

        event = None
        if desired == 0:
            self._rearm_required = False
            if self.episode_active and self._last_condition_ts is not None:
                if obs.ts - self._last_condition_ts + EPS >= cfg.episode_end_s:
                    self._end_episode(obs.ts)
        elif not self._rearm_required:
            self._last_condition_ts = obs.ts
            if not self.episode_active:
                event = self._start_episode(obs.ts, desired, reason)
            elif desired > self._episode_level:
                self._episode_level = desired
                self._episode_reason = reason
                event = "upgrade"

        if not obs.has_face:
            state = "no_face"
        elif self.episode_active or desired > 0:
            state = "drowsy"
        else:
            state = "awake"

        return Decision(
            state=state,
            level=self._episode_level,
            event=event,
            reason=self._episode_reason if self.episode_active else None,
            eyes_low_s=round(eyes_low_s, 2),
            yawn_s=round(yawn_s, 2),
        )

    def _start_episode(self, ts: float, desired: int, reason: str) -> Optional[str]:
        cfg = self.cfg
        in_cooldown = (
            self._last_episode_end is not None and ts - self._last_episode_end < cfg.cooldown_s
        )
        if desired == 1 and in_cooldown:
            return None

        level = desired
        if desired == 1:
            while self._l1_events and ts - self._l1_events[0] > cfg.l1_repeat_window_s:
                self._l1_events.popleft()
            self._l1_events.append(ts)
            if len(self._l1_events) >= cfg.l1_repeat_count:
                level, reason = 2, "repeated_l1"
                self._l1_events.clear()

        self._episode_level = level
        self._episode_reason = reason
        return "new"

    def _end_episode(self, ts: float) -> None:
        self._episode_level = 0
        self._episode_reason = None
        self._last_condition_ts = None
        self._last_episode_end = ts
