"""Triviador: cucerește teritorii răspunzând la întrebări."""
import difflib
import random
import re
import unicodedata

import wx

import settings
import sounds
from settings import gen

from trivia_data import CATEGORII, GRILA, NUMERICE

TERITORII = ["Alaska", "Canada", "Groenlanda", "Mexic", "Brazilia", "Argentina", "Islanda",
             "Marea Britanie", "Scandinavia", "Egipt", "Africa de Sud", "Siberia", "India",
             "China", "Japonia", "Indonezia", "Australia", "Noua Zeelandă"]
NUME_AI = ["Miruna", "Sara"]
DIFICULTATI = {"Ușor": (0.45, 0.35), "Mediu": (0.6, 0.2), "Greu": (0.75, 0.1)}
RUNDE_LUPTA = 5
LITERE = "ABCD"


class Player:
    def __init__(self, name, human=False):
        self.name, self.human, self.alive, self.bonus = name, human, True, 0


class Territory:
    def __init__(self, name):
        self.name, self.owner, self.value, self.base, self.towers = name, None, 0, False, 0


def fmt_num(x):
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}".replace(",", ".")
    return f"{x:.2f}".replace(".", ",")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def text_matches(given, correct):
    """Verifică un răspuns scris, iertând diacriticele, literele mari și micile greșeli."""
    a, c = norm(given), norm(correct)
    if not a:
        return False
    if a == c:
        return True
    na, nc = parse_num(given), parse_num(correct)
    if na is not None and nc is not None:
        return na == nc
    if len(a) >= 3 and set(a.split()) <= set(c.split()):
        return True
    return difflib.SequenceMatcher(None, a, c).ratio() >= 0.8


def parse_num(text):
    if text is None:
        return None
    t = text.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


class TriviadorGame:
    def __init__(self, cats, difficulty, rng=None, name="Jucător"):
        self.rng = rng or random.Random()
        self.p_ok, self.sd = DIFICULTATI[difficulty]
        self.players = [Player(name, True)] + [Player(n) for n in NUME_AI]
        mc = [q for q in GRILA if q[0] in cats] or list(GRILA)
        num = [q for q in NUMERICE if q[0] in cats] or list(NUMERICE)
        if len(num) < 6:
            num = num + [q for q in NUMERICE if q not in num]
        self.mc_pool, self.num_pool = mc, num
        self.mc_deck, self.num_deck = [], []
        names = TERITORII[:]
        self.rng.shuffle(names)
        self.terr = [Territory(n) for n in names]
        for i, p in enumerate(self.players):
            t = self.terr[i]
            t.owner, t.base, t.towers, t.value = i, True, 3, 1000

    def next_mc(self):
        if not self.mc_deck:
            self.mc_deck = self.mc_pool[:]
            self.rng.shuffle(self.mc_deck)
        cat, q, ok, wrong = self.mc_deck.pop()
        opts = [ok] + list(wrong)
        self.rng.shuffle(opts)
        return {"cat": cat, "q": q, "opts": opts, "ok": opts.index(ok)}

    def next_num(self):
        if not self.num_deck:
            self.num_deck = self.num_pool[:]
            self.rng.shuffle(self.num_deck)
        cat, q, ans = self.num_deck.pop()
        return {"cat": cat, "q": q, "ans": ans}

    def num_options(self, ans):
        """Patru variante pentru o întrebare cu număr, una fiind cea corectă."""
        is_int = float(ans).is_integer()
        is_year = is_int and 1000 <= ans <= 2100
        opts, tries = {ans}, 0
        while len(opts) < 4 and tries < 200:
            tries += 1
            if is_year:
                v = ans + self.rng.choice([-1, 1]) * self.rng.randint(3, 60)
            elif is_int and ans < 20:
                v = ans + self.rng.choice([-4, -3, -2, -1, 1, 2, 3, 4, 5])
            else:
                v = ans * self.rng.choice([0.5, 0.6, 0.7, 0.8, 1.2, 1.3, 1.5, 1.75, 2])
                v = round(v) if is_int else round(v, 2)
            if v > 0 and v != ans:
                opts.add(v)
        return sorted(opts)

    def ai_mc(self):
        return self.rng.random() < self.p_ok

    def ai_guess(self, ans):
        if 1000 <= ans <= 2100 and float(ans).is_integer():   # un an
            g = ans + self.rng.gauss(0, self.sd * 120)
        else:
            g = ans * (1 + self.rng.gauss(0, self.sd * 1.5))
            if ans > 0:
                g = max(g, 0)
        return round(g) if float(ans).is_integer() else round(g, 2)

    def free(self):
        return [i for i, t in enumerate(self.terr) if t.owner is None]

    def owned(self, pi):
        return [i for i, t in enumerate(self.terr) if t.owner == pi]

    def score(self, pi):
        return sum(t.value for t in self.terr if t.owner == pi) + self.players[pi].bonus

    def alive(self):
        return [i for i, p in enumerate(self.players) if p.alive]

    def rank(self, guesses, ans):
        """guesses: {pi: valoare sau None}. Întoarce lista de jucători, cel mai aproape primul."""
        def key(pi):
            g = guesses[pi]
            return (float("inf") if g is None else abs(g - ans), self.rng.random())
        return sorted(guesses, key=key)

    def take(self, pi, ti, value=200):
        t = self.terr[ti]
        t.owner, t.value = pi, value

    def ai_pick_free(self):
        return self.rng.choice(self.free())

    def ai_target(self, att):
        opts = [i for i, t in enumerate(self.terr) if t.owner not in (None, att)]
        nonbase = [i for i in opts if not self.terr[i].base]
        if nonbase and self.rng.random() < 0.75:
            return self.rng.choice(nonbase)
        return self.rng.choice(opts)

    def resolve(self, att, ti, att_wins, defense_bonus):
        """Aplică rezultatul unui atac. Întoarce textul rezultatului."""
        t = self.terr[ti]
        d = t.owner
        A, D = self.players[att].name, self.players[d].name
        if not att_wins:
            if defense_bonus:
                self.players[d].bonus += 100
                return f"{D} a apărat {t.name} și primește 100 de puncte."
            return f"{t.name} rămâne la {D}."
        if t.base:
            t.towers -= 1
            if t.towers > 0:
                return f"{A} a dărâmat un turn al bazei {gen(D)}. Mai are {t.towers}."
            # baza cucerită: atacatorul ia tot
            for x in self.terr:
                if x.owner == d:
                    x.owner = att
                    if x.base:
                        x.base, x.value, x.towers = False, 1000, 0
            self.players[d].alive = False
            return f"{A} a cucerit baza {gen(D)} și i-a luat toate teritoriile. {D} iese din joc."
        t.owner, t.value = att, 400
        return f"{A} a cucerit {t.name}, care acum valorează 400 de puncte."

    def describe(self, ti):
        t = self.terr[ti]
        who = "nimeni" if t.owner is None else self.players[t.owner].name
        if t.base:
            return f"Baza {gen(who)} ({t.name}), {t.towers} turnuri, 1000 de puncte"
        if t.owner is None:
            return f"{t.name}, liber"
        return f"{t.name}, al {gen(who)}, {t.value} de puncte"

    def scores_lines(self):
        out = []
        for i in sorted(range(len(self.players)), key=lambda i: -self.score(i)):
            p = self.players[i]
            extra = "" if p.alive else ", eliminat"
            out.append(f"{p.name}: {self.score(i)} puncte, {len(self.owned(i))} teritorii{extra}")
        return out

    def scores_text(self):
        parts = []
        for i in sorted(range(len(self.players)), key=lambda i: -self.score(i)):
            p = self.players[i]
            extra = "" if p.alive else ", eliminat"
            parts.append(f"{p.name} {self.score(i)} puncte, {len(self.owned(i))} teritorii{extra}")
        return ". ".join(parts) + "."


class TriviadorUI:
    def __init__(self, frame, back):
        self.f, self.back = frame, back
        self.cats, self.diff = [], "Mediu"
        self.num_mode = settings.get("mod_numeric", "variante")
        self.f.hotkeys = {}
        self.setup()

    # ---------- pregătire ----------
    def setup(self):
        if not self.cats:
            alese = "niciuna, alege-le înainte să începi"
        elif len(self.cats) == len(CATEGORII):
            alese = "toate"
        else:
            alese = ", ".join(self.cats)
        mod = "grilă" if self.num_mode == "variante" else "scris"
        txt = (f"Triviador. Categorii alese: {alese}. Dificultate adversari: {self.diff}. "
               f"Modalitatea jocului: {mod}.")
        self.f.show_menu("Triviador", [
            ("Începe jocul", self.start),
            ("Alege categoriile de întrebări", self.pick_cats),
            ("Alege dificultatea adversarilor", self.pick_diff),
            ("Alege modalitatea jocului", self.pick_mode),
            ("Ajutor", self.help_menu),
        ], on_escape=self.back, selected=0, repeat=txt)

    def pick_cats(self):
        choices = ["Toate"] + CATEGORII
        sel = [i + 1 for i, c in enumerate(CATEGORII) if c in self.cats]
        r = self.f.ask_multi("Bifează cu spațiu categoriile dorite, apoi apasă Enter. "
                             "Prima opțiune, Toate, le alege pe toate.", "Categorii", choices, sel)
        if r is not None:
            if 0 in r:
                self.cats = list(CATEGORII)
            else:
                self.cats = [CATEGORII[i - 1] for i in r]
        self.setup()

    def pick_mode(self):
        cur = "grilă" if self.num_mode == "variante" else "scris"
        self.f.show_menu("Modalitatea jocului", [
            ("Grilă, alegi răspunsul din variante", lambda: self._set_mode("variante")),
            ("Scris, scrii tu fiecare răspuns", lambda: self._set_mode("scriu")),
        ], on_escape=self.setup, selected=0 if self.num_mode == "variante" else 1,
            repeat=f"Alege modalitatea jocului. Acum este {cur}.")

    def _set_mode(self, mode):
        self.num_mode = mode
        settings.put("mod_numeric", mode)
        self.setup()

    def ask_number(self, msg, q, on_value):
        """Cere răspunsul la o întrebare cu număr, cu variante sau scris, după setare."""
        if self.num_mode == "variante":
            items = [(msg, None)]
            for k, v in enumerate(self.g.num_options(q["ans"])):
                items.append((f"{LITERE[k]}: {fmt_num(v)}", lambda v=v: on_value(v)))
            self.f.show_menu("Întrebare", items, on_escape=self.quit, selected=0)
            return
        text_msg = msg + " Scrie răspunsul."
        val = None
        while True:
            text = self.f.ask_text(text_msg, "Întrebare")
            if text is None:
                break
            val = parse_num(text)
            if val is not None:
                break
            text_msg = "Nu am înțeles numărul. " + q["q"]
        on_value(val)

    def pick_diff(self):
        items = [(d, lambda d=d: self._set_diff(d)) for d in DIFICULTATI]
        self.f.show_menu("Dificultate", items, on_escape=self.setup, selected=list(DIFICULTATI).index(self.diff),
                         repeat=f"Alege cât de buni sunt adversarii. Acum: {self.diff}.")

    def _set_diff(self, d):
        self.diff = d
        self.setup()

    def help_menu(self, selected=0):
        self.f.show_menu("Ajutor", [
            ("Cum se joacă", self.help),
            ("Comenzi de tastatură", self.keys_help),
        ], on_escape=self.setup, selected=selected, repeat="Ajutor pentru Triviador.")

    def keys_help(self):
        self.f.show_lines(
            "Comenzi de tastatură",
            "Săgețile sus și jos te mută prin liste. Enter alege opțiunea. "
            "Escape te duce înapoi, iar în timpul jocului te întreabă dacă vrei să ieși. "
            "F1 îți citește din nou întrebarea sau ce ai de făcut pe ecranul curent. "
            "F2 îți arată scorul. F3 îți arată harta cu teritoriile. "
            "Când scrii un răspuns, apeși Enter ca să-l trimiți. Alt F4 închide aplicația.",
            lambda: self.help_menu(1))

    def help(self):
        self.f.show_lines(
            "Cum se joacă Triviador",
            "Joci cu Miruna și Sara. Fiecare are o bază cu 3 turnuri, care valorează 1000 de puncte. "
            "Întâi urmează extinderea: la fiecare rundă primiți toți aceeași întrebare. "
            "Cine răspunde corect sau cel mai aproape de răspuns alege 2 teritorii libere, al doilea alege unul. Un teritoriu luat așa valorează 200. "
            "Din Alege modalitatea jocului alegi Grilă, ca să alegi fiecare răspuns din variante, sau Scris, ca să scrii tu fiecare răspuns. "
            f"Apoi urmează {RUNDE_LUPTA} runde de luptă. Pe rând, fiecare atacă un teritoriu al altcuiva. "
            "Atacatorul și apărătorul răspund la aceeași întrebare. Dacă doar atacatorul răspunde bine, cucerește teritoriul, "
            "care urcă la 400 de puncte. Dacă doar apărătorul răspunde bine, primește 100 de puncte. "
            "Dacă amândoi răspund bine, mai urmează o întrebare de departajare. O bază cade după 3 atacuri câștigate, "
            "iar cel care o cucerește ia toate teritoriile proprietarului. Câștigă cine are cele mai multe puncte la final.",
            lambda: self.help_menu(0))

    # ---------- joc ----------
    def start(self):
        if not self.cats:
            self.pick_cats()
            if not self.cats:
                return
        self.g = TriviadorGame(self.cats, self.diff, name=settings.player_name())
        self.f.hotkeys = {wx.WXK_F2: self.show_scores, wx.WXK_F3: self.show_map}
        g = self.g
        bases = ". ".join(f"Baza {gen(g.players[i].name)} este {g.terr[i].name}" for i in range(3))
        self.status(f"Jocul începe. {bases}. Urmează extinderea.", self.expansion_round)

    def status(self, msg, cont):
        self.cont = cont
        self.f.show_menu("Triviador", [
            (msg, None),
            ("Continuă", cont),
        ], on_escape=self.quit, selected=0)

    def show_map(self):
        self.f.show_overlay("Harta", [self.g.describe(i) for i in range(len(self.g.terr))])

    def show_scores(self):
        self.f.show_overlay("Scorul", self.g.scores_lines())

    def quit(self):
        if self.f.confirm("Sigur ieși din jocul de Triviador?"):
            self.setup()

    # ----- extindere -----
    def expansion_round(self):
        g = self.g
        if not g.free():
            self.battle_start()
            return
        q = g.next_num()
        msg = f"Extindere, {len(g.free())} teritorii libere. Categoria {q['cat']}. {q['q']}"
        self.ask_number(msg, q, lambda val: self.expansion_result(q, val))

    def expansion_result(self, q, val):
        g = self.g
        guesses = {0: val}
        for i in (1, 2):
            guesses[i] = g.ai_guess(q["ans"])
        order = g.rank(guesses, q["ans"])
        sounds.play("correct" if order[0] == 0 else ("wrong" if order[-1] == 0 else "select"))
        txt = f"Răspunsul corect: {fmt_num(q['ans'])}. "
        txt += ", ".join(f"{g.players[i].name} {'fără răspuns' if guesses[i] is None else fmt_num(guesses[i])}"
                         for i in range(3)) + ". "
        txt += f"Primul este {g.players[order[0]].name}, al doilea {g.players[order[1]].name}."
        self.picks = [order[0], order[0], order[1]]
        self.pick_log = []
        self.status(txt, self.process_picks)

    def process_picks(self):
        g = self.g
        while self.picks and g.free():
            pi = self.picks[0]
            if g.players[pi].human:
                items = [(f"Alege un teritoriu liber. Mai ai {self.picks.count(0)} de ales.", None)]
                items += [(g.terr[i].name, lambda i=i: self._human_pick(i)) for i in g.free()]
                self.f.show_menu("Alege teritoriul", items, on_escape=self.quit, selected=1)
                return
            ti = g.ai_pick_free()
            g.take(pi, ti)
            self.pick_log.append(f"{g.players[pi].name} a luat {g.terr[ti].name}")
            self.picks.pop(0)
        msg = (". ".join(self.pick_log) + ". ") if self.pick_log else ""
        self.status(msg + f"Mai sunt {len(g.free())} teritorii libere.", self.expansion_round)

    def _human_pick(self, ti):
        self.g.take(0, ti)
        self.pick_log.append(f"Ai luat {self.g.terr[ti].name}")
        self.picks.pop(0)
        self.process_picks()

    # ----- luptă -----
    def battle_start(self):
        self.round = 0
        self.queue = []
        self.status("Toate teritoriile au fost împărțite. Începe lupta. " + self.g.scores_text(),
                    self.next_attack)

    def next_attack(self):
        g = self.g
        if len(g.alive()) <= 1:
            return self.finish()
        while not self.queue:
            self.round += 1
            if self.round > RUNDE_LUPTA:
                return self.finish()
            alive = g.alive()
            k = (self.round - 1) % len(alive)
            self.queue = alive[k:] + alive[:k]
        att = self.queue.pop(0)
        if not g.players[att].alive:
            return self.next_attack()
        if g.players[att].human:
            items = [(f"Runda {self.round} din {RUNDE_LUPTA}. Tu ataci. Alege ținta. Ai {g.score(0)} puncte.", None)]
            for i, t in enumerate(g.terr):
                if t.owner not in (None, 0):
                    items.append((g.describe(i), lambda i=i: self.attack(0, i)))
            self.f.show_menu("Atacul tău", items, on_escape=self.quit, selected=1)
        else:
            self.attack(att, g.ai_target(att))

    def attack(self, att, ti):
        g = self.g
        d = g.terr[ti].owner
        self.cur = (att, ti, d)
        q = g.next_mc()
        self.cur_q = q
        A, D, T = g.players[att].name, g.players[d].name, g.terr[ti].name
        if att == 0:
            intro = f"Ataci {T}, apărat de {D}."
        elif d == 0:
            intro = f"{A} atacă {T}, teritoriul tău."
        else:
            # oamenii nu sunt implicați: simulăm
            a_ok, d_ok = g.ai_mc(), g.ai_mc()
            return self.after_mc(a_ok, d_ok, f"{A} atacă {T}, de la {D}. ", None)
        if self.num_mode == "scriu":
            text = self.f.ask_text(f"{intro} Categoria {q['cat']}. {q['q']} Scrie răspunsul.", "Întrebare")
            corect = q["opts"][q["ok"]]
            return self._answer_result(text is not None and text_matches(text, corect))
        items = [(f"{intro} Categoria {q['cat']}. {q['q']}", None)]
        for k, o in enumerate(q["opts"]):
            items.append((f"{LITERE[k]}: {o}", lambda k=k: self._answer(k)))
        self.f.show_menu("Întrebare", items, on_escape=self.quit, selected=0)

    def _answer(self, k):
        self._answer_result(k == self.cur_q["ok"])

    def _answer_result(self, me_ok):
        g, q = self.g, self.cur_q
        att, ti, d = self.cur
        sounds.play("correct" if me_ok else "wrong")
        other_ok = g.ai_mc()
        a_ok, d_ok = (me_ok, other_ok) if att == 0 else (other_ok, me_ok)
        corect = q["opts"][q["ok"]]
        head = ("Corect! " if me_ok else f"Greșit. Răspunsul corect era {corect}. ")
        other = g.players[d if att == 0 else att].name
        head += f"{other} a răspuns {'corect' if other_ok else 'greșit'}. "
        self.after_mc(a_ok, d_ok, head, None)

    def after_mc(self, a_ok, d_ok, head, _):
        g = self.g
        att, ti, d = self.cur
        if a_ok and d_ok:
            return self.tiebreak(head)
        txt = g.resolve(att, ti, a_ok and not d_ok, d_ok and not a_ok)
        self.status(head + txt, self.next_attack)

    def tiebreak(self, head):
        g = self.g
        att, ti, d = self.cur
        q = g.next_num()
        if 0 in (att, d):
            msg = f"{head}Amândoi ați răspuns corect. Departajare, categoria {q['cat']}. {q['q']}"
            self.ask_number(msg, q, lambda val: self.tiebreak_result(q, {0: val}, ""))
        else:
            self.tiebreak_result(q, {}, head)

    def tiebreak_result(self, q, guesses, head):
        g = self.g
        att, ti, d = self.cur
        for pi in (att, d):
            if pi != 0:
                guesses[pi] = g.ai_guess(q["ans"])
        order = g.rank(guesses, q["ans"])
        dist = {pi: (float("inf") if guesses[pi] is None else abs(guesses[pi] - q["ans"])) for pi in guesses}
        att_wins = dist[att] < dist[d]
        if 0 in (att, d):
            sounds.play("correct" if (att_wins == (att == 0)) else "wrong")
        txt = (f"{head}Departajare: {q['q']} Răspunsul corect: {fmt_num(q['ans'])}. "
               + ", ".join(f"{g.players[pi].name} {'fără răspuns' if guesses[pi] is None else fmt_num(guesses[pi])}"
                           for pi in (att, d)) + ". ")
        txt += g.resolve(att, ti, att_wins, False)
        self.status(txt, self.next_attack)

    def finish(self):
        g = self.g
        order = sorted(range(3), key=lambda i: -g.score(i))
        win = g.players[order[0]].name
        head = "Ai câștigat! Felicitări!" if order[0] == 0 else f"A câștigat {win}."
        self.f.show_menu("Final Triviador", [
            (f"Jocul s-a terminat. {head} {g.scores_text()}", None),
            ("Joc nou", self.start),
        ], on_escape=self.setup, selected=0)
