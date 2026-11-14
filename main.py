"""Robi's game - meniul principal."""
import sys
import threading

import wx

import settings
import sounds
import speech
import updater
from remi_ui import RemiUI
from triviador import TriviadorUI
from ui import MainFrame
from version import APP_NAME, VERSION


class App:
    def __init__(self):
        self.f = MainFrame(APP_NAME)
        self.f.Show()
        self.f.Raise()
        updater.cleanup_old()
        sounds.init()
        sounds.play("start")
        self.f.Bind(wx.EVT_CLOSE, self.on_close)
        self.main_menu()
        if not settings.get("nume"):
            wx.CallAfter(self.first_name)
        if updater.is_frozen():
            threading.Thread(target=self.check_update, args=(False,), daemon=True).start()

    def on_close(self, e):
        self.f.Hide()
        sounds.play_sync("exit")
        e.Skip()

    def main_menu(self, selected=0):
        self.f.hotkeys = {}
        self.f.show_menu("Meniu principal", [
            ("Jocuri", self.games_menu),
            ("Setări", self.settings_menu),
            ("Verifică actualizările", lambda: threading.Thread(
                target=self.check_update, args=(True,), daemon=True).start()),
        ], on_escape=self.f.Close, selected=selected,
            repeat="Meniul principal. Escape sau Alt F4 închide aplicația.")

    # ----- setări -----
    def first_name(self):
        for _ in range(3):
            name = self.ask_name("Bine ai venit în Robi's game! Scrie-ți numele, apoi apasă Enter. "
                                 "Îl poți schimba oricând din Setări.")
            if name:
                break
        if not name:
            settings.put("nume", "Jucător")
        self.main_menu()

    def ask_name(self, msg):
        text = self.f.ask_text(msg, "Numele tău")
        name = (text or "").strip()[:30]
        if name:
            settings.put("nume", name)
        return name

    def settings_menu(self, selected=0):
        stare = "pornite" if sounds.enabled else "oprite"
        self.f.show_menu("Setări", [
            (f"Numele tău: {settings.player_name()}", self.change_name),
            (f"Sunete: {stare}", self.toggle_sounds),
            (f"Schema de sunete: {sounds.scheme}", self.scheme_menu),
        ], on_escape=lambda: self.main_menu(selected=1), selected=selected)

    def scheme_menu(self):
        names = list(sounds.SCHEMES)
        self.f.show_menu("Schema de sunete", [(n, lambda n=n: self.set_scheme(n)) for n in names],
                         on_escape=lambda: self.settings_menu(selected=2),
                         selected=names.index(sounds.scheme) if sounds.scheme in names else 0,
                         repeat=f"Alege schema de sunete. Acum este {sounds.scheme}. Enter o alege și o ascultă.")

    def set_scheme(self, name):
        sounds.set_scheme(name)
        sounds.play("start")
        self.settings_menu(selected=2)

    def change_name(self):
        self.ask_name(f"Numele tău acum este {settings.player_name()}. Scrie numele nou și apasă Enter.")
        self.settings_menu(selected=0)

    def toggle_sounds(self):
        sounds.set_enabled(not sounds.enabled)
        self.settings_menu(selected=1)

    def games_menu(self):
        self.f.hotkeys = {}
        self.f.show_menu("Jocuri", [
            ("Triviador", lambda: TriviadorUI(self.f, self.games_menu)),
            ("Remi", lambda: RemiUI(self.f, self.games_menu)),
        ], on_escape=self.main_menu)

    # ----- actualizare -----
    def check_update(self, manual):
        try:
            info = updater.check_latest() if updater.is_frozen() else None
        except Exception as e:
            info = None
            if manual:
                wx.CallAfter(self.f.message, f"Nu am putut verifica actualizările. Motiv: {e}")
                return
        if not info:
            if manual:
                txt = (f"Ai ultima versiune, {VERSION}." if updater.is_frozen()
                       else "Actualizarea funcționează doar în versiunea .exe.")
                wx.CallAfter(self.f.message, txt)
            return
        wx.CallAfter(self.start_update, info)

    def start_update(self, info):
        tag, url, size = info
        self.f.show_progress("Se actualizează")
        self.last_spoken = 0

        def progress(pct):
            wx.CallAfter(self.on_progress, pct)

        def work():
            try:
                updater.download_and_replace(url, size, progress)
                wx.CallAfter(self.restart)
            except Exception:
                wx.CallAfter(self.update_failed)
        threading.Thread(target=work, daemon=True).start()

    def on_progress(self, pct):
        self.f.set_progress(pct)
        if pct >= self.last_spoken + 10:
            self.last_spoken = pct - pct % 10
            speech.speak(f"{self.last_spoken}%", interrupt=False)

    def update_failed(self):
        self.f.message("Actualizarea nu a reușit. Joci mai departe pe versiunea actuală.")
        self.main_menu()

    def restart(self):
        import subprocess
        try:
            import os
            env = dict(os.environ)
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            subprocess.Popen([updater.exe_path()], close_fds=True, env=env)
        finally:
            self.f.Destroy()
            sys.exit(0)


def main():
    app = wx.App(False)
    App()
    app.MainLoop()


if __name__ == "__main__":
    main()
