"""Setări salvate (nume, sunete) în %APPDATA%\\RobisGame\\setari.json."""
import json
import os
import tempfile

_cfg = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "RobisGame", "setari.json")
_data = None

MASCULINE_IN_A = {"mihnea", "luca", "toma", "horea", "sava", "costea", "ilia", "nicola", "vlaicu"}


def _load():
    global _data
    if _data is None:
        try:
            with open(_cfg, encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
    return _data


def get(key, default=None):
    return _load().get(key, default)


def put(key, value):
    d = _load()
    d[key] = value
    try:
        os.makedirs(os.path.dirname(_cfg), exist_ok=True)
        with open(_cfg, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def player_name():
    return get("nume") or "Jucător"


def gen(name):
    """Genitivul: Miruna -> Mirunei, Razvan -> lui Razvan."""
    low = name.strip().lower()
    if low.endswith("a") and low not in MASCULINE_IN_A and len(low) > 1:
        return name.strip()[:-1] + "ei"
    return "lui " + name.strip()
