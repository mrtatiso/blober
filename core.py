"""
blobengine.core: genome -> creature SVG, a line-by-line port of the page's JavaScript core (bna1).

Every number is computed in the same order as in the browser, so the same genome draws the same SVG,
character for character. Helpers named js_* reproduce JavaScript's own behaviour where Python differs
(rounding, number formatting, 32-bit integer math, Math.hypot).
"""
import math

VERSION = "bna1-pre"

# ---------- JavaScript arithmetic ----------

M32 = 0xFFFFFFFF


def imul(a, b):
    return (a * b) & M32


def js_round(x):
    """Math.round: nearest, halves go up (toward +infinity)."""
    return math.floor(x + 0.5)


def js_hypot(a, b):
    """Math.hypot as V8 computes it: scaled by the largest value, Kahan-compensated."""
    a, b = abs(a), abs(b)
    mx = a if a > b else b
    if mx == math.inf:
        return math.inf
    if mx == 0:
        return 0.0
    s = 0.0
    comp = 0.0
    for v in (a, b):
        n = v / mx
        summand = n * n - comp
        prelim = s + summand
        comp = (prelim - s) - summand
        s = prelim
    return math.sqrt(s) * mx


def js_fixed(x, digits):
    """Number.prototype.toFixed (-0 prints as 0)."""
    if x == 0:
        x = 0.0
    return f"{x:.{digits}f}"


def F(v):
    """The page's number format: one decimal, never -0.0."""
    r = js_round(v * 10) / 10
    return js_fixed(r, 1).replace("-0.0", "0.0", 1)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def js_sign(x):
    return 1.0 if x > 0 else -1.0 if x < 0 else x


# ---------- numbers from a seed ----------

def hash4(text):  # cyrb128
    h1, h2, h3, h4 = 1779033703, 3144134277, 1013904242, 2773480762
    units = text.encode("utf-16-le")
    for i in range(0, len(units), 2):
        k = units[i] | (units[i + 1] << 8)
        h1 = h2 ^ imul(h1 ^ k, 597399067)
        h2 = h3 ^ imul(h2 ^ k, 2869860233)
        h3 = h4 ^ imul(h3 ^ k, 951274213)
        h4 = h1 ^ imul(h4 ^ k, 2716044179)
    h1 = imul(h3 ^ (h1 >> 18), 597399067)
    h2 = imul(h4 ^ (h2 >> 22), 2869860233)
    h3 = imul(h1 ^ (h3 >> 17), 951274213)
    h4 = imul(h2 ^ (h4 >> 19), 2716044179)
    return [(h1 ^ h2 ^ h3 ^ h4) & M32, (h2 ^ h1) & M32, (h3 ^ h1) & M32, (h4 ^ h1) & M32]


def seeded(seed):  # sfc32, seeded like the page: "blober|" + seed
    a, b, c, d = hash4("blober|" + str(seed))
    state = [a, b, c, d]

    def nxt():
        a, b, c, d = state
        t = (((a + b) & M32) + d) & M32
        d = (d + 1) & M32
        a = b ^ (b >> 9)
        b = (c + ((c << 3) & M32)) & M32
        c = ((c << 21) & M32) | (c >> 11)
        c = (c + t) & M32
        state[0], state[1], state[2], state[3] = a, b, c, d
        return t / 4294967296

    for _ in range(12):
        nxt()
    return nxt


def gauss(r):
    u = math.sqrt(-2 * math.log(r() + 1e-12))
    return u * math.cos(6.2831853 * r())


def qv(v):  # genes live on 256 steps, so they round-trip
    return js_round(clamp(v) * 255) / 255


# ---------- distance fields: negative inside ----------

def circle(x, y, cx, cy, r):
    return js_hypot(x - cx, y - cy) - r


def capsule(x, y, ax, ay, bx, by, r):
    vx, vy = bx - ax, by - ay
    den = vx * vx + vy * vy or 1
    t = clamp(((x - ax) * vx + (y - ay) * vy) / den)
    return js_hypot(x - ax - vx * t, y - ay - vy * t) - r


def smin(a, b, k):
    h = max(k - abs(a - b), 0) / k
    return min(a, b) - h * h * k / 4


def smax(a, b, k):
    return -smin(-a, -b, k)


def polygon(corners, radius):
    n = len(corners)

    def f(x, y):
        d, pos = 9, 0
        for i in range(n):
            ax, ay = corners[i]
            bx, by = corners[(i + 1) % n]
            d = min(d, capsule(x, y, ax, ay, bx, by, 0))
            if (bx - ax) * (y - ay) - (by - ay) * (x - ax) >= 0:
                pos += 1
        return (-d if pos == n or pos == 0 else d) - radius
    return f


# ---------- genome ----------
# s: 16 shape genes · f: 10 face genes · e: eye style · m: mouth style
# t: 8 antenna genes (t0 = has antennas) · a: 7 arm genes (a0 = has arms) · l: 7 leg genes (l0 = has legs) · c: color

NS, NF, NL, NT, NE = 16, 10, 7, 8, 9
PALETTE = ["#7ec8f0", "#9bd36a", "#f7a440", "#f48aa0", "#a77be0", "#ef5f57", "#5fd0c4", "#f5d14a",
           "#c2a6f0", "#ff9e7a", "#9aa6b2", "#3d4fb5", "#3f9a83", "#6b4fb8", "#e8453c", "#f2ce3a"]
ARMS_ON, LEGS_ON, ANT_ON = .6, .45, .55
LIMB_KEY = {"arms": "a", "legs": "l", "antennas": "t"}
LIMB_ON = {"arms": ARMS_ON, "legs": LEGS_ON, "antennas": ANT_ON}


def is_on(part, g):
    return g[LIMB_KEY[part]][0] >= LIMB_ON[part]


def hex_of(arr):
    return "".join(f"{js_round(v * 255):02x}" for v in arr)


def from_hex(h, n):
    return [int(h[2 * i:2 * i + 2], 16) / 255 for i in range(n)]


def genome(g):
    return f"s={hex_of(g['s'])} f={hex_of(g['f'])} e={g['e']} m={g['m']} t={hex_of(g['t'])} a={hex_of(g['a'])} l={hex_of(g['l'])} c={g['c']}"


def parse_genome(line):
    """A genome line -> genome dict. Raises ValueError on anything malformed."""
    import re
    kv = {}
    for tok in line.strip().split():
        i = tok.find("=")
        if i > 0:
            kv[tok[:i]] = tok[i + 1:]

    def hx(k, n):
        v = kv.get(k, "")
        if not re.fullmatch(f"[0-9a-f]{{{2 * n}}}", v):
            raise ValueError(k)
        return from_hex(v, n)

    def integer(k, n):
        v = kv.get(k, "")
        if not re.fullmatch(r"\d+", v) or not 0 <= int(v) < n:
            raise ValueError(k)
        return int(v)

    return {"s": hx("s", NS), "f": hx("f", NF), "e": integer("e", NE), "m": integer("m", 10),
            "t": hx("t", NT), "a": hx("a", NL), "l": hx("l", NL), "c": integer("c", len(PALETTE))}


# ---------- shape: 16 numbers -> one smooth body ----------

def shape_params(G):
    def lin(v, t):
        return 0 if v < t else (v - t) / (1 - t)
    aspect, bd = .72 + G[0] * .66, G[14] - .5
    return {
        "a": math.sqrt(aspect), "b": 1 / math.sqrt(aspect),
        "p": 2 + G[1] * G[1] * 4,
        "poly": lin(G[2], .5), "n": 3 + math.floor(G[3] * 5.99),
        "taper": (G[4] - .5) * 1.0,
        "lobe": lin(G[5], .45) * .3, "nl": 3 + math.floor(G[6] * 9.99), "sharp": .35 + G[7] * G[7] * 3.2,
        "ears": lin(G[8], .62), "earSpread": G[9],
        "arch": lin(G[10], .66), "cleft": lin(G[11], .72),
        "wob": G[12] * G[12] * .13, "ph": G[13] * 6.2832,
        "bend": 0 if abs(bd) < .22 else js_sign(bd) * (abs(bd) - .22) / .28 * .42,
        "rot": G[15],
    }


FAMILY_GENES = {"poly": (2, .5), "lobe": (5, .45), "ears": (8, .62), "arch": (10, .66), "cleft": (11, .72)}


def fam_of(s):
    P = shape_params(s)
    if P["lobe"]:
        return "estrella" if P["sharp"] > 1.5 else "flor"
    if P["arch"]:
        return "arco"
    if P["cleft"]:
        return "corazón"
    if P["poly"] > .45:
        return "triángulo" if P["n"] == 3 else "cuadro" if P["n"] == 4 else "polígono"
    if P["ears"]:
        return "orejas"
    if P["bend"]:
        return "frijol"
    return "bola"


def field(P):
    a, b, p, poly, n, taper = P["a"], P["b"], P["p"], P["poly"], P["n"], P["taper"]
    lobe, nl, sharp, ears, earSpread = P["lobe"], P["nl"], P["sharp"], P["ears"], P["earSpread"]
    arch, cleft, wob, ph, bend, rot = P["arch"], P["cleft"], P["wob"], P["ph"], P["bend"], P["rot"]
    polyF = None
    if poly > 0:
        r0, rr, corners = -math.pi / 2 + rot * 2 * math.pi / n, .3, []
        for i in range(n):
            t = r0 + 2 * math.pi * i / n
            corners.append([math.cos(t) * (a * 1.1 - rr * .5), math.sin(t) * (b * 1.1 - rr * .5)])
        polyF = polygon(corners, rr)
    amp, rotL = lobe * (1 + sharp * .35), rot * 2 * math.pi / nl - math.pi / 2
    earR, ey = .15 + ears * .2, -b * .92
    ex = (0 if earSpread < .25 else .22 + earSpread * .38) * a * max(.45, 1 - taper * .9 * b)
    archR, archTop, cleftR = (.1 + arch * .2) * a, b * (1 - arch * 1.0), .13 + cleft * .2

    def f(x0, y0):
        yb = y0 - bend * x0 * x0 + bend * .35
        x, y = x0, yb
        t = math.atan2(y, x)
        m = 1
        if amp:
            m += amp * (math.pow(.5 + .5 * math.cos(nl * (t - rotL)), sharp) - .45)
        if wob:
            m += (1 - min(.8, lobe * 3)) * wob * (math.cos(2 * t + ph) * .6 + math.cos(3 * t + ph * 1.7) * .4 + math.cos(5 * t + ph * 2.3) * .2)
        x /= m
        y /= m
        tx = x / max(.4, 1 + taper * y)
        tt = math.atan2(y, tx)
        c, s = abs(math.cos(tt)) / a, abs(math.sin(tt)) / b
        d = js_hypot(tx, y) - math.pow(math.pow(c, p) + math.pow(s, p), -1 / p)
        if polyF:
            d = d * (1 - poly) + polyF(tx, y) * poly
        d *= m
        if ears:
            d = smin(d, circle(x0, yb, ex, ey, earR), .22)
            if ex:
                d = smin(d, circle(x0, yb, -ex, ey, earR), .22)
        if arch:
            d = smax(d, -capsule(x0, yb, 0, b * 1.5, 0, archTop, archR), .12)
        if cleft:
            d = smax(d, -circle(x0, yb, 0, -b * 1.13, cleftR), .14)
        return d
    return f


# ---------- outline: marching squares, smooth, even points ----------

def trace(f, n=110, span=2.05):
    step = 2 * span / n
    xs = [-span + i * step for i in range(n + 1)]
    v = [[f(x, y) for x in xs] for y in xs]
    edges, at = {}, {}

    def cross(i0, j0, i1, j1):
        a, b = v[j0][i0], v[j1][i1]
        t = a / (a - b) if a != b else .5
        p = (xs[i0] + (xs[i1] - xs[i0]) * t, xs[j0] + (xs[j1] - xs[j0]) * t)
        key = js_fixed(p[0], 6) + "," + js_fixed(p[1], 6)
        at[key] = p
        return key

    def link(a, b):
        edges.setdefault(a, []).append(b)
        edges.setdefault(b, []).append(a)

    for j in range(n):
        for i in range(n):
            c = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            pts = []
            for k in range(4):
                p, q = c[k], c[(k + 1) % 4]
                if (v[p[1]][p[0]] < 0) != (v[q[1]][q[0]] < 0):
                    pts.append(cross(p[0], p[1], q[0], q[1]))
            for k in range(0, len(pts) - 1, 2):
                link(pts[k], pts[k + 1])
    best, seen = [], set()
    for start in edges:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = next((p for p in edges[cur] if p != prev and p not in seen), None)
            if nxt is None:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        if len(loop) > len(best):
            best = loop
    return [at[k] for k in best]


def smooth(pts, passes=2):
    for _ in range(passes):
        n = len(pts)
        pts = [((pts[(i - 1) % n][0] + 2 * q[0] + pts[(i + 1) % n][0]) / 4,
                (pts[(i - 1) % n][1] + 2 * q[1] + pts[(i + 1) % n][1]) / 4) for i, q in enumerate(pts)]
    return pts


def resample(pts, n=140):
    m = len(pts)
    seg = [js_hypot(pts[(i + 1) % m][0] - p[0], pts[(i + 1) % m][1] - p[1]) for i, p in enumerate(pts)]
    total = 0
    for x in seg:
        total += x
    out, i, walked = [], 0, 0
    for k in range(n):
        target = total * k / n
        while i < m - 1 and walked + seg[i] < target:
            walked += seg[i]
            i += 1
        t = (target - walked) / seg[i] if seg[i] else 0
        a, b = pts[i], pts[(i + 1) % m]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def area(pts):
    s = 0
    n = len(pts)
    for i, p in enumerate(pts):
        q = pts[(i + 1) % n]
        s = s + p[0] * q[1] - q[0] * p[1]
    return abs(s) / 2


def good_loop(l):
    return len(l) > 30 and area(l) > .8 and all(abs(x) < 1.98 and abs(y) < 1.98 for x, y in l)


def curve(pts):
    n = len(pts)
    d = [f"M{F(pts[0][0])} {F(pts[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        d.append(f"C{F(p1[0] + (p2[0] - p0[0]) / 6)} {F(p1[1] + (p2[1] - p0[1]) / 6)} {F(p2[0] - (p3[0] - p1[0]) / 6)} {F(p2[1] - (p3[1] - p1[1]) / 6)} {F(p2[0])} {F(p2[1])}")
    return " ".join(d) + "Z"


def inside(pts, x, y):
    c = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def edge_dist(pts, x, y):
    d = 1e9
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        d = min(d, capsule(x, y, a[0], a[1], b[0], b[1], 0))
    return d


# ---------- a body: path, depth inside, normals along the edge ----------

class Body:
    __slots__ = ("path", "pts", "normals", "depth", "deep", "ok", "minX", "maxX", "minY", "maxY", "bone")


_body_cache = {}


def body(s):
    key = hex_of(s)
    B = _body_cache.get(key)
    if B is not None:
        return B
    P = shape_params(s)
    loop = trace(field(P))
    ok = good_loop(loop)
    if not ok:
        P = dict(P, arch=0, cleft=0, ears=0, lobe=P["lobe"] * .5, wob=P["wob"] * .5)
        loop = trace(field(P))
        ok = good_loop(loop)
    if not ok:
        P = dict(P, lobe=0, wob=0, poly=0, bend=0)
        loop = trace(field(P))
        ok = good_loop(loop)
    raw = resample(smooth(loop, 2), 140)
    xs, ys = [p[0] for p in raw], [p[1] for p in raw]
    k = 72 / max(max(xs) - min(xs), max(ys) - min(ys))
    cx, miny = (max(xs) + min(xs)) / 2, min(ys)
    h = (max(ys) - miny) * k
    oy = 9 + (72 - h) / 2
    pts = [(50 + (x - cx) * k, oy + (y - miny) * k) for x, y in raw]
    depth, deep = [], 0
    for j in range(50):
        row = []
        for i in range(50):
            X, Y = 1 + 2 * i, 1 + 2 * j
            d = edge_dist(pts, X, Y) if inside(pts, X, Y) else 0
            row.append(d)
            deep = max(deep, d)
        depth.append(row)
    normals = []
    n = len(pts)
    for i, p in enumerate(pts):
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        nx, ny = b[1] - a[1], -(b[0] - a[0])
        l = js_hypot(nx, ny) or 1
        nx /= l
        ny /= l
        if inside(pts, p[0] + nx * 1.5, p[1] + ny * 1.5):
            nx, ny = -nx, -ny
        normals.append((nx, ny))
    B = Body()
    B.path, B.pts, B.normals, B.depth, B.deep, B.ok = curve(pts), pts, normals, depth, deep, ok
    B.minX, B.maxX = min(p[0] for p in pts), max(p[0] for p in pts)
    B.minY, B.maxY = min(p[1] for p in pts), max(p[1] for p in pts)
    B.bone = None
    _body_cache[key] = B
    if len(_body_cache) > 600:
        del _body_cache[next(iter(_body_cache))]
    return B


def depth_at(B, X, Y):
    i, j = js_round((X - 1) / 2), js_round((Y - 1) / 2)
    return 0 if i < 0 or j < 0 or i > 49 or j > 49 else B.depth[j][i]


def row_span(B, X, Y):
    j, i0 = int(clamp(js_round((Y - 1) / 2), 0, 49)), int(clamp(js_round((X - 1) / 2), 0, 49))
    if not B.depth[j][i0]:
        return 0, 0
    l = r = i0
    while l > 0 and B.depth[j][l - 1]:
        l -= 1
    while r < 49 and B.depth[j][r + 1]:
        r += 1
    return X - (1 + 2 * l), (1 + 2 * r) - X


# ---------- face ----------

INK = "#2a2230"


def eye_draw(e):  # bna1 eye -> drawing (lentes, 5, is gone)
    return e if e < 5 else e + 1


def eye_radius(e, f):
    z, st = f[0], eye_draw(e)
    if st == 6:
        return 5 + z * 4
    if st == 1:
        return 3.4 + z * 3.2
    if st == 9:
        return 3 + z * 2.5
    if st == 0:
        return 1.9 + z * 2
    if st == 2:
        return 2.4 + z * 1.9
    return 2.8 + z * 2


def eye_gap(f, e=None):
    base = 5.5 + f[1] * 5.5
    return base if e is None else max(base, eye_radius(e, f) * 1.18)


def eye_tall(e, f):
    return eye_radius(e, f) * {2: 1.5, 9: 1.2}.get(eye_draw(e), 1)


def mouth_y(f):
    return 6.5 + f[7] * 5


def socket_r(e, f):  # an eye socket: this wide, 1.15 times as tall
    return eye_radius(e, f) * 1.12 + .5


def mouth_outline(m, f):
    """The outline of each mouth as points around its center, and how far its line reaches past them."""
    w = 2.2 + f[6] * 3.4
    return [None,
            ([(-w, 0), (w, 0), (0, w * .45), (-w * .5, w * .34), (w * .5, w * .34)], 1.1),
            ([(0, 1)], w * .6),
            ([(-w * 1.1, 0), (w * 1.1, 0), (0, w * 1.5), (-w * .8, w * 1.1), (w * .8, w * 1.1), (0, 0)], .3),
            ([(-w * .7, 0), (w * .7, 0), (0, 0)], 1.1),
            ([(-w * .5, 0), (w * .5, 0), (0, w * .25)], 1),
            ([(-w, 0), (-w * .5, -1), (0, 0), (w * .5, 1), (w, 0)], 1.1),
            ([(-w, 0), (-w * .5, w * .35), (0, 0), (w * .5, w * .35), (w, 0)], 1.1),
            ([(-w, w * .5), (w, w * .5), (0, w * .05), (-w * .5, w * .16), (w * .5, w * .16)], 1.1),
            ([(-w, 0), (w, 0), (0, w * .45), (-1.4, w * .2), (1.4, w * .2), (-1.4, w * .2 + 2.6), (1.4, w * .2 + 2.6)], 1.1),
            ][m]


def inset_path(B, m):
    def at(x, y):  # distance to the skin, from the body's depth grid (bilinear)
        fx, fy = (x - 1) / 2, (y - 1) / 2
        i, j = math.floor(fx), math.floor(fy)
        u, v = fx - i, fy - j

        def D(a, b):
            return 0 if a < 0 or b < 0 or a > 49 or b > 49 else B.depth[b][a]
        return D(i, j) * (1 - u) * (1 - v) + D(i + 1, j) * u * (1 - v) + D(i, j + 1) * (1 - u) * v + D(i + 1, j + 1) * u * v

    loop = trace(lambda u, v: m - at(50 + u * 24.4, 50 + v * 24.4), 90)
    if len(loop) < 20:
        return None
    pts = resample(smooth([(50 + u * 24.4, 50 + v * 24.4) for u, v in loop], 3), 90)
    return None if area(pts) < 40 else {"pts": pts, "path": curve(pts)}


def bone_shape(B):
    """The body bone, worked out once per body: {pts, path}."""
    if B.bone:
        return B.bone
    r = None
    for m in (max(3.5, min(7, B.deep * .22)), 3, 2):
        r = inset_path(B, m)
        if r:
            break
    B.bone = r or {"pts": B.pts, "path": B.path}
    return B.bone


_TRIES = None


def _tries():
    global _TRIES
    if _TRIES is None:
        t = [(0, 0)]
        rr = 2
        while rr <= 24:
            for k in range(16):
                a = k / 16 * 6.283
                t.append((math.cos(a) * rr, math.sin(a) * rr))
            rr += 2
        t.sort(key=lambda p: js_hypot(p[0] * 1.6, p[1]))
        _TRIES = t
    return _TRIES


def place_face(B, g):
    f, cells = g["f"], []
    for j in range(50):
        for i in range(50):
            if B.depth[j][i]:
                cells.append((1 + 2 * i, 1 + 2 * j, B.depth[j][i]))
    cand = [c for c in cells if c[2] >= B.deep * .55]
    core = [c for c in cells if c[2] >= B.deep * .85]
    top = min(c[1] for c in cand)
    sy = sx = 0
    for c in core:
        sy += c[1]
    for c in core:
        sx += c[0]
    cy, cx = sy / len(core), sx / len(core)

    def row_x(y):
        row = [c for c in cells if abs(c[1] - y) <= 1.2 and c[2] >= B.deep * .4]
        if not row:
            return cx
        s = 0
        for c in row:
            s += c[0]
        return s / len(row)

    fy = top + 1 + (cy - top) * (.08 + .92 * f[2])
    fx = row_x(fy)
    l0, r0 = row_span(B, fx, fy)
    fx += (f[9] - .5) * 2 * min(l0, r0) * .3
    want, R, Rv = .9 + .8 * f[3], eye_radius(g["e"], f), eye_tall(g["e"], f)
    gp = [0] if eye_draw(g["e"]) == 6 else [-eye_gap(f, g["e"]), eye_gap(f, g["e"])]
    my = mouth_y(f)

    def fits(x, y, s):
        return all(depth_at(B, x + dx * s, y) >= max(R, Rv) * s * 1.18 + 1.2 and depth_at(B, x + dx * s, y - Rv * s) > 1 for dx in gp) \
            and (g["m"] == 0 or depth_at(B, x, y + my * s) > 2.6 * s)

    bone = bone_shape(B)
    bp, sock = bone["pts"], socket_r(g["e"], f) * 1.15

    def in_bone(x, y, s):
        for dx in gp:
            X = x + dx * s
            if not (inside(bp, X, y) and edge_dist(bp, X, y) >= sock * s + .8):
                return False
        return True

    mo = mouth_outline(g["m"], f) if g["m"] else None

    def mouth_in(x, y, s):
        if not mo:
            return True
        for px, py in mo[0]:
            X, Y = x + px * s, y + (my + py) * s
            if not (inside(bp, X, Y) and edge_dist(bp, X, Y) >= mo[1] * s + .6):
                return False
        return True

    def ok(x, y, s):
        return fits(x, y, s) and in_bone(x, y, s) and mouth_in(x, y, s)

    tries = _tries()
    state = {"s": want}

    def search(ox, oy, lo):
        while state["s"] >= lo:
            s = state["s"]
            for dx, dy in tries:
                if ok(ox + dx, oy + dy, s):
                    return (ox + dx, oy + dy)
            state["s"] *= .93
        return None

    found = search(fx, fy, want * .6)
    if not found:
        state["s"] = want * .6
        found = search(cx, cy - 2, want * .3)
    if found:
        fx, fy = found
        s = state["s"]
    else:
        fx, fy, s = cx, cy - 2, want * .3
    return {"x": fx, "y": fy, "s": s, "fit": bool(found)}


def eyes_svg(e0, f):
    e = eye_draw(e0)
    z, g = f[0], eye_gap(f, e0)
    lx, ly = clamp((f[4] - .5) * 2 + (f[9] - .5) * .8, -1, 1), (f[5] - .5) * 1.6

    def dot(x, r, y=0, fill="K"):
        return f'<circle cx="{F(x)}" cy="{F(y)}" r="{F(r)}" fill="{fill}"/>'

    def wh(x, r, y=0):
        return f'<circle cx="{F(x)}" cy="{F(y)}" r="{F(r)}" fill="#fff"/>'

    def arc(x, w, up):
        return f'<path d="M{F(x - w)} {F(w * .4 * up)}q{F(w)} {F(-w * 1.1 * up)} {F(2 * w)} 0" stroke="K" stroke-width="2.3" fill="none" stroke-linecap="round"/>'

    def pupil(x, R, px=lx):
        return wh(x, R) + dot(x + px * R * .38, R * .56, ly * R * .38, INK)

    def shine(x, r):
        return dot(x, r) + f'<circle cx="{F(x - r * .35)}" cy="{F(-r * .38)}" r="{F(r * .36)}" fill="#fff"/>'

    if e == 0:
        r = 1.9 + z * 2
        return dot(-g, r) + dot(g, r)
    if e == 1:
        R = 3.4 + z * 3.2
        return pupil(-g, R) + pupil(g, R)
    if e == 2:
        rx = 2 + z * 1.6
        ry = rx * 1.5

        def o(x):
            return f'<ellipse cx="{F(x)}" cy="0" rx="{F(rx)}" ry="{F(ry)}" fill="K"/><circle cx="{F(x - rx * .3)}" cy="{F(-ry * .4)}" r="{F(rx * .35)}" fill="#fff"/>'
        return o(-g) + o(g)
    if e == 3:
        w = 2.8 + z * 2
        return arc(-g, w, 1) + arc(g, w, 1)
    if e == 4:
        w = 2.8 + z * 2
        return arc(-g, w, -1) + arc(g, w, -1)
    if e == 5:
        w = 2.6 + z * 2
        hh = w * .8

        def r(x):
            return f'<rect x="{F(x - w)}" y="{F(-hh)}" width="{F(2 * w)}" height="{F(hh * 1.7)}" rx="{F(hh * .7)}" fill="{INK}"/>'
        return r(-g) + r(g) + f'<path d="M{F(-g + w * .6)} {F(-hh * .5)}H{F(g - w * .6)}" stroke="{INK}" stroke-width="1.6"/><path d="M{F(-g - w * .5)} {F(-hh * .2)}l{F(w * .6)} {F(-hh * .5)}M{F(g - w * .5)} {F(-hh * .2)}l{F(w * .6)} {F(-hh * .5)}" stroke="#fff" stroke-width="1" stroke-linecap="round" opacity=".7"/>'
    if e == 6:
        return pupil(0, 5 + z * 4)
    if e == 7:
        r = 2.4 + z * 2
        return shine(-g, r) + shine(g, r)
    if e == 8:
        r = 2.2 + z * 1.8
        return shine(-g, r) + arc(g, r + 1, 1)
    rx = 3 + z * 2.5
    ry = rx * 1.2

    def o2(x, px):
        return f'<ellipse cx="{F(x)}" cy="0" rx="{F(rx)}" ry="{F(ry)}" fill="#fff"/>' + dot(x + px * rx * .4, rx * .5, ly * ry * .3, INK)
    return o2(-g, .7) + o2(g, -.7)


def mouth_svg(m, f):
    w = 2.2 + f[6] * 3.4

    def line(d, width=2.2):
        return f'<path d="{d}" stroke="K" stroke-width="{width}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    if m == 0:
        return ""
    if m == 1:
        return line(f"M{F(-w)} 0q{F(w)} {F(w * .9)} {F(2 * w)} 0")
    if m == 2:
        return f'<ellipse cx="0" cy="1" rx="{F(w * .55)}" ry="{F(w * .6)}" fill="K"/>'
    if m == 3:
        return f'<path d="M{F(-w * 1.1)} 0h{F(w * 2.2)}q0 {F(w * 1.5)} {F(-w * 1.1)} {F(w * 1.5)}q{F(-w * 1.1)} 0 {F(-w * 1.1)} {F(-w * 1.5)}z" fill="{INK}"/><path d="M{F(-w * .55)} {F(w * 1.25)}q{F(w * .55)} {F(-w * .7)} {F(w * 1.1)} 0" fill="#e86a7a"/>'
    if m == 4:
        return line(f"M{F(-w * .7)} 0h{F(w * 1.4)}")
    if m == 5:
        return line(f"M{F(-w * .5)} 0q{F(w * .5)} {F(w * .5)} {F(w)} 0", 2)
    if m == 6:
        return line(f"M{F(-w)} 0q{F(w * .5)} -2 {F(w)} 0t{F(w)} 0")
    if m == 7:
        return line(f"M{F(-w)} 0q{F(w * .5)} {F(w * .7)} {F(w)} 0q{F(w * .5)} {F(w * .7)} {F(w)} 0")
    if m == 8:
        return line(f"M{F(-w)} {F(w * .5)}q{F(w)} {F(-w * .9)} {F(2 * w)} 0")
    return line(f"M{F(-w)} 0q{F(w)} {F(w * .9)} {F(2 * w)} 0") + f'<rect x="-1.4" y="{F(w * .2)}" width="2.8" height="2.6" rx=".6" fill="#fff"/>'


# ---------- arms and legs ----------

def rot(v, t):
    x, y = v
    return (x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t))


def norm(v):
    x, y = v
    l = js_hypot(x, y) or 1
    return (x / l, y / l)


def limb_path(N, D, L, curl, w, mirror):
    E = (D[0] * L, D[1] * L)
    P = (-D[1], D[0])
    c = curl * (-1 if mirror else 1)
    c1 = (N[0] * L * .4, N[1] * L * .4)
    c2 = (E[0] - D[0] * L * .35 + P[0] * c * L * .55, E[1] - D[1] * L * .35 + P[1] * c * L * .55)
    return E, f'<path d="M0 0C{F(c1[0])} {F(c1[1])} {F(c2[0])} {F(c2[1])} {F(E[0])} {F(E[1])}" stroke="D" stroke-width="{F(w)}" fill="none" stroke-linecap="round"/>'


def arms(B, g, face):
    a = g["a"]
    L, w = 7 + a[2] * 13, 3 + a[3] * 2.8
    Y = face["y"] + (B.maxY - face["y"]) * (.12 + .62 * a[1])
    swing = (-55 + a[4] * 130) * math.pi / 180
    curl = (-1 if a[5] < .5 else 1) * (.3 + abs(a[5] - .5) * 1.2)
    out = {}
    for side in (-1, 1):
        idx = -1
        for i, p in enumerate(B.pts):
            if abs(p[1] - Y) < 2.6 and (idx < 0 or (p[0] - B.pts[idx][0]) * side > 0):
                idx = i
        if idx < 0:
            m = 0
            for i, p in enumerate(B.pts):
                if p[0] * side > B.pts[m][0] * side:
                    m = i
            idx = m
        A, N = B.pts[idx], B.normals[idx]
        if N[0] * side < .2:
            N = norm((N[0] + side * .8, N[1]))
        D = rot(N, swing * (-1 if N[0] < 0 else 1))
        E, svg = limb_path(N, D, L, curl, w, side > 0)
        hand = f'<circle cx="{F(E[0])}" cy="{F(E[1])}" r="{F(w * .66)}" fill="D"/>' if a[6] > .55 else ""
        out["arm-left" if side < 0 else "arm-right"] = (A[0] - N[0] * w * .6, A[1] - N[1] * w * .6, svg + hand)
    return out


def legs(B, g):
    l = g["l"]
    w, W, cx = 3.2 + l[3] * 2.8, B.maxX - B.minX, (B.maxX + B.minX) / 2
    curl = (-1 if l[5] < .5 else 1) * (.25 + abs(l[5] - .5) * 1.1)
    splay = l[4] * .75
    out = {}
    for side in (-1, 1):
        hx = cx + side * (.1 + l[1] * .26) * W
        idx = -1
        for i, p in enumerate(B.pts):
            if abs(p[0] - hx) < 2.6 and (idx < 0 or p[1] > B.pts[idx][1]):
                idx = i
        if idx < 0:
            m = 0
            for i, p in enumerate(B.pts):
                if p[1] > B.pts[m][1]:
                    m = i
            idx = m
        A, N = B.pts[idx], B.normals[idx]
        D = norm((side * splay + N[0] * .25, 1 + max(0, N[1]) * .25))
        ax, ay = A[0] - N[0] * w * .9, A[1] - N[1] * w * .9
        foot = w * .6 if l[6] > .5 else 0
        L = min(6 + l[2] * 12, (97 - foot - ay) / max(.5, D[1]))
        E, svg = limb_path((0, 1), D, L, curl, w, side > 0)
        shoe = f'<ellipse cx="{F(E[0] + side * w * .45)}" cy="{F(E[1])}" rx="{F(w * (.85 + (l[6] - .5) * .8))}" ry="{F(w * .6)}" fill="D"/>' if foot else ""
        out["leg-left" if side < 0 else "leg-right"] = (ax, ay, svg + shoe)
    return out


def antenna_svg(style, D, L, bend, w, tip):
    E = (D[0] * L, D[1] * L)
    P = (-D[1], D[0])
    C1 = (D[0] * L * .45 + P[0] * bend * L * .45, D[1] * L * .45 + P[1] * bend * L * .45)

    def stem(Ln=1, width=w):
        return f'<path d="M0 0Q{F(C1[0] * Ln)} {F(C1[1] * Ln)} {F(E[0] * Ln)} {F(E[1] * Ln)}" stroke="D" stroke-width="{F(width)}" fill="none" stroke-linecap="round"/>'
    ang = math.atan2(D[1], D[0]) * 180 / math.pi

    def leaf(x, y, a, rx, ry):
        return f'<ellipse cx="0" cy="0" rx="{F(rx)}" ry="{F(ry)}" fill="D" transform="translate({F(x)} {F(y)}) rotate({F(a)}) translate({F(rx * .8)} 0)"/>'
    if style == 0:
        return stem(1, w * .7)
    if style == 1:
        return stem() + f'<circle cx="{F(E[0])}" cy="{F(E[1])}" r="{F(2.2 * tip)}" fill="D"/>'
    if style == 2:
        return stem(.8) + leaf(E[0] * .8, E[1] * .8, ang + bend * 25, 3.4 * tip, 1.6 * tip)
    if style == 3:
        r = 2 * tip
        s = 0 if bend < 0 else 1
        k = 1 if s else -1
        return stem() + f'<path d="M{F(E[0])} {F(E[1])}a{F(r)} {F(r)} 0 1 {s} {F(P[0] * r * 2 * k)} {F(P[1] * r * 2 * k)}" stroke="D" stroke-width="{F(w)}" fill="none" stroke-linecap="round"/>'
    if style == 4:
        parts = []
        for da in (-.45, 0, .45):
            d = rot(D, da)
            l = L * (.7 if da else .85)
            parts.append(f'<path d="M0 0q{F(d[0] * l * .5 + P[0] * bend * l * .3)} {F(d[1] * l * .5 + P[1] * bend * l * .3)} {F(d[0] * l)} {F(d[1] * l)}" stroke="D" stroke-width="{F(w * .7)}" fill="none" stroke-linecap="round"/>')
        return "".join(parts)
    return stem(.65) + leaf(E[0] * .65, E[1] * .65, ang - 40, 2.6 * tip, 1.3 * tip) + leaf(E[0] * .65, E[1] * .65, ang + 40, 2.6 * tip, 1.3 * tip)


def antennas(B, g):
    t = g["t"]
    two, style = t[2] >= .5, min(5, math.floor(t[1] * 6))
    L, bend, spread, side, tip, w = 5 + t[3] * 11, (t[4] - .5) * 2, t[5], (t[6] - .5) * 2, .75 + t[7] * .9, 2.2
    Wd, cx = B.maxX - B.minX, (B.maxX + B.minX) / 2
    xs = [cx + k * (.08 + spread * .2) * Wd + side * Wd * .1 for k in (-1, 1)] if two else [cx + side * Wd * .25]
    out = {}
    for k, hx in enumerate(xs):
        idx = -1
        for i, p in enumerate(B.pts):
            if abs(p[0] - hx) < 2.6 and (idx < 0 or p[1] < B.pts[idx][1]):
                idx = i
        if idx < 0:
            m = 0
            for i, p in enumerate(B.pts):
                if p[1] < B.pts[m][1]:
                    m = i
            idx = m
        A, N = B.pts[idx], B.normals[idx]
        lean = (1 if k else -1) * (.15 + spread * .45) if two else side * .3
        D = norm((N[0] * .5 + lean, min(N[1], -.3) - .6))
        Lk = max(3, min(L, (A[1] - 2 - 2.5 * tip) / max(.4, -D[1])))
        out[f"antenna-{k + 1}"] = (A[0] - N[0] * 1.2, A[1] - N[1] * 1.2, antenna_svg(style, D, Lk, -bend if two and not k else bend, w, tip))
    return out


# ---------- the whole creature ----------

def dark(color, k=.76):
    return "#" + "".join(f"{math.floor(int(color[i:i + 2], 16) * k):02x}" for i in (1, 3, 5))


def lum(c):
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return .3 * r + .59 * g + .11 * b


def svg_doc(box, inner, extra=""):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}"{extra}>{inner}</svg>\n'


def paint(s, c):
    return s.replace('"C"', f'"{c}"').replace('"D"', f'"{dark(c)}"').replace('"K"', f'"{"#fff" if lum(c) < .42 else INK}"')


LIMB_IDS = ("antenna-1", "antenna-2", "leg-left", "leg-right", "arm-left", "arm-right")


def render(g):
    """genome -> {'creature': svg string, 'ok': bool}. The SVG is the page's creature.svg, byte for byte."""
    B = body(g["s"])
    face = place_face(B, g)
    color = PALETTE[g["c"]]
    limbs = {}
    if is_on("antennas", g):
        limbs.update(antennas(B, g))
    if is_on("legs", g):
        limbs.update(legs(B, g))
    if is_on("arms", g):
        limbs.update(arms(B, g, face))
    groups = []

    def put(id_, x, y, s, inner):
        groups.append(f'<g id="{id_}" transform="translate({F(x)} {F(y)}){"" if s == 1 else f" scale({F(s)})"}">{inner}</g>')

    for id_ in LIMB_IDS:
        if id_ in limbs:
            x, y, svg = limbs[id_]
            put(id_, x, y, 1, svg)
    groups.append(f'<g id="body"><path d="{B.path}" fill="C"/></g>')
    s, g9 = face["s"], eye_gap(g["f"], g["e"])
    if g["f"][8] > .62:
        bx, my = (7 if g["e"] == 5 else g9 + 1.5), mouth_y(g["f"]) * .45 + 1.5
        put("blush", face["x"], face["y"], s, f'<ellipse cx="{F(-bx)}" cy="{F(my)}" rx="3" ry="1.8" fill="#ff6f86" opacity=".45"/><ellipse cx="{F(bx)}" cy="{F(my)}" rx="3" ry="1.8" fill="#ff6f86" opacity=".45"/>')
    put("eyes", face["x"], face["y"], s, eyes_svg(g["e"], g["f"]))
    if g["m"]:
        put("mouth", face["x"], face["y"] + mouth_y(g["f"]) * s, s, mouth_svg(g["m"], g["f"]))
    creature = paint(svg_doc("0 0 100 100", "".join(groups), f' data-genome="{genome(g)}"'), color)
    return {"creature": creature, "ok": B.ok and face["fit"]}


_fit_cache = {}


def good_blob(g):
    """A blob is made only if its body traced well and its face (eye sockets and mouth too) fits inside the bone."""
    B = body(g["s"])
    if not B.ok:
        return False
    key = hex_of(g["s"]) + hex_of(g["f"]) + str(g["e"]) + "." + str(g["m"])
    v = _fit_cache.get(key)
    if v is None:
        v = place_face(B, g)["fit"]
        _fit_cache[key] = v
        if len(_fit_cache) > 4000:
            del _fit_cache[next(iter(_fit_cache))]
    return v
