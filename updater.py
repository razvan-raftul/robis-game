"""Actualizare automată de pe GitHub Releases."""
import json
import os
import ssl
import sys
import urllib.request

from version import VERSION, REPO, ASSET_NAME, as_tuple

UA = {"User-Agent": "JocuriAccesibile-updater", "Accept": "application/vnd.github+json"}


def _ctx():
    """Certificatele vin cu aplicația (certifi), ca să meargă și pe calculatoare noi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url, timeout, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA["User-Agent"]})
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_ctx())
    except ssl.SSLError:
        return urllib.request.urlopen(req, timeout=timeout)


def is_frozen():
    return getattr(sys, "frozen", False)


def exe_path():
    return os.path.abspath(sys.executable)


def cleanup_old():
    """Șterge versiunea veche rămasă după o actualizare."""
    if not is_frozen():
        return
    old = exe_path() + ".old"
    if os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass


def check_latest(timeout=8):
    """Întoarce (tag, url_descărcare, mărime) dacă există o versiune mai nouă, altfel None."""
    try:
        with _open(f"https://api.github.com/repos/{REPO}/releases/latest", timeout, UA) as r:
            data = json.loads(r.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        if as_tuple(tag) <= as_tuple(VERSION):
            return None
        for a in data.get("assets", []):
            if a.get("name") == ASSET_NAME:
                return tag, a["browser_download_url"], a.get("size", 0)
        return None
    except Exception:
        # varianta de rezervă: pagina obișnuită de GitHub, fără API
        with _open(f"https://github.com/{REPO}/releases/latest", timeout) as r:
            final = r.geturl()
        tag = final.rstrip("/").rsplit("/", 1)[-1]
        if "/tag/" not in final or as_tuple(tag) <= as_tuple(VERSION):
            return None
        return tag, f"https://github.com/{REPO}/releases/download/{tag}/{ASSET_NAME}", 0


def download_and_replace(url, size, progress):
    """Descarcă noul exe și îl pune în locul celui vechi. progress(procent) e apelat la fiecare procent nou."""
    target = exe_path()
    new_path = target + ".new"
    with _open(url, 30) as r, open(new_path, "wb") as f:
        total = int(r.headers.get("Content-Length") or size or 0)
        done = 0
        last = -1
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = min(100, done * 100 // total)
                if pct != last:
                    last = pct
                    progress(pct)
    if total and os.path.getsize(new_path) < total:
        os.remove(new_path)
        raise IOError("Descărcare incompletă")
    old = target + ".old"
    if os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass
    os.replace(target, old)      # Windows permite redenumirea exe-ului care rulează
    os.replace(new_path, target)
    return target
