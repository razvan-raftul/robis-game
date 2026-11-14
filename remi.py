"""Logica pentru Remi pe tablă și Remi etalat (varianta românească, cu piese)."""
import random

from remi_core import (Formation, best_partition, candidates, choose_discard, closing_plan,
                       make_deck, sort_tiles, used_ids)

NUME_AI = ["Miruna", "Sara", "Cristi"]


class RPlayer:
    def __init__(self, name, human=False):
        self.name, self.human = name, human
        self.score = 0
        self.reset()

    def reset(self):
        self.hand, self.etalat, self.laid_points, self.atu, self.on_board = [], False, 0, 0, False


def total(fs):
    return sum(f.points() for f in fs)


def valid_first(fs):
    return total(fs) >= 45 and any(f.kind == "run" or f.has_ace_group() for f in fs)


def _copy(fs):
    return [Formation(f.kind, list(f.cells)) for f in fs]


def keep_one(hand, fs, first):
    """Ne asigurăm că rămâne măcar o piesă în mână pentru aruncat."""
    if len(used_ids(fs)) < len(hand):
        return fs
    for k, f in enumerate(fs):
        for i in reversed(f.removable_cells()):
            g = _copy(fs)
            if g[k].cells[i][0].joker:
                continue
            g[k].cells.pop(i)
            if not first or valid_first(g):
                return g
    for k in sorted(range(len(fs)), key=lambda k: fs[k].points()):
        g = _copy(fs[:k] + fs[k + 1:])
        if g and (not first or valid_first(g)):
            return g
    return None


def etalare_plan(hand, first, must=None):
    """Întoarce formațiile pentru etalare (prima etalare are nevoie de 45 de puncte și o suită)."""
    options = []

    def with_forced(f):
        ids = {x.id for x in f.tiles}
        _, fs = best_partition([x for x in hand if x.id not in ids])
        return [f] + fs

    if must is None:
        _, fs = best_partition(hand)
        options.append(fs)
        if first and fs and total(fs) >= 45 and not valid_first(fs):
            for t in hand:
                if t.joker:
                    continue
                rest = [x for x in hand if x is not t]
                for f in candidates(t, rest):
                    if f.kind == "run":
                        options.append(with_forced(f))
    else:
        rest = [x for x in hand if x is not must]
        if must.joker:
            _, fs = best_partition(hand)
            if must.id in used_ids(fs):
                options.append(fs)
        else:
            for f in candidates(must, rest):
                options.append(with_forced(f))
    best = None
    for fs in options:
        if not fs:
            continue
        if first and not valid_first(fs):
            continue
        fs = keep_one(hand, fs, first)
        if not fs:
            continue
        if must is not None and must.id not in used_ids(fs):
            continue
        if best is None or total(fs) > total(best):
            best = fs
    return best


class RemiGame:
    def __init__(self, variant, n_ai, rng=None, name="Jucător"):
        self.variant = variant          # "tabla" sau "etalat"
        self.rng = rng or random.Random()
        self.players = [RPlayer(name, True)] + [RPlayer(n) for n in NUME_AI[:n_ai]]
        self.starter = self.rng.randrange(len(self.players))
        self.round_no = 0

    @property
    def etalat_mode(self):
        return self.variant == "etalat"

    def new_round(self):
        self.round_no += 1
        self.deck = make_deck(self.rng)
        self.atu = next(t for t in self.deck if not t.joker)
        n = len(self.players)
        for p in self.players:
            p.reset()
        for i in range(n):
            pi = (self.starter + i) % n
            cnt = 15 if i == 0 else 14
            self.players[pi].hand = sort_tiles([self.deck.pop(0) for _ in range(cnt)])
        for p in self.players:
            p.atu = sum(1 for t in p.hand if t.sig() == self.atu.sig())
        self.table = []
        self.discard = None
        self.turn = self.starter
        self.state = "discard"          # cel care începe are 15 piese și doar aruncă
        self.turns_done = 0
        self.over, self.closer, self.summary = False, None, ""
        self.starter = (self.starter + 1) % n
        return self.start_text()

    def start_text(self):
        who = [p.name for p in self.players if p.atu]
        s = f"Runda {self.round_no}. Atuul este {self.atu.name()}."
        if who:
            s += " Au atuul: " + ", ".join(who) + "."
        s += f" Începe {self.players[self.turn].name}."
        return s

    def cur(self):
        return self.players[self.turn]

    def can_etalate_now(self):
        return self.turns_done >= len(self.players)

    # ----- acțiuni -----
    def draw(self, pi):
        if not self.deck:
            self.end_round(None)
            return None
        t = self.deck.pop(0)
        self.players[pi].hand.append(t)
        self.players[pi].hand = sort_tiles(self.players[pi].hand)
        self.state = "discard"
        return t

    def discard_use_plan(self, pi):
        """Etalat: piesa aruncată se poate lua doar dacă e folosită imediat."""
        d = self.discard
        if d is None:
            return None
        p = self.players[pi]
        if not self.etalat_mode:
            return ("free", None)
        if p.etalat:
            for f in self.table:
                if f.attach_value(d) is not None:
                    return ("attach", f)
            best = None
            for f in candidates(d, p.hand) if not d.joker else []:
                if len(p.hand) + 1 - len(f.cells) >= 1 and (best is None or f.points() > best.points()):
                    best = f
            if best:
                return ("form", best)
            return None
        if not self.can_etalate_now():
            return None
        fs = etalare_plan(p.hand + [d], True, must=d)
        if fs:
            return ("etalare", fs)
        return None

    def take_discard(self, pi):
        plan = self.discard_use_plan(pi)
        if plan is None:
            return None
        p, d = self.players[pi], self.discard
        self.discard = None
        p.hand = sort_tiles(p.hand + [d])
        self.state = "discard"
        kind, data = plan
        if kind == "free":
            return f"a luat {d.name()}"
        if kind == "attach":
            pts = self.attach(pi, d, data)
            return f"a luat {d.name()} și a lipit-o la {data.name()}"
        if kind == "form":
            self.lay(pi, [data])
            return f"a luat {d.name()} și a pus {data.name()}"
        pts = self.lay(pi, data)
        return f"a luat {d.name()} și s-a etalat cu {pts} de puncte"

    def lay(self, pi, forms):
        p = self.players[pi]
        ids = used_ids(forms)
        p.hand = [x for x in p.hand if x.id not in ids]
        pts = 0
        for f in forms:
            f.owner = pi
            self.table.append(f)
            pts += f.points()
        p.etalat = True
        p.laid_points += pts
        return pts

    def attach(self, pi, t, f):
        p = self.players[pi]
        pts = f.attach(t)
        if pts is None:
            return None
        p.hand = [x for x in p.hand if x is not t]
        p.laid_points += pts
        return pts

    def attach_options(self, pi):
        p = self.players[pi]
        if not self.etalat_mode or not p.etalat or len(p.hand) <= 1:
            return []
        out = []
        for t in p.hand:
            for f in self.table:
                if f.attach_value(t) is not None:
                    out.append((t, f))
        return out

    def lay_plan(self, pi):
        p = self.players[pi]
        if not self.etalat_mode:
            return None
        if not p.etalat:
            if not self.can_etalate_now():
                return None
            return etalare_plan(p.hand, True)
        _, fs = best_partition(p.hand)
        if not fs:
            return None
        return keep_one(p.hand, fs, False)

    def do_discard(self, pi, t):
        p = self.players[pi]
        p.hand = [x for x in p.hand if x is not t]
        self.discard = t
        if self.etalat_mode and not p.hand:
            self.end_round(pi)
            return
        self.next_turn()

    def close_tabla(self, pi):
        p = self.players[pi]
        plan = closing_plan(p.hand)
        if not plan:
            return False
        t, fs = plan
        p.hand = [x for x in p.hand if x is not t]
        self.discard = t
        p.closing_forms = fs
        self.end_round(pi)
        return True

    def next_turn(self):
        self.turns_done += 1
        self.turn = (self.turn + 1) % len(self.players)
        self.state = "draw"

    def end_round(self, closer):
        self.over, self.closer = True, closer
        lines = []
        if closer is None:
            lines.append("S-a terminat pachetul, nimeni nu a închis.")
        else:
            lines.append(f"{self.players[closer].name} a închis jocul.")
        for i, p in enumerate(self.players):
            delta, parts = 0, []
            if self.etalat_mode:
                if p.etalat:
                    pen = sum(t.penalty() for t in p.hand)
                    delta += p.laid_points - pen
                    parts.append(f"{p.laid_points} puncte etalate")
                    if pen:
                        parts.append(f"minus {pen} din mână")
                else:
                    delta -= 100
                    parts.append("neetalat, minus 100")
                if i == closer:
                    delta += 50
                    parts.append("plus 50 pentru închidere")
            else:
                if i == closer:
                    delta += 100
                    parts.append("plus 100 pentru închidere")
                else:
                    _, fs = best_partition(p.hand, "count")
                    used = used_ids(fs)
                    pen = sum(t.penalty() for t in p.hand if t.id not in used)
                    delta -= pen
                    parts.append(f"minus {pen} pentru piesele nefolosite")
            if p.atu:
                delta += 50 * p.atu
                parts.append(f"plus {50 * p.atu} pentru atu")
            p.score += delta
            lines.append(f"{p.name}: {'+' if delta >= 0 else ''}{delta} ({', '.join(parts)}). Total {p.score}.")
        self.summary = " ".join(lines)

    # ----- calculator -----
    def ai_turn(self):
        """Joacă tura jucătorului curent (calculator). Întoarce un text cu ce a făcut."""
        pi = self.turn
        p = self.players[pi]
        acts = []
        if self.state == "draw":
            took = False
            d = self.discard
            if d is not None:
                if self.etalat_mode:
                    plan = self.discard_use_plan(pi)
                    if plan and (plan[0] != "form" or plan[1].points() >= 15):
                        acts.append(self.take_discard(pi)); took = True
                else:
                    before = len(used_ids(best_partition(p.hand, "count")[1]))
                    _, fs = best_partition(p.hand + [d], "count")
                    if d.joker or (d.id in used_ids(fs) and len(used_ids(fs)) > before):
                        acts.append(self.take_discard(pi)); took = True
            if not took:
                if self.draw(pi) is None:
                    return f"{p.name} nu mai are ce trage. " + self.summary
                acts.append("a tras din pachet")
        if not self.etalat_mode:
            if closing_plan(p.hand):
                self.close_tabla(pi)
                return f"{p.name} {', '.join(acts)} și a închis!"
            _, fs = best_partition(p.hand, "count")
            t = choose_discard(p.hand, fs)
            self.do_discard(pi, t)
            acts.append(f"a aruncat {t.name()}")
            return f"{p.name} " + ", ".join(acts) + "."
        # etalat
        plan = self.lay_plan(pi)
        if plan:
            first = not p.etalat
            pts = self.lay(pi, plan)
            acts.append(("s-a etalat" if first else "a pus formații noi") + f" cu {pts} de puncte")
        changed = True
        while changed:
            changed = False
            for t, f in self.attach_options(pi):
                self.attach(pi, t, f)
                acts.append(f"a lipit {t.name()}")
                changed = True
                break
        _, fs = best_partition(p.hand)
        t = choose_discard(p.hand, fs)
        self.do_discard(pi, t)
        acts.append(f"a aruncat {t.name()}")
        txt = f"{p.name} " + ", ".join(acts) + "."
        if self.over:
            txt += f" {p.name} a închis!"
        else:
            txt += f" Mai are {len(p.hand)} piese."
        return txt
