"""Versiunea aplicației. BUILD este completat automat de GitHub la fiecare compilare."""
try:
    from build_info import BUILD
except ImportError:
    BUILD = 0

VERSION = f"1.0.{BUILD}"
REPO = "OWNER/jocuri-accesibile"
ASSET_NAME = "JocuriAccesibile.exe"


def as_tuple(v):
    v = v.lstrip("vV")
    out = []
    for part in v.split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out)
