# blober

**Play here: https://mrtatiso.github.io/blober/**

**On your phone:** open it and add it to your home screen (Safari: share → Add to Home Screen; Chrome: ⋮ → Install app). It opens full screen with its own yellow icon and works offline.

An endless white floor, and blobs that fall from the sky.

**blober is the filter.** Every blob you pat, send off in hearts, or get rid of is a vote. The page learns your taste, and the blobs that fall look more and more like the ones you like. One in five is still pure chance, so something new keeps showing up.

**And then you play with them.** The **▶** button opens the games. Each one is made of your blobs and reads the same `.bna`.

## How to play

Double click (or double tap) the start screen and the first one falls.

| | mouse | touch |
|---|---|---|
| drop a blob | double click the floor | double tap the floor |
| move or throw it | drag | drag |
| a pat | click | tap |
| scare it | right click | double tap |
| **more like this** (it leaves happy) | double click | press and hold, slide to ♥ |
| **no more like this** | double right click | press and hold, slide to 💔 |
| move around | drag the floor | drag the floor, or two fingers |
| zoom | scroll | pinch |

On touch, holding a finger on a blob brings up ♥ and 💔 around it: slide to one without lifting, and let go. Let go anywhere else and nothing happens.

The more you clean up, the more ways to go get unlocked.

## The `···` menu

- **controls:** the rules, any time.
- **photograph:** the cursor turns into a camera. Click a blob to download its profile picture: a 512 × 512 PNG drawn from its vector (not a screenshot), whole, and laid out to fit a round avatar.
- **save / load:** your filter (your votes, favorites and how many are gone, plus where you are in the games) as a `.bna` file. Take it to another computer, or share it.
- **save to a folder…** (Chrome and Edge): pick a folder once, and the page keeps `blober.bna` there, updated after every vote. When you come back, the browser may ask again: `···` → reconnect.

Your filter stays in your browser. Nothing is sent anywhere.

## ▶ Games

### blobslinger

**Play here: https://mrtatiso.github.io/blober/blobslinger.html** (or **▶** → blobslinger)

Throw the ones you like at the ones you don't.

- **Yours, happy:** you throw your favorites and the blobs you said "more like this" to. They come in their own colors, and a gray one gets a color you liked in blober instead. They smile, hop on the band, put their arms up in the air, and cheer every time one of the others falls.
- **The ones you got rid of, gray and sad:** every "no more like this" comes back without its color, frowning, with its arms hanging. They watch your blob fly at them.
- **Endless rounds:** each round is built from its number, so a given round always has the same layout. Rounds get bigger and harder: more groups, towers, walls, pyramids, houses. Pieces are soft, hard or glass.
- **One hit:** whatever your blob hits, a sad one or a block, breaks. Your blob bounces off and stays where it lands.
- **Always possible:** one sad one more each few rounds, up to 9, with one blob more than sad ones (10 at most).
- **How each blob plays comes from its genome:** shape sets its weight and bounce, legs and arms its grip, spikes and ears how hard it hits.

| | mouse | touch |
|---|---|---|
| aim | drag the blob on the band down and away | same |
| throw | let go | let go |
| call it off | drag it back up | same |
| move around | drag anywhere else | drag, or two fingers |
| zoom | scroll | pinch |
| restart the round | `↺` or `R` | `↺` |

Clear every sad one to go on: each blob you didn't need is worth 1,000 points. Run out of blobs and the round starts again.

Its `···` menu has **save .bna** and **load .bna**, the same file as blober's. Loading one adds its blobs to yours and takes you to its round. **← blober** goes back to the filter.

New to blober? blobslinger still works: it makes up random blobs until you've voted on some.

## The `.bna`

One text file holds everything: the filter for blober and your place in the games.

```
bna1
# gone 102
# blobslinger round 12 score 34000
fav s=… f=… e=… m=… t=… a=… l=… c=…
yes blob s=…
no blob s=…
yes color s=…
```

- `fav` and `yes blob`: the ones you liked. In blobslinger these are the ones you throw.
- `no blob`: the ones you got rid of. In blobslinger they come back gray and sad.
- `yes color`: colors you liked. A gray favorite gets one of these.
- `# blobslinger round N score M`: your round and points in blobslinger (files from before the rename say `# blobsling`; both are read). blober keeps this line every time it saves; when two files disagree, the higher round wins.

## The genome

Every blob comes from one line of text, its genome:

```
s=<shape> f=<face> e=<eyes> m=<mouth> t=<antennas> a=<arms> l=<legs> c=<color>
```

The same line always draws the same blob. The genomes are inside every `.bna`.

## blobengine (Python)

The same blobs outside the browser: give it a `.bna` and it makes new ones that fit it, as SVG or as a profile picture. Same genome, same drawing as the page, byte for byte.

```
pip install git+https://github.com/mrtatiso/blober
```

From the command line:

```
blobengine client.bna -o avatar.png          # one new blob
blobengine client.bna -n 6 -o avatars        # six, in a folder
blobengine --genome "s=… c=3" -o same.png    # draw a genome you kept
blobengine                                   # no .bna: random blobs
```

From code:

```python
from blobengine import BlobEngine, Blob

engine = BlobEngine.load("client.bna")
blob = engine.new_blob()            # one that fits the filter (one in five is pure chance)
blob.save("avatar.png")             # 512 × 512, fits a round avatar
print(blob.genome)                  # keep this line: it draws the same blob again
Blob.from_genome(line).save("again.png")
```

Options: `--size`, `--background auto|#rrggbb|none`, `--no-shadow`, `--circle`, `--fit circle|square`, `--seed`, `--color`, `--svg`.

## Run it locally

Two pages, side by side: `index.html` (blober) and `blobslinger.html`. The rest is for installing it on a phone: `manifest.webmanifest`, `sw.js` (offline) and the icons (`icon.svg` for the browser tab; `icon-192.png`, `icon-512.png` rounded, for desktops; `icon-maskable-*.png` full square, for Android; `apple-touch-icon.png` full square, for iPhone, iPad and Mac). Open `index.html` in a browser and that's it: no server, no install, no dependencies. The logos are drawn as SVG, and the Bagel Fat One font for the titles lives in `fonts/` (SIL Open Font License, see `fonts/OFL.txt`), so nothing is fetched from anywhere else and it all works offline. blobslinger also includes [Matter.js](https://brm.io/matter-js/) 0.20 (MIT) for its physics.

Over `file://`, some browsers keep each file's storage separate. If blobslinger doesn't find your blobs, use **load .bna**, or serve the folder (for example `python3 -m http.server`).

## License

blober is **source available**, free to play and to mod, but not to sell.

- **You can:** play it, study the code, change it, make mods, and share them for free (keep the `LICENSE` file and its `Required Notice` line with them).
- **You can also:** stream it, make videos of it, and write about it, monetized or not.
- **You can't:** sell blober, a modified version, or a mod, or put it inside anything you charge for (a paid app, a paid game, a paid service), without permission.
- **The name and the logo** ("blober", "blobslinger" and their logos) are not covered by the license: a mod can't be called blober or look like the official game. Call yours something else and say it's based on blober.

The official version (like the one on Steam) is sold by its author. Code is under the [PolyForm Noncommercial License 1.0.0](LICENSE). Want to use it commercially? Ask.

Versions published before this change were released under MIT. Third-party parts keep their own licenses: see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
