"""
blobengine.engine: load a .bna (the filter you trained in blober), ask for new blobs, get them as SVG or PNG.

    from blobengine import BlobEngine
    engine = BlobEngine.load("mine.bna")
    blob = engine.new_blob()
    blob.save("avatar.png")
"""
import io
import math
import os
import random as _random
import time

from .core import PALETTE, genome, parse_genome, render, good_blob, seeded, fam_of
from .brain import (Brain, PARTS, LIKE, compose, random_part, gen_part, choose, tuning, to_bna1)


# ---------- one blob ----------

class Blob:
    """One creature. Made from a genome line; the same line always draws the same blob, here and in the page."""

    def __init__(self, g):
        self.g = g
        self._svg = None

    @classmethod
    def from_genome(cls, line):
        return cls(parse_genome(line))

    @property
    def genome(self):
        """The line that makes it again (paste it in any blobengine, or keep it as the blob's id)."""
        return genome(self.g)

    @property
    def family(self):
        return fam_of(self.g["s"])

    @property
    def color(self):
        return PALETTE[self.g["c"]]

    @property
    def svg(self):
        """The creature as SVG, 100 × 100 units: the same file as the page's creature.svg."""
        if self._svg is None:
            self._svg = render(self.g)["creature"]
        return self._svg

    def bounds(self):
        """Where the drawing really is, in creature units (x0, y0, x1, y1). Limbs may reach past the 100 × 100 canvas."""
        if getattr(self, "_bounds", None) is None:
            probe = _raster(_wide(self.svg), 600)                # 200 × 200 units around the canvas, 3 px per unit
            box = probe.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox() or (240, 220, 360, 380)
            u = 200 / 600
            self._bounds = (-50 + box[0] * u, -50 + box[1] * u, -50 + box[2] * u, -50 + box[3] * u)
        return self._bounds

    def png(self, size=512, background="auto", shadow=True, padding=.06, circle=False, fit="circle"):
        """
        The blob as a profile picture, centered on a square; nothing of it is cut, outstretched arms included.
          size        side in pixels
          background  "auto" (a soft tint of the blob's color), any "#rrggbb", or None for transparent
          shadow      the soft floor shadow under it, as in the page
          padding     empty margin around it, as a fraction of the side (circle=True adds what the round cut needs)
          circle      cut to a circle, corners transparent
          fit         "circle" (default): the blob fits inside the round crop most apps apply to a profile picture,
                      as big as its real outline allows; "square": it fills the square
        """
        from PIL import Image, ImageDraw, ImageChops

        x0, y0, x1, y1 = self.bounds()
        bw, bh = x1 - x0, y1 - y0
        from .core import body as _body
        B = _body(self.g["s"])
        sw = (B.maxX - B.minX)                                   # the shadow follows the body, as in the page
        sh = sw * .1 if shadow else 0                            # how far it reaches below the feet
        cw, ch = max(bw, sw * .84 if shadow else 0), bh + sh     # what has to fit
        avail = size * (1 - 2 * padding)
        k = avail / max(cw, ch)                                  # pixels per creature unit: fits the square
        if fit == "circle" or circle:                            # fits the circle: the farthest point of the real outline
            k = min(k, avail / 2 / self._reach(cw, ch, x0, y0, sw if shadow else 0, B))
        ox = (size - bw * k) / 2 - x0 * k                        # where the canvas origin lands
        oy = (size - ch * k) / 2 - y0 * k
        bg = _tint(self.color) if background == "auto" else background
        out = Image.new("RGBA", (size, size), _rgba(bg) if bg else (0, 0, 0, 0))
        if shadow:
            ss = 4                                               # drawn 4× and shrunk, for a soft edge
            layer = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
            cx, cy = (ox + (B.minX + B.maxX) / 2 * k) * ss, (oy + y1 * k) * ss
            rx, ry = sw * .42 * k * ss, sw * .1 * k * ss
            ImageDraw.Draw(layer).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(0, 0, 0, 41))
            out.alpha_composite(layer.resize((size, size), Image.LANCZOS))
        px = max(1, int(math.ceil(200 * k)))                     # the wide canvas, sharp at this scale
        art = _raster(_wide(self.svg), px)
        out.alpha_composite(art, (int(round(ox - 50 * k)), int(round(oy - 50 * k))))
        if circle:
            ss = 4
            mask = Image.new("L", (size * ss, size * ss), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
            out.putalpha(ImageChops.multiply(out.getchannel("A"), mask.resize((size, size), Image.LANCZOS)))
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return buf.getvalue()

    def _reach(self, cw, ch, x0, y0, sw, B):
        """How far (in units) the drawing and its shadow reach from the center of what is laid out."""
        probe = _raster(_wide(self.svg), 300)                    # 1.5 px per unit is plenty to find the farthest point
        a = probe.getchannel("A").point(lambda v: 255 if v > 40 else 0)
        u, mx, my = 200 / 300, (x0 + self.bounds()[2]) / 2, y0 + ch / 2   # the layout centers the drawing across, drawing+shadow down
        w, data, far = a.size[0], a.getdata(), 0.0
        for i, v in enumerate(data):
            if v:
                X, Y = -50 + (i % w + .5) * u, -50 + (i // w + .5) * u
                d = (X - mx) ** 2 + (Y - my) ** 2
                if d > far:
                    far = d
        far = far ** .5
        if sw:                                                   # the shadow: an ellipse under the feet
            cx, cy, rx, ry = (B.minX + B.maxX) / 2, self.bounds()[3], sw * .42, sw * .1
            for k in range(64):
                t = k / 64 * 6.2832
                far = max(far, ((cx + rx * math.cos(t) - mx) ** 2 + (cy + ry * math.sin(t) - my) ** 2) ** .5)
        return far + 1

    def framed_svg(self, margin=3):
        """The SVG with its view fitted to the whole drawing (limbs that reach past the canvas included)."""
        x0, y0, x1, y1 = self.bounds()
        return self.svg.replace('viewBox="0 0 100 100"', f'viewBox="{x0 - margin:.1f} {y0 - margin:.1f} {x1 - x0 + 2 * margin:.1f} {y1 - y0 + 2 * margin:.1f}"', 1)

    def save(self, path, **kw):
        """Save as .png (profile picture, options as in png()) or .svg."""
        if str(path).lower().endswith(".svg"):
            data = self.framed_svg().encode("utf-8")
        else:
            data = self.png(**kw)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def __repr__(self):
        return f"Blob({self.family}, {self.color}, '{self.genome}')"


def _raster(svg, px):
    """SVG -> RGBA PIL image, px × px. Uses resvg-py, or cairosvg if that is what is installed."""
    from PIL import Image
    try:
        import resvg_py
        data = resvg_py.svg_to_bytes(svg_string=svg, width=px, height=px)
    except ImportError:
        try:
            import cairosvg
            data = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=px, output_height=px)
        except ImportError:
            raise RuntimeError("blobengine needs an SVG renderer for PNG: pip install resvg-py (or cairosvg)") from None
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _wide(svg):
    """The same drawing on a 200 × 200 view around the canvas, so nothing that reaches past it is cut."""
    return svg.replace('viewBox="0 0 100 100"', 'viewBox="-50 -50 200 200"', 1)


def _rgba(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + ((int(c[6:8], 16),) if len(c) == 8 else (255,))


def _tint(color, k=.8):
    r, g, b, _ = _rgba(color)
    return "#%02x%02x%02x" % tuple(int(round(v + (255 - v) * k)) for v in (r, g, b))


# ---------- the engine ----------

class BlobEngine:
    """
    Holds one filter (the votes of a .bna) and makes new blobs from it, the way the page does
    when one falls: most are bred from what you liked, one in five is pure chance.
    An engine with no .bna makes random blobs.
    """

    def __init__(self, text=""):
        self.brain = Brain()
        self.favorites = []
        self.gone = 0
        if text:
            self.read(text)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(f.read())

    def read(self, text):
        """Add a .bna's votes, favorites ("fav ...") and kill count ("# gone N"). Returns how many new votes."""
        import re
        seen = {f"{e['kind']} {e['part']} {e['s']}" for e in self.brain.events}
        votes = []
        for raw in (text or "").split("\n"):
            line = raw.strip()
            if line.startswith("fav "):
                s = line[4:]
                try:
                    parse_genome(s)
                    if s not in self.favorites:
                        self.favorites.append(s)
                except ValueError:
                    pass
                continue
            m = re.match(r"^# gone (\d+)", line)
            if m:
                self.gone = max(self.gone, int(m.group(1)))
                continue
            for v in to_bna1(line):
                if v not in seen:
                    seen.add(v)
                    votes.append(v)
        return self.brain.read("\n".join(votes))

    @property
    def votes(self):
        return len(self.brain.events)

    def polish(self):
        return min(3, len(self.brain.events) // 150)

    def new_blob(self, seed=None, color=None):
        """
        A new blob that fits the filter.
          seed   any string or number: the same seed with the same .bna gives the same blob
          color  a palette index (0-15) or one of its colors ("#7ec8f0"); by default, any color
        """
        r = seeded(seed) if seed is not None else seeded(f"{time.time_ns()}|{_random.random()}")
        c = _color_index(color)
        t0 = tuning(self.brain, self.polish())
        t = {"explore": max(.3, t0["explore"]), "sigma": max(.06, t0["sigma"]), "temp": max(.8, t0["temp"])}
        novel = r() < .2                                  # one in five is pure chance and skips the filter
        for _ in range(8):
            cands = []
            for _i in range(1 if novel else 24):
                g = compose(*[random_part(p, r) if novel or p == "color" else gen_part(self.brain, p, r, t) for p in PARTS])
                if c is not None:
                    g["c"] = c
                score = 0
                for p in LIKE:
                    score += self.brain.score(p, g)
                cands.append({"g": g, "score": score})
            picked = choose(cands, 1, t["temp"], r)
            if picked and good_blob(picked[0]):
                return Blob(picked[0])
        for _ in range(200):                              # the filter found nothing that fits: chance, but a proper one
            g = compose(*[random_part(p, r) for p in PARTS])
            if c is not None:
                g["c"] = c
            if good_blob(g):
                return Blob(g)
        return Blob(g)

    def new_blobs(self, n, seed=None, color=None):
        """n new blobs (with a seed: the same n every time)."""
        return [self.new_blob(seed=None if seed is None else f"{seed}|{i}", color=color) for i in range(n)]


def _color_index(color):
    if color is None:
        return None
    if isinstance(color, int):
        if not 0 <= color < len(PALETTE):
            raise ValueError(f"color index must be 0-{len(PALETTE) - 1}")
        return color
    c = str(color).lower()
    if c in PALETTE:
        return PALETTE.index(c)
    raise ValueError(f"color must be a palette index or one of {PALETTE}")


def new_blob(bna=None, seed=None, color=None):
    """One-liner: new_blob("mine.bna") -> Blob. bna may be a path, the .bna text, or None (random)."""
    if bna is None:
        return BlobEngine().new_blob(seed=seed, color=color)
    if os.path.exists(str(bna)):
        return BlobEngine.load(bna).new_blob(seed=seed, color=color)
    return BlobEngine(str(bna)).new_blob(seed=seed, color=color)
