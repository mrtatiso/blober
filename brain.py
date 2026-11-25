"""
blobengine.brain: what you like, learned from the votes in a .bna, and how new genomes are made from it.
A port of the page's Brain, attribute(), train() and generators, in the same order of operations.
"""
import math
import re

from .core import (NS, NF, NT, NL, NE, PALETTE, FAMILY_GENES, LIMB_KEY, LIMB_ON, is_on, qv, clamp, gauss,
                   fam_of, genome, hex_of, parse_genome)

PARTS = ["shape", "face", "antennas", "arms", "legs", "color"]
BLOB = ["shape", "face", "antennas", "arms", "legs"]
LIKE = BLOB                                   # what the floor scores by: color is never learned, every color keeps coming
NEUTRAL_FACE = {"f": [qv(v) for v in (.45, .5, .3, .5, .5, .5, .35, .4, 0, .5)], "e": 0, "m": 5}
BAND = {"shape": .09, "face": .1, "antennas": .13, "arms": .13, "legs": .13, "color": .2}


def rnd(r, n):
    return [qv(r()) for _ in range(n)]


def compose(*parts):
    g = {}
    for p in parts:
        g.update(p)
    return g


# ---------- making genomes: random, mutated, crossed ----------

def random_shape(r):  # most random bodies have one or two features, not all at once
    s, keys = rnd(r, NS), list(FAMILY_GENES)
    k = 0 if r() < .3 else 1 if r() < .75 else 2
    on = []
    while len(on) < k:
        key = keys[math.floor(r() * len(keys))]
        if key not in on:
            on.append(key)
    for key in keys:
        i, t = FAMILY_GENES[key]
        s[i] = qv(t + (1 - t) * (.15 + .85 * r()) if key in on else r() * t * .9)
    if r() < .5:
        s[14] = qv(.3 + r() * .4)
    s[12] = qv(r() * .8)
    return s


def random_part(p, r):
    if p == "shape":
        return {"s": random_shape(r)}
    if p == "face":
        f = rnd(r, NF)
        e = math.floor(r() * NE)
        return {"f": f, "e": e, "m": math.floor(r() * 10)}
    if p == "antennas":
        return {"t": rnd(r, NT)}
    if p == "arms":
        return {"a": rnd(r, NL)}
    if p == "legs":
        return {"l": rnd(r, NL)}
    return {"c": math.floor(r() * len(PALETTE))}


def part_of(p, g):
    if p == "shape":
        return {"s": g["s"]}
    if p == "face":
        return {"f": g["f"], "e": g["e"], "m": g["m"]}
    if p == "antennas":
        return {"t": g["t"]}
    if p == "arms":
        return {"a": g["a"]}
    if p == "legs":
        return {"l": g["l"]}
    return {"c": g["c"]}


def mutate_part(p, v, r, sigma):
    def mv(arr):
        return [qv(x + gauss(r) * sigma) if r() < .5 else x for x in arr]
    if p == "shape":
        return {"s": mv(v["s"])}
    if p == "face":
        f = mv(v["f"])
        e = math.floor(r() * NE) if r() < sigma * .8 else v["e"]
        m = math.floor(r() * 10) if r() < sigma * .8 else v["m"]
        return {"f": f, "e": e, "m": m}
    if p in ("antennas", "arms", "legs"):
        k = LIMB_KEY[p]
        return {k: mv(v[k])}
    return {"c": math.floor(r() * len(PALETTE)) if r() < sigma * 1.5 else v["c"]}


def cross_part(p, a, b, r):
    def mix(x, y):
        return [v if r() < .5 else y[i] for i, v in enumerate(x)]
    if p == "shape":
        return {"s": mix(a["s"], b["s"])}
    if p == "face":
        f = mix(a["f"], b["f"])
        e = a["e"] if r() < .5 else b["e"]
        return {"f": f, "e": e, "m": a["m"] if r() < .5 else b["m"]}
    if p in ("antennas", "arms", "legs"):
        k = LIMB_KEY[p]
        return {k: mix(a[k], b[k])}
    return a if r() < .5 else b


# ---------- what you like: one small model per part ----------

def b3(v):
    return 0 if v < .34 else 1 if v < .67 else 2


def b4(v):
    return min(3, math.floor(v * 4))


def feats(p, g):
    fam, k = fam_of(g["s"]), []
    if p == "shape":
        k += [f"fam={fam}", f"asp={b3(g['s'][0])}", f"{fam}|asp={b3(g['s'][0])}"]
        for i in (1, 2, 4, 5, 7, 8, 10, 11, 12, 14):
            k.append(f"s{i}={b4(g['s'][i])}")
    elif p == "face":
        e, m = g["e"], g["m"]
        k += [f"e={e}", f"m={m}", f"em={e}.{m}", f"{fam}|e={e}", f"{fam}|m={m}"]
        for i, v in enumerate(g["f"]):
            k.append(f"f{i}={b3(v)}")
        for i in (0, 2, 3, 9):
            k.append(f"{fam}|f{i}={b3(g['f'][i])}")
    elif p in LIMB_KEY:
        t = LIMB_KEY[p]
        arr, on = g[t], 1 if is_on(p, g) else 0
        k += [f"{t}={on}", f"{fam}|{t}={on}"]
        if on:
            for i in range(1, len(arr)):
                k.append(f"{t}{i}={b3(arr[i])}")
            for i in (1, 2, 4):
                k.append(f"{fam}|{t}{i}={b3(arr[i])}")
            if t == "t":
                st = min(5, math.floor(arr[1] * 6))
                k += [f"t1s={st}", f"{fam}|t1s={st}"]
    else:
        k += [f"c={g['c']}", f"{fam}|c={g['c']}"]
    return k


def rms2(x, y, frm=0):
    s = 0
    for i in range(frm, len(x)):
        s += (x[i] - y[i]) ** 2
    return s / (len(x) - frm)


def dist2(p, g, h):
    if p == "shape":
        return rms2(g["s"], h["s"])
    if p == "face":
        return rms2(g["f"], h["f"]) + (g["e"] != h["e"]) * .06 + (g["m"] != h["m"]) * .03
    if p in LIMB_KEY:
        on1, on2, k = is_on(p, g), is_on(p, h), LIMB_KEY[p]
        return 1 if on1 != on2 else 0 if not on1 else rms2(g[k], h[k], 1)
    return 0 if g["c"] == h["c"] else 1


def expand(kind, part):
    """A vote -> rows per part: (part, liked, weight). 'all' is the whole creature, 'blob' all but its color."""
    if kind == "bad":
        return [(p, 0, 1) if p == part else (p, 1, .3) for p in PARTS]
    lst = PARTS if part == "all" else BLOB if part == "blob" else None
    if kind == "yes":
        return [(p, 1, 1) for p in lst] if lst else [(part, 1, 1)]
    if kind == "no":
        return [(p, 0, .8 if part == "blob" else .6) for p in lst] if lst else [(part, 0, 1)]
    if kind == "meh":
        return [(p, 0, .2) for p in lst] if lst else [(part, 0, .3)]
    return []


def sameness(p, a, b):
    return math.exp(-dist2(p, a, b) / (2 * BAND[p] ** 2))


def attribute(events):
    """Whole-creature votes say "this one", not "because of what": opposite votes on near copies tell which part decided."""
    whole = [i for i, e in enumerate(events) if e["part"] in ("all", "blob") and e["kind"] in ("yes", "no")]
    out = {}
    for i in whole:
        e = events[i]
        liked = e["kind"] == "yes"
        diff = [0] * len(BLOB)
        near = clash = later = 0
        for j in whole:
            o = events[j]
            if (o["kind"] == "yes") == liked:
                continue
            s0, s1 = sameness("shape", e["g"], o["g"]), sameness("face", e["g"], o["g"])
            if s0 < .05 and s1 < .05:
                continue
            s = [s0, s1] + [sameness(p, e["g"], o["g"]) for p in BLOB[2:]]
            d = sorted(-math.log(v + 1e-9) for v in s)
            d.pop()
            tot = 0
            for x in d:
                tot += x
            S = math.exp(-tot / len(d))
            if S < .15:
                continue
            if 1 - min(s) < .35:
                clash += S
                if j > i:
                    later += S
                continue
            near += S
            for k, v in enumerate(s):
                diff[k] += S * (1 - v)
        if not near and not clash:
            continue
        sure, w = near / (near + .6), {}
        for k, p in enumerate(BLOB):
            a = clamp(.2 + 1.6 * diff[k] / near, .15, 1.8) if near else 1
            w[p] = 1 + (a - 1) * sure
        if liked and clash:
            for p in BLOB:
                w[p] /= 1 + clash + 2 * later
        out[i] = w
    return out


def train(rows):
    w, bias = {}, 0
    W = 0
    for r in rows:
        W += r["w"]
    epoch = 0
    while epoch < 150 and rows:
        grad, gb = {}, 0
        for r in rows:
            z = bias
            for k in r["f"]:
                z += w.get(k, 0)
            e = ((0.0 if -z > 709 else 1 / (1 + math.exp(-z))) - r["y"]) * r["w"]   # JS: exp overflows to Infinity, 1/Infinity = 0
            gb += e
            for k in r["f"]:
                grad[k] = grad.get(k, 0) + e
        bias -= 1.5 * gb / W
        for k, gk in grad.items():
            v = w.get(k, 0)
            w[k] = v - 2 * (gk / W + .006 * v)
        epoch += 1
    return {"w": w, "bias": bias}


VOTE_RE = re.compile(r"^(yes|no|meh|bad) (all|blob|shape|face|antennas|arms|legs|color) (.+)$")


class Brain:
    def __init__(self):
        self.events = []
        self.cache = None

    def add(self, kind, part, g):
        self.events.append({"kind": kind, "part": part, "g": g, "s": genome(g)})
        self.cache = None

    def text(self):
        return "".join(f"{e['kind']} {e['part']} {e['s']}\n" for e in self.events) or "\n"

    def read(self, text):
        n = 0
        for line in (text or "").split("\n"):
            m = VOTE_RE.match(line.strip())
            if not m:
                continue
            try:
                self.add(m.group(1), m.group(2), parse_genome(m.group(3)))
                n += 1
            except ValueError:
                pass
        return n

    def m(self, p):
        if self.cache is None:
            by = {q: [] for q in PARTS}
            credit = attribute(self.events)
            for i, ev in enumerate(self.events):
                c = credit.get(i)
                for q, y, w in expand(ev["kind"], ev["part"]):
                    by[q].append({"g": ev["g"], "s": ev["s"], "y": y, "w": w * (c[q] if c and q in c else 1), "i": i, "f": feats(q, ev["g"])})
            self.cache = {}
            for q in PARTS:
                t = train(by[q])
                self.cache[q] = {"rows": by[q], "w": t["w"], "bias": t["bias"]}
        return self.cache[p]

    def score(self, p, g):
        """The model says what kind of thing you like; nearness to what you voted says which exact one."""
        M, h2 = self.m(p), 2 * BAND[p] ** 2
        z = 0
        for k in feats(p, g):
            z += M["w"].get(k, 0)
        near = 0
        for r in M["rows"]:
            d = dist2(p, g, r["g"])
            if d < 4.5 * h2:
                near += r["w"] * (1 if r["y"] else -1.3) * math.exp(-d / h2)
        return z + 1.6 * math.tanh(near * .6)

    def total(self, g):
        s = 0
        for p in PARTS:
            s += self.score(p, g)
        return s

    def parents(self, p):
        M, seen, out = self.m(p), set(), []
        for i in range(len(M["rows"]) - 1, -1, -1):
            if len(out) >= 80:
                break
            r = M["rows"][i]
            if r["y"] != 1:
                continue
            v = part_of(p, r["g"])
            flat = []
            for x in v.values():
                if isinstance(x, list):
                    flat += x
                else:
                    flat.append(x)
            key = hex_of(flat)
            if key in seen:
                continue
            seen.add(key)
            out.append({"v": v, "w": r["w"] * (1 - len(out) / 120)})
        return out

    def votes(self, p):
        return len(self.m(p)["rows"])


def pick_w(items, ws, r):
    t, c = 0, []
    for x in ws:
        t += x
        c.append(t)
    x = r() * t
    i = next((k for k, v in enumerate(c) if v >= x), -1)
    return items[len(items) - 1 if i < 0 else i]


def tuning(brain, polish):
    n = len(brain.events)
    return {"explore": max(.06, .45 * math.pow(.62, polish), .5 if n < 30 else 0),
            "sigma": max(.025, .15 * math.pow(.75, polish)), "temp": max(.3, 1.1 * math.pow(.82, polish))}


def gen_part(brain, p, r, t):
    ps = brain.parents(p)
    if not ps or r() < t["explore"]:
        return random_part(p, r)
    v = pick_w(ps, [x["w"] for x in ps], r)["v"]
    if len(ps) > 1 and r() < .25:
        v = cross_part(p, v, pick_w(ps, [x["w"] for x in ps], r)["v"], r)
    return mutate_part(p, v, r, t["sigma"])


def choose(cands, n, temp, r, taken=None):
    """Choose n among scored candidates: the better more likely, never two almost the same."""
    taken = set() if taken is None else taken
    out = []
    left = [c for c in cands if genome(c["g"]) not in taken]
    while len(out) < n and left:
        top = max(c["score"] for c in left)
        c = pick_w(left, [math.exp((x["score"] - top) / temp) for x in left], r)
        left.remove(c)
        if any(rms2(o["g"]["s"], c["g"]["s"]) < .002 and o["g"]["e"] == c["g"]["e"] for o in out):
            continue
        out.append(c)
        taken.add(genome(c["g"]))
    return [c["g"] for c in out]


# ---------- reading a .bna ----------

def to_bna1(line):
    """Votes from blober 2.0.0 -> bna1 lines (bna1 lines pass through)."""
    if re.search(r" t=[0-9a-f]{16} ", line):
        return [line]
    m = re.search(r" e=(\d) m=(\d) a=", line)
    v = re.match(r"^(yes|no|meh|bad) (\w+) (.+)$", line)
    if not m or not v:
        return []
    e = int(m.group(1))
    if e == 5:
        return []
    if e > 5:
        e -= 1
    g = v.group(3).replace(m.group(0), f" e={e} m={m.group(2)} t=00{'80' * 7} a=", 1)
    g = re.sub(r" f=([0-9a-f]{6})[0-9a-f]{2}", r" f=\g<1>80", g, count=1)
    if v.group(1) == "bad":
        return [f"no {v.group(2)} {g}"]
    if v.group(2) == "all":
        return [f"{v.group(1)} {p} {g}" for p in ("shape", "face", "arms", "legs", "color")]
    return [f"{v.group(1)} {v.group(2)} {g}"]
