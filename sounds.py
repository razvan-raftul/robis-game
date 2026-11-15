"""Sunete pentru meniuri și jocuri, generate la pornire.
Meniul: bătăi și clicuri (fără note). Corect/greșit, deschidere/închidere: sunete de celestă."""
import math
import os
import random
import struct
import tempfile
import wave

import settings

try:
    import winsound
except ImportError:
    winsound = None

RATE = 22050


# ---------------- unelte de sinteză ----------------
def _hit(tone_start, tone_end, tone_decay, tone_amp, noise_amp, noise_decay, bright, length=0.12, seed=1):
    """O bătaie: un „bum” scurt care coboară repede + un fâșâit scurt de atingere.
    bright: 0 = zgomot înfundat (lemn, masă), 1 = zgomot ascuțit (clic, castanete)."""
    rnd = random.Random(seed)
    n = int(RATE * length)
    out = []
    phase = 0.0
    lp = 0.0
    prev = 0.0
    a = 0.02 + 0.6 * (1 - bright)  # cât de înfundat e zgomotul
    for i in range(n):
        t = i / RATE
        f = tone_end + (tone_start - tone_end) * math.exp(-t * 60)
        phase += 2 * math.pi * f / RATE
        tone = tone_amp * math.sin(phase) * math.exp(-t * tone_decay)
        w = rnd.uniform(-1, 1)
        lp += (w - lp) * (1 - a)
        if bright > 0.5:
            nz, prev = lp - prev, lp  # doar partea ascuțită
            nz *= 2.0
        else:
            nz = lp
        noise = noise_amp * nz * math.exp(-t * noise_decay)
        att = min(1.0, i / (RATE * 0.0008))
        out.append(att * (tone + noise))
    while out and abs(out[-1]) < 0.002:
        out.pop()
    return out


def _gap(ms):
    return [0.0] * int(RATE * ms / 1000)


def _scale(s, k):
    return [x * k for x in s]


def _celesta_notes(notes, total, bright=1.0, decay=3.5, vol=0.22, tremolo=0.0):
    """notes: listă de (start_secunde, frecvență). Sunet de celestă: clopoțel mic, limpede, care se stinge."""
    n = int(RATE * total)
    buf = [0.0] * n
    partials = [(1.0, 1.0), (2.0, 0.28 * bright), (3.0, 0.08 * bright), (4.07, 0.12 * bright)]
    for start, freq in notes:
        s0 = int(start * RATE)
        for i in range(s0, n):
            t = (i - s0) / RATE
            env = min(1.0, t / 0.002) * math.exp(-t * decay)
            if t > 0.01 and env < 0.0005:
                break
            if tremolo:
                env *= 1 - tremolo * (0.5 + 0.5 * math.sin(2 * math.pi * 5.5 * t))
            v = 0.0
            for mult, amp in partials:
                v += amp * math.exp(-t * decay * (mult - 1) * 0.8) * math.sin(2 * math.pi * freq * mult * t)
            buf[i] += vol * env * v
    # coada liniștită: fade final ca să nu facă „clic”
    fade = int(RATE * 0.05)
    for k in range(min(fade, n)):
        buf[n - 1 - k] *= k / fade
    return buf


def _save(path, samples, level=0.25):
    """Scrie sunetul cu vârful la nivelul cerut (ca toate să fie la fel de tari, nu prea tare)."""
    peak = max((abs(x) for x in samples), default=0) or 1.0
    g = level / peak
    frames = bytearray()
    for x in samples:
        frames += struct.pack("<h", int(32767 * max(-1.0, min(1.0, x * g))))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def _note(name):
    """C5, E6 ... -> frecvență."""
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    semi = names[name[0]] + (1 if "#" in name else 0) - (1 if "b" in name[1:] else 0)
    octave = int(name[-1])
    return 440.0 * 2 ** ((semi + (octave - 4) * 12) / 12)


# ---------------- schemele pentru meniu (doar bătăi) ----------------
# nume: parametrii bătăii de bază pentru _hit
SCHEMES = {
    "Bătaie în lemn": dict(tone_start=1400, tone_end=900, tone_decay=70, tone_amp=0.5, noise_amp=0.5, noise_decay=120, bright=0.3),
    "Clic": dict(tone_start=3000, tone_end=2500, tone_decay=400, tone_amp=0.15, noise_amp=0.9, noise_decay=500, bright=1.0),
    "Tic-tac": dict(tone_start=3500, tone_end=3000, tone_decay=180, tone_amp=0.35, noise_amp=0.6, noise_decay=300, bright=0.9),
    "Bătaie în ușă": dict(tone_start=260, tone_end=130, tone_decay=35, tone_amp=0.8, noise_amp=0.5, noise_decay=90, bright=0.1),
    "Degete pe masă": dict(tone_start=500, tone_end=250, tone_decay=60, tone_amp=0.4, noise_amp=0.7, noise_decay=110, bright=0.2),
    "Tobă mică": dict(tone_start=320, tone_end=180, tone_decay=30, tone_amp=0.5, noise_amp=0.8, noise_decay=35, bright=0.7),
    "Castanete": dict(tone_start=2200, tone_end=1900, tone_decay=150, tone_amp=0.4, noise_amp=0.7, noise_decay=220, bright=0.95),
    "Hârtie": dict(tone_start=0.1, tone_end=0.1, tone_decay=1, tone_amp=0.0, noise_amp=0.8, noise_decay=60, bright=0.8),
}


def _scheme_sounds(p):
    """Din bătaia de bază face sunetele de meniu, ușor de deosebit între ele."""
    base = _hit(**p, seed=1)
    lower = dict(p, tone_start=p["tone_start"] * 0.7, tone_end=p["tone_end"] * 0.7)
    higher = dict(p, tone_start=p["tone_start"] * 1.25, tone_end=p["tone_end"] * 1.25)
    heavy = dict(p, tone_start=p["tone_start"] * 0.45, tone_end=p["tone_end"] * 0.45,
                 tone_decay=p["tone_decay"] * 0.6, tone_amp=max(p["tone_amp"], 0.3), noise_decay=p["noise_decay"] * 0.6)
    return {
        "move": _scale(base, 0.55),                                              # o bătaie mică
        "select": _scale(_hit(**p, seed=2) + _gap(55) + _hit(**higher, seed=3), 0.75),  # două bătăi, a doua mai sus
        "back": _scale(_hit(**p, seed=4) + _gap(55) + _hit(**lower, seed=5), 0.75),     # două bătăi, a doua mai jos
        "edge": _scale(_hit(**heavy, length=0.2, seed=6), 0.8),                  # o bătaie grea, înfundată
    }


# ---------------- corect / greșit: celestă ----------------
def _correct():
    notes = [(0.0, _note("C6")), (0.09, _note("E6")), (0.18, _note("G6")), (0.27, _note("C7"))]
    return _celesta_notes(notes, 1.3, decay=3.0)


def _wrong():
    notes = [(0.0, _note("E5")), (0.0, _note("F5")), (0.22, _note("B4")), (0.22, _note("C5"))]
    return _celesta_notes(notes, 1.2, bright=0.6, decay=4.0, vol=0.18)


# ---------------- deschidere / închidere: în genul celestei ----------------
def _intro_spec(name):
    """Întoarce (note deschidere, note închidere, opțiuni timbru)."""
    up = lambda seq, step: [(i * step, _note(n)) for i, n in enumerate(seq)]
    if name == "Celestă":
        o = up(["C6", "E6", "G6", "C7"], 0.16)
        c = up(["C7", "G6", "E6", "C6"], 0.16)
        return o, c, dict()
    if name == "Cutie muzicală":
        o = up(["G5", "C6", "E6", "G6", "E6", "C7"], 0.14)
        c = up(["C7", "G6", "E6", "C6", "G5"], 0.16)
        return o, c, dict(bright=1.4, decay=2.6)
    if name == "Clopoței de vânt":
        o = [(0.0, _note("D6")), (0.11, _note("A6")), (0.19, _note("F#6")), (0.33, _note("B6")), (0.42, _note("E7"))]
        c = [(0.0, _note("E7")), (0.12, _note("B6")), (0.22, _note("F#6")), (0.36, _note("A6")), (0.47, _note("D6"))]
        return o, c, dict(decay=2.2, vol=0.18)
    if name == "Glockenspiel":
        o = up(["E6", "G#6", "B6", "E7"], 0.13)
        c = up(["E7", "B6", "G#6", "E6"], 0.13)
        return o, c, dict(bright=1.6, decay=2.0, vol=0.2)
    if name == "Vibrafon":
        o = up(["F5", "A5", "C6", "E6"], 0.2)
        c = up(["E6", "C6", "A5", "F5"], 0.2)
        return o, c, dict(bright=0.5, decay=1.8, tremolo=0.35)
    return None


INTROS = {n: True for n in ("Celestă", "Cutie muzicală", "Clopoței de vânt", "Glockenspiel", "Vibrafon")}
INTROS["Fără sunet"] = None

_base = os.path.join(tempfile.gettempdir(), "RobisGame_sunete_v9")
enabled = True
scheme = "Bătaie în lemn"
intro = "Celestă"


def _make_intro(name):
    spec = _intro_spec(name) if INTROS.get(name) else None
    if not spec:
        return
    o, c, opts = spec
    d = os.path.join(_base, "intro_" + name)
    os.makedirs(d, exist_ok=True)
    for snd, notes in (("start", o), ("exit", c)):
        p = os.path.join(d, snd + ".wav")
        if not os.path.exists(p):
            total = notes[-1][0] + 1.6
            _save(p, _celesta_notes(notes, total, **opts), 0.22)


def _make(name):
    d = os.path.join(_base, name)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(os.path.join(d, "demo.wav")):
        snds = _scheme_sounds(SCHEMES[name])
        levels = {"move": 0.22, "select": 0.28, "back": 0.28, "edge": 0.3}
        demo = []
        for snd, data in snds.items():
            peak = max((abs(x) for x in data), default=0) or 1.0
            snds[snd] = [x * levels[snd] / peak for x in data]
            _save(os.path.join(d, snd + ".wav"), snds[snd], levels[snd])
        for snd in ("move", "move", "select", "back"):
            demo += snds[snd] + _gap(150)
        _save(os.path.join(d, "demo.wav"), demo, 0.3)
    common = os.path.join(_base, "comun")
    os.makedirs(common, exist_ok=True)
    for snd, fn in (("correct", _correct), ("wrong", _wrong)):
        p = os.path.join(common, snd + ".wav")
        if not os.path.exists(p):
            _save(p, fn(), 0.3)


def _path(name):
    if name in ("start", "exit"):
        if not INTROS.get(intro):
            return None
        return os.path.join(_base, "intro_" + intro, name + ".wav")
    if name in ("correct", "wrong"):
        return os.path.join(_base, "comun", name + ".wav")
    return os.path.join(_base, scheme, name + ".wav")


def init():
    global enabled, scheme, intro
    enabled = bool(settings.get("sunete", True))
    intro = settings.get("sunet_intro", "Celestă")
    if intro not in INTROS:
        intro = "Celestă"
    scheme = settings.get("schema_sunete", "Bătaie în lemn")
    if scheme not in SCHEMES:
        scheme = "Bătaie în lemn"
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


def _play_file(p):
    if not enabled or winsound is None or not p:
        return
    try:
        winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


def preview_scheme(name):
    """Ascultă o schemă de meniu fără s-o alegi."""
    if name not in SCHEMES:
        return
    try:
        _make(name)
    except Exception:
        return
    _play_file(os.path.join(_base, name, "demo.wav"))


def preview_intro(name):
    """Ascultă un sunet de deschidere fără să-l alegi. „Fără sunet” oprește ce se aude."""
    if not INTROS.get(name):
        if winsound is not None:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass
        return
    try:
        _make_intro(name)
    except Exception:
        return
    _play_file(os.path.join(_base, "intro_" + name, "start.wav"))


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
    _play_file(_path(name))
