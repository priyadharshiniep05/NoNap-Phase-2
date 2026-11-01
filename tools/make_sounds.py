#!/usr/bin/env python3
"""Generate NoNap alert sounds with the standard library only (wave + math).

    python3 tools/make_sounds.py

Writes:
  pi_client/sounds/chime.wav    level 1: soft two-note chime (Pi 3.5 mm jack)
  pi_client/sounds/alarm.wav    level 2-3: urgent two-tone pulse, loops cleanly
  app/assets/sounds/chime.wav   the same chime for the iPhone app (if app/ exists)

22.05 kHz, mono, 16-bit: light enough for aplay on a Raspberry Pi 1.
Works with Python 3.5+.
"""

from __future__ import division

import math
import os
import struct
import wave

RATE = 22050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_wav(path, samples):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    w = wave.open(path, "wb")
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples)
        w.writeframes(frames)
    finally:
        w.close()
    print("wrote {} ({:.2f} s)".format(os.path.relpath(path, ROOT), len(samples) / RATE))


def bell(freq, start, dur, total, decay=4.5, gain=0.5):
    """A soft bell: fundamental + quiet overtone with exponential decay."""
    out = [0.0] * total
    s0 = int(start * RATE)
    for i in range(int(dur * RATE)):
        t = i / RATE
        env = math.exp(-decay * t) * min(1.0, t / 0.008)  # 8 ms attack: no click
        v = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * 2.01 * freq * t)
        if s0 + i < total:
            out[s0 + i] += gain * env * v
    return out


def chime():
    total = int(1.1 * RATE)
    a = bell(880.0, 0.0, 1.1, total)  # A5
    b = bell(1318.5, 0.18, 0.92, total)  # E6
    return [x + y for x, y in zip(a, b)]


def alarm():
    """2.0 s: four 0.5 s cells of 880/1175 Hz beeps. Starts and ends silent so it loops."""
    total = int(2.0 * RATE)
    out = [0.0] * total
    cell = int(0.5 * RATE)
    beep = int(0.36 * RATE)
    for c in range(4):
        freq = 880.0 if c % 2 == 0 else 1174.7
        for i in range(beep):
            t = i / RATE
            edge = min(1.0, i / (0.006 * RATE), (beep - i) / (0.006 * RATE))
            # a little 3rd harmonic makes it cut through road noise without being a harsh square wave
            v = math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * 3 * freq * t)
            out[c * cell + i] = 0.62 * edge * v
    return out


def main():
    c = chime()
    write_wav(os.path.join(ROOT, "pi_client", "sounds", "chime.wav"), c)
    write_wav(os.path.join(ROOT, "pi_client", "sounds", "alarm.wav"), alarm())
    if os.path.isdir(os.path.join(ROOT, "app", "assets")):
        write_wav(os.path.join(ROOT, "app", "assets", "sounds", "chime.wav"), c)


if __name__ == "__main__":
    main()
