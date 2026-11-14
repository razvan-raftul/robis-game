"""Ecranele accesibile pentru Remi pe tablă și Remi etalat."""
from remi import RemiGame
from remi_core import best_partition, closing_plan, sort_tiles, used_ids

TITLURI = {"tabla": "Remi pe tablă", "etalat": "Remi etalat"}

REGULI = {
    "tabla": (
        "Remi pe tablă se joacă cu 106 piese: numerele de la 1 la 13 în patru culori, roșu, galben, albastru și negru, "
        "câte două din fiecare, plus 2 jokeri. Fiecare primește 14 piese, iar cel care începe primește 15 și doar aruncă. "
        "La rândul tău tragi o piesă din pachet sau iei piesa aruncată de jucătorul dinainte, apoi arunci o piesă. "
        "Formațiile sunt suite, adică cel puțin 3 numere consecutive de aceeași culoare, unde 1 poate sta înainte de 2 sau după 13, "
        "și terțe sau quarte, adică același număr în culori diferite. Jokerul ține locul oricărei piese. "
        "Închizi când toate cele 14 piese rămase îți formează formații și arunci a cincisprezecea. "
        "Cine închide primește 100 de puncte, ceilalți pierd valoarea pieselor nefolosite: 5 pentru 2 până la 9, 10 pentru 10 până la 13, "
        "25 pentru 1 și 50 pentru joker. Cine are atuul primește 50 de puncte. "
        "Opțiunea Formații posibile îți citește cea mai bună aranjare a pieselor tale."),
    "etalat": (
        "Remi etalat se joacă cu aceleași 106 piese. Fiecare primește 14 piese, cel care începe 15. "
        "La rând tragi din pachet sau iei piesa aruncată, dar pe aceasta o poți lua doar dacă o folosești imediat pe masă. "
        "Etalarea înseamnă să pui formații pe masă. Prima etalare se poate face doar după ce toți au jucat o tură, "
        "trebuie să aibă cel puțin 45 de puncte și cel puțin o suită, sau o terță de 1. "
        "Valori la etalare: 2 până la 9 câte 5 puncte, 10 până la 13 câte 10, 1 în suita 1 2 3 face 5, în suita 12 13 1 face 10, "
        "iar în terță face 25. Jokerul ia valoarea piesei înlocuite. "
        "După ce te-ai etalat poți pune formații noi și poți lipi piese la orice formație de pe masă. "
        "Închizi când arunci ultima piesă din mână. La final primești punctele etalate minus piesele rămase în mână, "
        "cine nu s-a etalat pierde 100, cine închide primește 50, iar atuul aduce 50.")}


class RemiUI:
    def __init__(self, frame, variant, back):
        self.f, self.variant, self.back = frame, variant, back
        self.title = TITLURI[variant]
        self.n_ai = 2
        self.g = None
        self.setup()

    def setup(self):
        self.f.show_menu(self.title, [
            (f"{self.title}. Joci cu {self.n_ai} {'adversar' if self.n_ai == 1 else 'adversari'} pe calculator.", None),
            ("Începe jocul", self.start),
            ("Alege numărul de adversari", self.pick_n),
            ("Reguli", self.rules),
            ("Înapoi la jocuri", self.back),
        ], on_escape=self.back, selected=1)

    def pick_n(self):
        items = [("Câți adversari vrei?", None)]
        for n in (1, 2, 3):
            items.append((f"{n} {'adversar' if n == 1 else 'adversari'}", lambda n=n: self._set_n(n)))
        self.f.show_menu("Adversari", items, on_escape=self.setup, selected=self.n_ai)

    def _set_n(self, n):
        self.n_ai = n
        self.setup()

    def rules(self):
        self.f.message(REGULI[self.variant], "Reguli " + self.title)
        self.setup()

    # ---------- desfășurare ----------
    def start(self):
        self.g = RemiGame(self.variant, self.n_ai)
        self.new_round()

    def new_round(self):
        txt = self.g.new_round()
        self.run_ai([txt])

    def run_ai(self, log):
        g = self.g
        while not g.over and not g.cur().human:
            log.append(g.ai_turn())
        if g.over:
            return self.round_end(" ".join(log))
        if g.state == "draw":
            self.turn_menu(" ".join(log))
        else:
            self.action_menu(" ".join(log) + " Ai 15 piese, începi tu: aruncă o piesă.")

    def info(self):
        g = self.g
        me = g.players[0]
        d = f"Piesa aruncată: {g.discard.name()}." if g.discard else "Nu e nicio piesă aruncată."
        return f"Ai {len(me.hand)} piese. {d} În pachet: {len(g.deck)}."

    def common_items(self, back):
        items = [("Piesele mele", lambda: self.show_hand(back)),
                 ("Formații posibile", lambda: self.show_possible(back))]
        if self.g.etalat_mode:
            items.append(("Masa", lambda: self.show_table(back)))
        items += [("Scorul", lambda: back(self.scores())),
                  ("Ieși din joc", self.quit)]
        return items

    def turn_menu(self, msg):
        g = self.g
        self.cur_back = self.turn_menu
        items = [(f"{msg} E rândul tău. {self.info()}".strip(), None),
                 (f"Trage o piesă din pachet", self.do_draw)]
        if g.discard is not None:
            plan = g.discard_use_plan(0)
            if plan:
                extra = "" if plan[0] == "free" else ", o folosești imediat"
                items.append((f"Ia piesa aruncată: {g.discard.name()}{extra}", self.do_take))
        items += self.common_items(self.turn_menu)
        self.f.show_menu(self.title, items, on_escape=self.quit, selected=0)

    def do_draw(self):
        t = self.g.draw(0)
        if t is None:
            return self.round_end(self.g.summary)
        self.action_menu(f"Ai tras {t.name()}.")

    def do_take(self):
        r = self.g.take_discard(0)
        if r is None:
            return self.turn_menu("Nu poți lua piesa aruncată.")
        self.action_menu("Tu " + r + ".")

    def action_menu(self, msg):
        g = self.g
        items = [(f"{msg} {self.info()} Acum trebuie să arunci o piesă.", None),
                 ("Aruncă o piesă", self.pick_discard)]
        if not g.etalat_mode:
            if closing_plan(g.players[0].hand):
                items.append(("Închide jocul", self.do_close))
        else:
            plan = g.lay_plan(0)
            if plan:
                lbl = "Etalează" if not g.players[0].etalat else "Pune formații noi pe masă"
                items.append((f"{lbl}: {sum(f.points() for f in plan)} de puncte", lambda: self.do_lay(plan)))
            if g.attach_options(0):
                items.append(("Lipește o piesă pe masă", self.pick_attach))
        items += self.common_items(self.action_menu)
        self.f.show_menu(self.title, items, on_escape=self.quit, selected=0)

    def pick_discard(self):
        hand = self.g.players[0].hand
        items = [(f"Alege piesa de aruncat cu Enter. Ai {len(hand)} piese.", None)]
        items += [(t.name(), lambda t=t: self.do_discard(t)) for t in sort_tiles(hand)]
        self.f.show_menu("Aruncă", items, on_escape=lambda: self.action_menu("Nu ai aruncat încă."), selected=1)

    def do_discard(self, t):
        g = self.g
        g.do_discard(0, t)
        if g.over:
            return self.round_end(f"Ai aruncat {t.name()} și ai închis! " + g.summary)
        self.run_ai([f"Ai aruncat {t.name()}."])

    def do_close(self):
        g = self.g
        plan = closing_plan(g.players[0].hand)
        if not plan:
            return self.action_menu("Nu poți închide.")
        t, fs = plan
        txt = "Formațiile tale: " + ". ".join(f.name() for f in fs) + f". Arunci {t.name()}. Închizi?"
        if self.f.confirm(txt, "Închidere"):
            g.close_tabla(0)
            return self.round_end("Ai închis! " + g.summary)
        self.action_menu("Nu ai închis.")

    def do_lay(self, plan):
        g = self.g
        txt = ". ".join(f"{f.name()}, {f.points()} puncte" for f in plan)
        if not self.f.confirm(f"Pui pe masă: {txt}. Total {sum(f.points() for f in plan)} de puncte. Continui?",
                              "Etalare"):
            return self.action_menu("Nu ai pus nimic pe masă.")
        pts = g.lay(0, plan)
        self.action_menu(f"Ai pus pe masă formații de {pts} de puncte.")

    def pick_attach(self):
        g = self.g
        opts = g.attach_options(0)
        items = [("Alege ce piesă lipești și unde.", None)]
        for t, fm in opts:
            owner = "ta" if fm.owner == 0 else f"lui {g.players[fm.owner].name}"
            items.append((f"{t.name()} la {fm.name()}, formația {owner}", lambda t=t, fm=fm: self.do_attach(t, fm)))
        self.f.show_menu("Lipire", items, on_escape=lambda: self.action_menu("Nu ai lipit nimic."), selected=1)

    def do_attach(self, t, fm):
        pts = self.g.attach(0, t, fm)
        self.action_menu(f"Ai lipit {t.name()}, {pts} de puncte.")

    # ---------- informații ----------
    def show_hand(self, back):
        g = self.g
        hand = sort_tiles(g.players[0].hand)
        items = [(f"Ai {len(hand)} piese. Atuul este {g.atu.name()}. Escape pentru întoarcere.", None)]
        items += [(t.name(), None) for t in hand]
        self.f.show_menu("Piesele mele", items, on_escape=lambda: back("Te-ai întors."))

    def show_possible(self, back):
        hand = self.g.players[0].hand
        mode = "count" if not self.g.etalat_mode else "points"
        _, fs = best_partition(hand, mode)
        used = used_ids(fs)
        left = [t for t in sort_tiles(hand) if t.id not in used]
        items = [(f"Formații posibile: {len(fs)}. Escape pentru întoarcere.", None)]
        items += [(f"{f.name()}, {f.points()} puncte", None) for f in fs]
        items.append(("Piese rămase în afara formațiilor: " + (", ".join(t.name() for t in left) or "niciuna"), None))
        self.f.show_menu("Formații posibile", items, on_escape=lambda: back("Te-ai întors."))

    def show_table(self, back):
        g = self.g
        items = [(f"Pe masă sunt {len(g.table)} formații. Escape pentru întoarcere.", None)]
        for fm in g.table:
            owner = "a ta" if fm.owner == 0 else f"a lui {g.players[fm.owner].name}"
            items.append((f"{fm.name()}, {owner}", None))
        for p in g.players[1:]:
            items.append((f"{p.name} are {len(p.hand)} piese, {'etalat' if p.etalat else 'neetalat'}", None))
        self.f.show_menu("Masa", items, on_escape=lambda: back("Te-ai întors."))

    def scores(self):
        return "Scor total: " + ", ".join(f"{p.name} {p.score}" for p in self.g.players) + "."

    def quit(self):
        if self.f.confirm(f"Sigur ieși din {self.title}?"):
            self.setup()

    def round_end(self, msg):
        g = self.g
        best = max(g.players, key=lambda p: p.score)
        self.f.show_menu(self.title, [
            (f"Runda s-a terminat. {msg} Pe primul loc: {best.name}.", None),
            ("Rundă nouă", self.new_round),
            ("Joc nou, scorul de la zero", self.start),
            ("Înapoi la jocuri", self.back),
        ], on_escape=self.setup, selected=0)
