"""Fereastra principală și ecranele accesibile (liste native, citite de NVDA)."""
import re

import wx

import sounds
import speech


class MainFrame(wx.Frame):
    def __init__(self, title):
        super().__init__(None, title=title, size=(760, 520))
        self.base_title = title
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.panel = None
        self.list = None
        self.items = []
        self.on_escape = None
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    # ---- ecran listă ----
    def show_menu(self, title, items, on_escape=None, selected=0):
        """items: listă de (text, funcție sau None). Primul element poate fi un mesaj."""
        old = self.panel
        p = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        lbl = wx.StaticText(p, label=title)
        lb = wx.ListBox(p, choices=[str(i[0]) for i in items], style=wx.LB_SINGLE)
        lb.SetName(title)
        if items:
            lb.SetSelection(max(0, min(selected, len(items) - 1)))
        lb.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._activate())
        lb.Bind(wx.EVT_LISTBOX, lambda e: sounds.play("move"))
        s.Add(lbl, 0, wx.ALL, 6)
        s.Add(lb, 1, wx.EXPAND | wx.ALL, 6)
        p.SetSizer(s)
        self.sizer.Add(p, 1, wx.EXPAND)
        if old is not None:
            self.sizer.Detach(old)
            old.Destroy()
        self.panel, self.list, self.items, self.on_escape = p, lb, items, on_escape
        self.repeat = str(items[0][0]) if items else title
        self.SetTitle(f"{title} - {self.base_title}")
        self.Layout()
        wx.CallAfter(self._focus)

    def _focus(self):
        if self.list:
            try:
                self.list.SetFocus()
            except RuntimeError:
                pass

    def _activate(self):
        if not self.list:
            return
        i = self.list.GetSelection()
        if 0 <= i < len(self.items):
            cb = self.items[i][1]
            if cb:
                sounds.play("select")
                wx.CallAfter(cb)

    def _on_key(self, e):
        k = e.GetKeyCode()
        focus = wx.Window.FindFocus()
        if k == wx.WXK_F1 and self.list:
            self.repeat_message()
            return
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focus is self.list and self.list:
            self._activate()
            return
        if k == wx.WXK_ESCAPE and self.on_escape and focus is self.list:
            sounds.play("back")
            wx.CallAfter(self.on_escape)
            return
        if focus is self.list and self.list and k in (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_HOME, wx.WXK_END):
            i, n = self.list.GetSelection(), self.list.GetCount()
            if (k in (wx.WXK_UP, wx.WXK_HOME) and i <= 0) or (k in (wx.WXK_DOWN, wx.WXK_END) and i >= n - 1):
                sounds.play("edge")
        e.Skip()

    def repeat_message(self):
        """F1: citește din nou mesajul sau întrebarea de pe ecran."""
        if not speech.speak(self.repeat):
            try:
                self.list.SetSelection(0)
                self.list.SetFocus()
            except RuntimeError:
                pass

    def show_lines(self, title, text, on_escape):
        """Text lung afișat ca listă, câte o propoziție pe rând. Escape te întoarce."""
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        items = [(f"{title}. Mergi cu săgeata jos, câte o propoziție. Escape te întoarce.", None)]
        items += [(p, None) for p in parts]
        self.show_menu(title, items, on_escape=on_escape)

    # ---- dialoguri (NVDA citește automat textul dialogului) ----
    def ask_text(self, message, caption="Răspuns"):
        dlg = wx.TextEntryDialog(self, message, caption)

        def on_key(e):
            if e.GetKeyCode() == wx.WXK_F1:
                speech.speak(message)
            else:
                e.Skip()
        dlg.Bind(wx.EVT_CHAR_HOOK, on_key)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                return dlg.GetValue()
            return None
        finally:
            dlg.Destroy()

    def ask_multi(self, message, caption, choices, selected):
        dlg = wx.MultiChoiceDialog(self, message, caption, choices)
        dlg.SetSelections(selected)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                return dlg.GetSelections()
            return None
        finally:
            dlg.Destroy()

    def message(self, text, caption="Informație"):
        wx.MessageBox(text, caption, wx.OK | wx.ICON_INFORMATION, self)

    def confirm(self, text, caption="Confirmare"):
        return wx.MessageBox(text, caption, wx.YES_NO | wx.ICON_QUESTION, self) == wx.YES
