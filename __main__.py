"""
python -m blobengine mine.bna                    one new blob -> blob.png
python -m blobengine mine.bna -n 6 -o avatars    six, in a folder
python -m blobengine --genome "s=… c=3" -o a.png draw a given genome
python -m blobengine                             no .bna: random blobs
"""
import argparse
import os
import sys

from .engine import Blob, BlobEngine


def main(argv=None):
    ap = argparse.ArgumentParser(prog="blobengine", description="Make blobs from a blober filter (.bna).")
    ap.add_argument("bna", nargs="?", help="the .bna saved from blober (leave out for random blobs)")
    ap.add_argument("-n", type=int, default=1, help="how many (default 1)")
    ap.add_argument("-o", "--out", default=None, help="output file (one blob) or folder (several)")
    ap.add_argument("--seed", default=None, help="same seed + same .bna = same blobs")
    ap.add_argument("--color", default=None, help="palette index 0-15 or #rrggbb from the palette")
    ap.add_argument("--genome", default=None, help="draw this genome line instead of making a new one")
    ap.add_argument("--size", type=int, default=512, help="PNG side in pixels (default 512)")
    ap.add_argument("--background", default="auto", help='"auto", "#rrggbb", or "none" for transparent')
    ap.add_argument("--no-shadow", action="store_true", help="no floor shadow")
    ap.add_argument("--circle", action="store_true", help="cut the picture to a circle (transparent corners)")
    ap.add_argument("--fit", choices=["circle", "square"], default="circle", help="fit the round profile crop (default) or fill the square")
    ap.add_argument("--svg", action="store_true", help="save SVG instead of PNG")
    a = ap.parse_args(argv)

    color = int(a.color) if a.color and a.color.isdigit() else a.color
    if a.genome:
        blobs = [Blob.from_genome(a.genome)]
    else:
        engine = BlobEngine.load(a.bna) if a.bna else BlobEngine()
        blobs = engine.new_blobs(a.n, seed=a.seed, color=color) if a.n > 1 else [engine.new_blob(seed=a.seed, color=color)]
    ext = ".svg" if a.svg else ".png"
    kw = {} if a.svg else {"size": a.size, "background": None if a.background == "none" else a.background,
                          "shadow": not a.no_shadow, "circle": a.circle, "fit": a.fit}
    if len(blobs) == 1 and (a.out is None or not os.path.isdir(a.out)) and not (a.out or "").endswith(os.sep):
        paths = [a.out or "blob" + ext]
    else:
        folder = a.out or "blobs"
        os.makedirs(folder, exist_ok=True)
        paths = [os.path.join(folder, f"blob-{i + 1:03d}{ext}") for i in range(len(blobs))]
    for b, p in zip(blobs, paths):
        b.save(p, **kw)
        print(f"{p}\t{b.genome}")


if __name__ == "__main__":
    sys.exit(main())
