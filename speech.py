"""Vorbire prin NVDA (nvdaControllerClient). Dacă NVDA nu e pornit, nu face nimic."""
import ctypes
import os
import sys

_dll = None


def _load():
    global _dll
    if _dll is not None:
        return _dll
    _dll = False
    if os.name != "nt":
        return _dll
    bases = [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(sys.executable)),
             os.path.dirname(os.path.abspath(__file__))]
    for base in bases:
        if not base:
            continue
        for name in ("nvdaControllerClient64.dll", "nvdaControllerClient.dll"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                try:
                    _dll = ctypes.WinDLL(p)
                    return _dll
                except OSError:
                    pass
    return _dll


def speak(text, interrupt=True):
    d = _load()
    if not d:
        return False
    try:
        if d.nvdaController_testIfRunning() != 0:
            return False
        if interrupt:
            d.nvdaController_cancelSpeech()
        d.nvdaController_speakText(ctypes.c_wchar_p(text))
        return True
    except Exception:
        return False
