"""Piese, formații și căutarea celor mai bune formații pentru Remi."""
import itertools
import random

CULORI = ["Roșu", "Galben", "Albastru", "Negru"]


class Tile:
    __slots__ = ("id", "color", "num")

    def __init__(self, id, color, num):
        self.id, self.color, self.num = id, color, num

    @property
    def joker(self):
        return self.color < 0

    def name(self):
        return "Joker" if self.joker else f"{CULORI[self.color]} {self.num}"

    def sig(self):
        return (self.color, self.num)

    def sort_key(self):
        return (1, 0, 0) if self.joker else (0, self.color, self.num)

    def penalty(self):
        """Valoarea piesei rămase în mână la final."""
        if self.joker:
            return 50
        if self.num == 1:
            return 25
        return 10 if self.num >= 10 else 5

    def __repr__(self):
        return self.name()


def make_deck(rng):
    tiles, i = [], 0
    for _ in range(2):
        for c in range(4):
            for n in range(1, 14):
                tiles.append(Tile(i, c, n)); i += 1
    tiles.append(Tile(i, -1, 0)); tiles.append(Tile(i + 1, -1, 0))
    rng.shuffle(tiles)
    return tiles


def sort_tiles(tiles):
    return sorted(tiles, key=Tile.sort_key)


def num_name(v):
    return "1" if v == 14 else str(v)


class Formation:
    """kind: 'run' (suită) sau 'group' (terță/quartă). cells: listă de (Tile, valoare reprezentată).
    Pentru suită, valoarea 14 înseamnă 1 pus după 13."""

    def __init__(self, kind, cells, owner=None):
        self.kind, self.owner = kind, owner
        self.cells = sorted(cells, key=lambda c: c[1]) if kind == "run" else list(cells)

    @property
    def tiles(self):
        return [c[0] for c in self.cells]

    def color(self):
        for t, _ in self.cells:
            if not t.joker:
                return t.color
        return 0

    def number(self):
        return self.cells[0][1]

    def cell_points(self, v):
        if self.kind == "group":
            return 25 if v == 1 else (10 if v >= 10 else 5)
        if v == 14:
            return 10
        if v == 1:
            return 5
        return 10 if v >= 10 else 5

    def points(self):
        return sum(self.cell_points(v) for _, v in self.cells)

    def has_ace_group(self):
        return self.kind == "group" and self.number() == 1

    def name(self):
        parts = []
        for t, v in self.cells:
            parts.append(f"joker ca {num_name(v)}" if t.joker else num_name(v))
        if self.kind == "run":
            return f"Suită {CULORI[self.color()].lower()}: " + ", ".join(parts)
        cols = [CULORI[t.color].lower() for t, _ in self.cells if not t.joker]
        nj = sum(1 for t, _ in self.cells if t.joker)
        extra = f", plus {nj} joker" if nj else ""
        return f"Terță de {num_name(self.number())}: " + ", ".join(cols) + extra if len(self.cells) == 3 \
            else f"Quartă de {num_name(self.number())}: " + ", ".join(cols) + extra

    # ----- lipire -----
    def attach_value(self, t):
        """Întoarce valoarea pe care ar primi-o piesa t dacă e lipită, sau None."""
        vals = [v for _, v in self.cells]
        if self.kind == "group":
            if len(self.cells) >= 4:
                return None
            n = self.number()
            if t.joker:
                return n
            cols = {x.color for x, _ in self.cells if not x.joker}
            if t.num == n and t.color not in cols:
                return n
            return None
        lo, hi = min(vals), max(vals)
        c = self.color()
        cand = []
        if t.joker:
            cand = [hi + 1, lo - 1]
        elif t.color == c:
            cand = [14] if t.num == 1 else [t.num]
            if t.num == 1:
                cand.append(1)
        for p in cand:
            if (p == lo - 1 and p >= 1) or (p == hi + 1 and p <= 14):
                nlo, nhi = min(lo, p), max(hi, p)
                if nlo == 1 and nhi == 14:
                    continue
                return p
        return None

    def attach(self, t):
        v = self.attach_value(t)
        if v is None:
            return None
        self.cells.append((t, v))
        if self.kind == "run":
            self.cells.sort(key=lambda c: c[1])
        return self.cell_points(v)

    def removable_cells(self):
        """Piese care pot fi scoase fără ca formația să devină invalidă."""
        if len(self.cells) <= 3:
            return []
        if self.kind == "group":
            return list(range(len(self.cells)))
        return [0, len(self.cells) - 1]


def _pos_num(p):
    return 1 if p == 14 else p


def candidates(t, rest):
    """Toate formațiile care conțin piesa t (care nu e joker), folosind piese din rest."""
    jokers = [x for x in rest if x.joker]
    k = len(jokers)
    by_sig = {}
    for x in rest:
        if not x.joker:
            by_sig.setdefault(x.sig(), x)
    out = []
    # terțe / quarte
    n = t.num
    others = [by_sig[(c, n)] for c in range(4) if c != t.color and (c, n) in by_sig]
    for r in range(0, len(others) + 1):
        for sub in itertools.combinations(others, r):
            for j in range(0, min(k, 3) + 1):
                size = 1 + r + j
                if 3 <= size <= 4:
                    cells = [(t, n)] + [(x, n) for x in sub] + [(jk, n) for jk in jokers[:j]]
                    out.append(Formation("group", cells))
    # suite
    c = t.color
    positions = [n] + ([14] if n == 1 else [])
    for p in positions:
        for lo in range(max(1, p - 13), p + 1):
            need, cells, ok = 0, [], True
            # parcurgem de la lo până la p (stânga)
            for q in range(lo, p):
                x = by_sig.get((c, _pos_num(q)))
                if x is not None and not (q in (1, 14) and _pos_num(q) == t.num and x is t):
                    cells.append((x, q))
                else:
                    need += 1
                    cells.append((None, q))
            if need > k:
                continue
            cells.append((t, p))
            for hi in range(p, 15):
                if hi > p:
                    x = by_sig.get((c, _pos_num(hi)))
                    if x is not None:
                        cells.append((x, hi))
                    else:
                        need += 1
                        cells.append((None, hi))
                if need > k:
                    break
                if lo == 1 and hi == 14:
                    break
                if hi - lo + 1 >= 3:
                    # nu folosi aceeași piesă de două ori (1 jos și 1 sus)
                    used = [x for x, _ in cells if x is not None]
                    if len({x.id for x in used}) != len(used):
                        continue
                    ji, real = 0, []
                    for x, q in cells:
                        if x is None:
                            real.append((jokers[ji], q)); ji += 1
                        else:
                            real.append((x, q))
                    out.append(Formation("run", real))
    return out


def best_partition(tiles, mode="points"):
    """Caută formații disjuncte. mode='points' maximizează punctele de etalare,
    mode='count' maximizează numărul de piese folosite. Întoarce (scor, [formații])."""
    tiles = sort_tiles(tiles)
    memo = {}

    def value(f):
        if mode == "points":
            return f.points()
        return len(f.cells) * 1000 + f.points()

    def solve(rem):
        key = tuple(sorted(x.id for x in rem))
        if key in memo:
            return memo[key]
        real = [x for x in rem if not x.joker]
        if not real:
            memo[key] = (0, [])
            return memo[key]
        t = real[0]
        rest = [x for x in rem if x is not t]
        best = solve(rest)
        for f in candidates(t, rest):
            ids = {x.id for x in f.tiles}
            r2 = [x for x in rest if x.id not in ids]
            s, fs = solve(r2)
            s += value(f)
            if s > best[0]:
                best = (s, [f] + fs)
        memo[key] = best
        return best

    s, fs = solve(tiles)
    fs = [Formation(f.kind, list(f.cells)) for f in fs]
    if mode == "count":
        used = {x.id for f in fs for x in f.tiles}
        for j in [x for x in tiles if x.joker and x.id not in used]:
            for f in fs:
                if f.attach_value(j) is not None:
                    f.attach(j)
                    break
    return s, fs


def used_ids(forms):
    return {x.id for f in forms for x in f.tiles}


def closing_plan(hand):
    """Remi pe tablă: hand are 15 piese. Întoarce (piesa de aruncat, formații) dacă poți închide, altfel None."""
    _, fs = best_partition(hand, "count")
    used = used_ids(fs)
    left = [x for x in hand if x.id not in used]
    if len(left) == 1:
        return left[0], fs
    if len(left) == 0:
        for f in fs:
            rc = f.removable_cells()
            if rc:
                i = rc[-1]
                t = f.cells.pop(i)[0]
                return t, fs
        for t in hand:
            rest = [x for x in hand if x is not t]
            _, fs2 = best_partition(rest, "count")
            if len(used_ids(fs2)) == 14:
                return t, fs2
    return None


def usefulness(t, hand):
    """Cât de utilă e o piesă (pentru alegerea piesei de aruncat)."""
    if t.joker:
        return 100
    u = 0
    for x in hand:
        if x is t or x.joker:
            continue
        if x.color == t.color and abs(x.num - t.num) <= 2 and x.num != t.num:
            u += 3 - abs(x.num - t.num)
        if t.num == 1 and x.color == t.color and x.num in (12, 13):
            u += 1
        if x.num == t.num and x.color != t.color:
            u += 2
    return u


def choose_discard(hand, forms):
    used = used_ids(forms)
    left = [x for x in hand if x.id not in used and not x.joker]
    if not left:
        left = [x for x in hand if not x.joker] or list(hand)
        # preferă o piesă care se poate scoate dintr-o formație lungă
        for f in forms:
            for i in f.removable_cells():
                t = f.cells[i][0]
                if not t.joker:
                    return t
    return min(left, key=lambda x: (usefulness(x, hand), -x.penalty(), x.id))
