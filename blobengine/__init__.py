"""
blobengine: make blobs from a blober filter (.bna).

    from blobengine import BlobEngine, Blob, new_blob

    engine = BlobEngine.load("mine.bna")     # the votes you trained in blober
    blob = engine.new_blob()                 # one that fits your taste
    blob.save("avatar.png")                  # profile picture, 512 × 512
    print(blob.genome)                       # the line that makes it again

    Blob.from_genome("s=… f=… e=3 m=1 …").save("same.png")   # any genome, same drawing as the page
"""
from .core import VERSION, PALETTE, genome, parse_genome, render, good_blob
from .engine import Blob, BlobEngine, new_blob

__all__ = ["Blob", "BlobEngine", "new_blob", "PALETTE", "VERSION", "genome", "parse_genome", "render", "good_blob"]
__version__ = "1.0.0"
