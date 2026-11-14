"""Sunete scurte pentru meniuri, generate la pornire (nu au nevoie de fișiere separate)."""
import json
import math
import os
import struct
import tempfile
import wave

try:
    import winsound
except ImportError:
    winsound = None

RATE = 22050
SOUNDS = {
    "move": ([(1000, 30)], 0.22),
    "select": ([(660, 45), (990, 70)], 0.3),
    "back": ([(990, 45), (660, 70)], 0.3),
    "edge": ([(200, 70)], 0.35),
    "correct": ([(523, 80), (659, 80), (784, 80), (1047, 160)], 0.32),
    "wrong": ([(311, 140), (233, 260)], 0.35),
}
_dir = os.path.join(tempfile.gettempdir(), "RobisGame_sunete_v2")
_cfg = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "RobisGame", "setari.json")
enabled = True


def _write(path, segments, vol):
    frames = bytearray()
    for freq, ms in segments:
        n = int(RATE * ms / 1000)
        for i in range(n):
            env = min(1.0, i / (RATE * 0.004), (n - i) / (RATE * 0.012))
            frames += struct.pack("<h", int(32767 * vol * env * math.sin(2 * math.pi * freq * i / RATE)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def init():
    global enabled
    try:
        with open(_cfg, encoding="utf-8") as f:
            enabled = bool(json.load(f).get("sunete", True))
    except Exception:
        enabled = True
    try:
        os.makedirs(_dir, exist_ok=True)
        for name, (seg, vol) in SOUNDS.items():
            p = os.path.join(_dir, name + ".wav")
            if not os.path.exists(p):
                _write(p, seg, vol)
    except Exception:
        pass


def set_enabled(value):
    global enabled
    enabled = value
    try:
        os.makedirs(os.path.dirname(_cfg), exist_ok=True)
        with open(_cfg, "w", encoding="utf-8") as f:
            json.dump({"sunete": value}, f)
    except Exception:
        pass


def play(name):
    if not enabled or winsound is None:
        return
    p = os.path.join(_dir, name + ".wav")
    try:
        winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
