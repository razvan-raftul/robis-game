"""Robi's game - meniul principal."""
import sys
import threading

import wx

import sounds
import speech
import updater
from remi_ui import RemiUI
from triviador import TriviadorUI
from ui import MainFrame
from version import APP_NAME, VERSION


class App:
    def __init__(self):
        self.f = MainFrame(f"{APP_NAME} {VERSION}")
        self.f.Show()
        self.f.Raise()
        updater.cleanup_old()
        sounds.init()
        self.main_menu()
        if updater.is_frozen():
            threading.Thread(target=self.check_update, args=(False,), daemon=True).start()

    def main_menu(self, selected=0):
        stare = "pornite" if sounds.enabled else "oprite"
        self.f.show_menu("Meniu principal", [
            ("Jocuri", self.games_menu),
            (f"Sunete în meniu: {stare}", self.toggle_sounds),
            ("Verifică actualizările", lambda: threading.Thread(
                target=self.check_update, args=(True,), daemon=True).start()),
            ("Despre", self.about),
        ], on_escape=self.f.Close, selected=selected)

    def toggle_sounds(self):
        sounds.set_enabled(not sounds.enabled)
        self.main_menu(selected=1)

    def games_menu(self):
        self.f.show_menu("Jocuri", [
            ("Triviador", lambda: TriviadorUI(self.f, self.games_menu)),
            ("Remi pe tablă", lambda: RemiUI(self.f, "tabla", self.games_menu)),
            ("Remi etalat", lambda: RemiUI(self.f, "etalat", self.games_menu)),
        ], on_escape=self.main_menu)

    def about(self):
        self.f.message(f"{APP_NAME}, versiunea {VERSION}. Se actualizează singur de pe GitHub. "
                       "În liste te miști cu săgețile, Enter alege, Escape te duce înapoi. Din meniul principal ieși cu Escape sau Alt F4.", "Despre")

    # ----- actualizare -----
    def check_update(self, manual):
        try:
            info = updater.check_latest() if updater.is_frozen() else None
        except Exception:
            info = None
            if manual:
                wx.CallAfter(self.f.message, "Nu am putut verifica actualizările. Verifică internetul.")
                return
        if not info:
            if manual:
                txt = ("Ai ultima versiune." if updater.is_frozen()
                       else "Actualizarea funcționează doar în versiunea .exe.")
                wx.CallAfter(self.f.message, txt)
            return
        wx.CallAfter(self.start_update, info)

    def start_update(self, info):
        tag, url, size = info
        self.f.show_menu("Actualizare", [("Se actualizează", None)])
        speech.speak("Se actualizează")
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
        if self.f.list:
            try:
                self.f.list.SetString(0, f"Se actualizează {pct}%")
            except RuntimeError:
                pass
        if pct >= self.last_spoken + 10 or pct == 100:
            self.last_spoken = pct - pct % 10
            speech.speak(f"{pct}%")

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
