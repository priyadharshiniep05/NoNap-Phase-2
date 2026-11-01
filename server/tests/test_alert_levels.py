"""Unit tests for the time-window alert level policy (frames at ~3 fps)."""

from server.app.services.alert_levels import AlertLevelPolicy, LevelConfig, Observation

FPS = 3.0
DT = 1.0 / FPS
EAR_T, MAR_T = 0.21, 0.60


def obs(ts, ear=0.30, mar=0.15, face=True):
    return Observation(ts=ts, has_face=face, ear=ear, mar=mar, ear_threshold=EAR_T, mar_threshold=MAR_T)


def run(policy, start, seconds, **kw):
    """Feed frames at 3 fps for `seconds`; return (decisions, next timestamp)."""
    out = []
    n = int(round(seconds * FPS))
    t = start
    for _ in range(n):
        out.append(policy.observe(obs(t, **kw)))
        t += DT
    return out, t


def events(decisions):
    return [(d.event, d.level, d.reason) for d in decisions if d.event]


def test_single_blink_is_ignored():
    p = AlertLevelPolicy()
    ds, t = run(p, 0.0, 2.0)
    ds2 = [p.observe(obs(t, ear=0.10))]  # one closed frame ~ a blink
    ds3, _ = run(p, t + DT, 2.0)
    assert events(ds + ds2 + ds3) == []
    assert all(d.state == "awake" for d in ds3)


def test_eyes_closed_raises_level1_at_1s_then_level2_at_2s():
    p = AlertLevelPolicy()
    ds, _ = run(p, 0.0, 3.0, ear=0.10)
    ev = [(round(d.eyes_low_s, 2), d.event, d.level) for d in ds if d.event]
    assert ev[0][1:] == ("new", 1) and ev[0][0] >= 1.0
    assert ev[1][1:] == ("upgrade", 2) and ev[1][0] >= 2.0
    assert len(ev) == 2  # one episode, one alert, upgraded in place
    assert ds[-1].state == "drowsy"


def test_episode_ends_and_cooldown_suppresses_new_level1_but_not_level2():
    p = AlertLevelPolicy()
    _, t = run(p, 0.0, 1.4, ear=0.10)  # L1 episode
    ds, t = run(p, t, 2.0)  # eyes open long enough to end it
    assert not p.episode_active
    ds, t = run(p, t, 1.4, ear=0.10)  # within 5 s cooldown: L1 suppressed
    assert events(ds) == []
    ds, t = run(p, t, 1.0, ear=0.10)  # keeps closing past 2 s: L2 is never suppressed
    assert events(ds) == [("new", 2, "eyes_closed")]


def test_third_level1_within_60s_becomes_level2():
    p = AlertLevelPolicy()
    t = 0.0
    seen = []
    for _ in range(3):
        ds, t = run(p, t, 1.4, ear=0.10)
        seen += events(ds)
        _, t = run(p, t, 8.0)  # end episode and clear the cooldown
    assert seen == [("new", 1, "eyes_closed"), ("new", 1, "eyes_closed"), ("new", 2, "repeated_l1")]


def test_level1_events_older_than_window_do_not_count():
    p = AlertLevelPolicy(cfg=LevelConfig(l1_repeat_window_s=60.0))
    t = 0.0
    seen = []
    for gap in (40.0, 40.0, 0.0):
        ds, t = run(p, t, 1.4, ear=0.10)
        seen += events(ds)
        _, t = run(p, t, gap or 1.0)
    assert [e[1] for e in seen] == [1, 1, 1]


def test_frame_gap_resets_timer():
    p = AlertLevelPolicy()
    d1 = p.observe(obs(0.0, ear=0.10))
    d2 = p.observe(obs(2.5, ear=0.10))  # 2.5 s gap: we did not see the eyes in between
    assert d1.event is None and d2.event is None
    assert d2.eyes_low_s == 0.0


def test_sustained_yawn_is_level1():
    p = AlertLevelPolicy()
    ds, _ = run(p, 0.0, 1.5, mar=0.80)
    assert events(ds) == [("new", 1, "yawn")]


def test_short_mouth_opening_is_not_a_yawn():
    p = AlertLevelPolicy()
    ds, _ = run(p, 0.0, 0.6, mar=0.80)
    assert events(ds) == []


def test_no_face_reports_state_and_resets_timers():
    p = AlertLevelPolicy()
    run(p, 0.0, 0.7, ear=0.10)
    d = p.observe(obs(0.7, face=False))
    assert d.state == "no_face" and d.eyes_low_s == 0.0
    ds, _ = run(p, 1.0, 0.7, ear=0.10)
    assert events(ds) == []


def test_acknowledge_requires_eyes_to_open_before_next_episode():
    p = AlertLevelPolicy()
    _, t = run(p, 0.0, 2.4, ear=0.10)
    p.acknowledge(t)
    ds, t = run(p, t, 3.0, ear=0.10)  # still low right after ack: no new alert
    assert events(ds) == []
    _, t = run(p, t, 6.0)  # opens eyes, cooldown passes
    ds, _ = run(p, t, 1.4, ear=0.10)
    assert events(ds) == [("new", 1, "eyes_closed")]
