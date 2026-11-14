"""Sunete pentru meniuri și jocuri, generate la pornire, în mai multe scheme."""
import math
import os
import struct
import tempfile
import wave

import settings

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
# nume: (formă de undă, înmulțitor de înălțime, volum, cât de repede se stinge)
SCHEMES = {
    "Clasic": ("sine", 1.0, 1.0, 0.0),
    "Moale": ("triangle", 0.75, 0.9, 0.0),
    "Retro": ("square", 1.0, 0.45, 0.0),
    "Clopoțel": ("bell", 1.5, 1.0, 6.0),
    "Lemn": ("bell", 0.6, 1.1, 18.0),
}
# sunete de deschidere și închidere, alese separat: nume: (deschidere, închidere, formă, stingere)
INTROS = {
    "Liniștit": ([(392, 220), (494, 220), (587, 520)], [(587, 220), (494, 220), (392, 560)], "sine", 0.0),
    "Harpă": ([(262, 160), (330, 160), (392, 160), (523, 600)], [(523, 160), (392, 160), (330, 160), (262, 650)], "bell", 3.0),
    "Clopoței": ([(784, 260), (988, 700)], [(988, 260), (784, 750)], "bell", 4.0),
    "Adânc": ([(196, 350), (294, 700)], [(294, 350), (196, 800)], "triangle", 0.0),
    "Fără sunet": None,
}
_base = os.path.join(tempfile.gettempdir(), "RobisGame_sunete_v6")
enabled = True
scheme = "Clasic"
intro = "Liniștit"


def _wave(kind, phase):
    s = math.sin(phase)
    if kind == "square":
        return 1.0 if s >= 0 else -1.0
    if kind == "triangle":
        return 2 / math.pi * math.asin(s)
    if kind == "bell":
        return 0.75 * s + 0.25 * math.sin(2.76 * phase)
    return s


def _write(path, segments, vol, kind, mult, gain, decay, soft=False):
    frames = bytearray()
    for freq, ms in segments:
        n = int(RATE * ms / 1000)
        f = freq * mult
        for i in range(n):
            if soft:  # intrare și stingere lente, fără „clic”
                env = min(1.0, i / (RATE * 0.06), (n - i) / (RATE * 0.15))
            else:
                env = min(1.0, i / (RATE * 0.004), (n - i) / (RATE * 0.012))
            if decay:
                env *= math.exp(-decay * i / RATE)
            v = vol * gain * env * _wave(kind, 2 * math.pi * f * i / RATE)
            frames += struct.pack("<h", int(32767 * max(-1.0, min(1.0, v))))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def _dir():
    return os.path.join(_base, scheme)


def _make_intro(name):
    spec = INTROS.get(name)
    if not spec:
        return
    start, end, kind, decay = spec
    d = os.path.join(_base, "intro_" + name)
    os.makedirs(d, exist_ok=True)
    for snd, seg in (("start", start), ("exit", end)):
        p = os.path.join(d, snd + ".wav")
        if not os.path.exists(p):
            _write(p, seg, 0.16, kind, 1.0, 1.0, decay, True)


def _path(name):
    if name in ("start", "exit"):
        if not INTROS.get(intro):
            return None
        return os.path.join(_base, "intro_" + intro, name + ".wav")
    return os.path.join(_dir(), name + ".wav")


def _make(name):
    kind, mult, gain, decay = SCHEMES[name]
    d = os.path.join(_base, name)
    os.makedirs(d, exist_ok=True)
    for snd, spec in SOUNDS.items():
        seg, vol = spec[0], spec[1]
        soft = len(spec) > 2 and spec[2]
        p = os.path.join(d, snd + ".wav")
        if not os.path.exists(p):
            # sunetele de pornire și închidere rămân blânde în orice schemă
            _write(p, seg, vol, "sine" if soft else kind, 1.0 if soft else mult, 1.0 if soft else gain,
                   0.0 if soft else decay, soft)


def init():
    global enabled, scheme, intro
    enabled = bool(settings.get("sunete", True))
    intro = settings.get("sunet_intro", "Liniștit")
    if intro not in INTROS:
        intro = "Liniștit"
    scheme = settings.get("schema_sunete", "Clasic")
    if scheme not in SCHEMES:
        scheme = "Clasic"
    try:
        _make(scheme)
        _make_intro(intro)
    except Exception:
        pass


def set_intro(name):
    global intro
    if name not in INTROS:
        return
    intro = name
    settings.put("sunet_intro", name)
    try:
        _make_intro(name)
    except Exception:
        pass


def set_enabled(value):
    global enabled
    enabled = value
    settings.put("sunete", value)


def set_scheme(name):
    global scheme
    if name not in SCHEMES:
        return
    scheme = name
    settings.put("schema_sunete", name)
    try:
        _make(name)
    except Exception:
        pass


def play_sync(name):
    """Sunet care se aude până la capăt (la ieșirea din aplicație)."""
    if not enabled or winsound is None:
        return
    try:
        p = _path(name)
        if p:
            winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except Exception:
        pass


def play(name):
    if not enabled or winsound is None:
        return
    try:
        p = _path(name)
        if p:
            winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
