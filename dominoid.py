#!/usr/bin/env python3
"""Dominoid: parametric 'musical domino' tiles for resin printing.

Each tile is a solid portrait tile (20 mm wide, 70 mm high, 5 mm thick)
whose face carries a five-line staff engraved edge to edge across the
width, so tiles standing side by side chain into one continuous staff.
One note name is shown as crotchets in three octave positions, ledger
lines and accidental included, reading low to high left to right, with
the note name as a heading at the top.

A full set is 21 tiles: seven letters, each as a natural, a sharp and a
flat. That covers every key signature from seven flats to seven sharps,
so any major, natural minor or harmonic minor scale can be laid out.

Engraved features (staff, heading) are recessed so they can be
paint-filled black after printing; note glyphs (accidentals, heads,
stems, ledger lines) are embossed so they can be felt and dry-brushed.

Usage:
    python3 dominoid.py                # the whole 21-tile set
    python3 dominoid.py C F# Bb        # named tiles only

Output: output/dominoid_<name>.stl (mm units) and a 2D design proof
output/dominoid_<name>_face.png.
"""

import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.affinity import rotate as shapely_rotate
from shapely.affinity import scale as shapely_scale
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

# ---------------------------------------------------------------- tile
TILE_W = 20.0        # mm, face width (X): tiles chain along this edge
TILE_H = 70.0        # mm, face height (Y)
TILE_T = 5.0         # mm, thickness (Z)
CHAMFER = 0.6        # mm, chamfer on all edges

# ------------------------------------------------------------ notation
GAP = 2.6            # staff space (line-centre to line-centre)
STAFF_Y = 35.0       # y of the middle staff line
STAFF_LINE_W = 0.35  # engraved staff line width
ENGRAVE_D = 0.4      # engraving depth
EMBOSS_H = 0.5       # emboss height above the face

HEAD_A = 0.64 * GAP           # notehead ellipse semi-axes
HEAD_B = 0.445 * GAP
HEAD_TILT = math.radians(20)  # anticlockwise tilt of the notehead
STEM_W = 0.5                  # stem width
STEM_LEN = 3.5 * GAP          # standard stem length: 3.5 spaces
STEM_MIN = 2.5 * GAP          # shortest a stem may be trimmed to
LEDGER_LEN = 2.0 * GAP        # ledger line length, centred on the head
LEDGER_W = 0.5                # ledger line width (thicker than staff)

NOTE_X = 11.0                 # x of the middle octave column
NOTE_SPREAD = 4.0             # x offset between octave columns
ACC_DX = -4.2                 # accidental centre, relative to its head
ACC_STROKE = 0.45             # accidental stroke width

HEADING_H = 9.0               # heading letter cap height
HEADING_W = 7.0               # heading letter width
HEADING_STROKE = 1.3          # heading letter stroke width
HEADING_Y = 61.0              # heading centre height
HEADING_ACC_SCALE = 1.25      # accidental size in the heading
HEADING_ACC_GAP = 0.8         # gap between heading letter and accidental

# Diatonic index for staff-position arithmetic (E4 = bottom line = 0).
_LETTERS = "CDEFGAB"

# Octaves per letter, chosen around the written clarinet range (C gets
# middle C, third-space C and high C, as requested).
DEFAULT_OCTAVES = {
    "C": (4, 5, 6), "D": (4, 5, 6), "E": (4, 5, 6), "F": (4, 5, 6),
    "G": (3, 4, 5), "A": (3, 4, 5), "B": (3, 4, 5),
}

# An accidental never changes where the note sits on the staff, only
# what it is called: C sharp shares middle C's line.
ACCIDENTALS = ("", "#", "b")
ACC_SUFFIX = {"": "", "#": "_sharp", "b": "_flat",
              "##": "_double_sharp", "bb": "_double_flat"}
ACC_SYMBOL = {"": "", "#": "♯", "b": "♭",
              "##": "×", "bb": "♭♭"}


def staff_position(letter, octave):
    """Note position in staff spaces above the bottom line (E4)."""
    steps = (octave - 4) * 7 + (_LETTERS.index(letter) - _LETTERS.index("E"))
    return steps / 2.0


def bottom_line_y():
    return STAFF_Y - 2 * GAP


def note_y(position):
    return bottom_line_y() + position * GAP


def ledger_positions(position):
    """Integer staff positions needing ledger lines for a note."""
    if position <= -1:
        return [p for p in range(-1, math.floor(position) - 1, -1)
                if p >= position]
    if position >= 5:
        return [p for p in range(5, math.floor(position) + 1)]
    return []


# ------------------------------------------------------- 2D primitives
def ellipse_poly(cx, cy, a, b, tilt, n=96):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    x, y = a * np.cos(t), b * np.sin(t)
    ct, st = math.cos(tilt), math.sin(tilt)
    return Polygon(np.c_[cx + x * ct - y * st, cy + x * st + y * ct])


def rect_poly(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _bar(x0, x1, y, s):
    return rect_poly(x0, y - s / 2, x1, y + s / 2)


def _stem(x, y0, y1, s):
    return rect_poly(x - s / 2, y0, x + s / 2, y1)


def _ring(cx, cy, rx, ry, s, t0=0.0, t1=360.0, n=96):
    """Elliptical annulus sector, stroke s taken inwards."""
    t = np.radians(np.linspace(t0, t1, n))
    outer = np.c_[cx + rx * np.cos(t), cy + ry * np.sin(t)]
    inner = np.c_[cx + (rx - s) * np.cos(t[::-1]),
                  cy + (ry - s) * np.sin(t[::-1])]
    return Polygon(np.r_[outer, inner])


def letter_poly(letter, cx=0.0, cy=0.0, h=HEADING_H, w=HEADING_W,
                s=HEADING_STROKE):
    """A geometric capital A-G: cap height h, width w, stroke s.

    Drawn from bars, stems and elliptical annulus sectors so the whole
    alphabet shares one weight and one width, and engraves cleanly.
    """
    top, bot = h / 2, -h / 2
    left, right = -w / 2, w / 2
    x_stem = left + s / 2
    parts = []
    if letter == "A":
        for x_foot in (left, right):
            parts.append(LineString([(x_foot, bot), (0, top)])
                         .buffer(s / 2, cap_style=2, join_style=2))
        parts.append(_bar(left * 0.72, right * 0.72, bot + h * 0.3, s))
    elif letter == "B":
        parts.append(_stem(x_stem, bot, top, s))
        for y_bowl in (h / 4, -h / 4):
            parts.append(_ring(x_stem, y_bowl, w - s / 2, h / 4, s, -90, 90))
    elif letter == "C":
        parts.append(_ring(0, 0, right, top, s, 40, 320))
    elif letter == "D":
        parts.append(_stem(x_stem, bot, top, s))
        parts.append(_ring(x_stem, 0, w - s / 2, top, s, -90, 90))
    elif letter in ("E", "F"):
        parts.append(_stem(x_stem, bot, top, s))
        parts.append(_bar(left, right, top - s / 2, s))
        parts.append(_bar(left, right * 0.8, 0, s))
        if letter == "E":
            parts.append(_bar(left, right, bot + s / 2, s))
    elif letter == "G":
        parts.append(_ring(0, 0, right, top, s, 30, 330))
        cos30 = math.cos(math.radians(30))
        parts.append(_bar(0, right * cos30 + s / 2, -h * 0.1, s))
        # spur: spans the arc's whole end face, so no notch is left at
        # the join, and dips just past it so the two overlap rather than
        # meeting at a single degenerate point
        parts.append(rect_poly((right - s) * cos30, -top / 2 - s / 4,
                               right * cos30 + s / 2, -h * 0.1 + s / 2))
    else:
        raise ValueError(f"no heading glyph for {letter!r}")
    glyph = unary_union(parts).buffer(0)
    if glyph.geom_type != "Polygon":
        raise ValueError(f"{letter!r} glyph is not one clean outline")
    return translate(glyph, cx, cy)


def sharp_poly(cx=0.0, cy=0.0, s=ACC_STROKE):
    """A sharp sign, sized in staff spaces and centred on the notehead."""
    parts = [_stem(x, -1.1 * GAP, 1.1 * GAP, s) for x in (-0.55, 0.55)]
    for y in (-0.38 * GAP, 0.38 * GAP):
        parts.append(shapely_rotate(_bar(-1.2, 1.2, y, s * 1.25), 12,
                                    origin=(0, y)))
    return translate(unary_union(parts).buffer(0), cx, cy)


def flat_poly(cx=0.0, cy=0.0, s=ACC_STROKE):
    """A flat sign: the bowl sits on the note, the stem rises above it."""
    stem = rect_poly(-0.95, -0.50 * GAP, -0.95 + s, 1.50 * GAP)
    bowl = ellipse_poly(0.05, -0.15, 1.10, 1.15, 0.0).difference(
        ellipse_poly(-0.18, -0.20, 1.10 - s, 1.15 - s, 0.0))
    bowl = bowl.intersection(rect_poly(-0.95, -3, 3, 3))
    return translate(unary_union([stem, bowl]).buffer(0), cx, cy)


def double_sharp_poly(cx=0.0, cy=0.0, s=ACC_STROKE):
    """A double sharp: the engraver's X, drawn as two crossed bars."""
    arm = 0.46 * GAP
    parts = [shapely_rotate(rect_poly(-arm, -s * 0.7, arm, s * 0.7), a,
                            origin=(0, 0)) for a in (45, -45)]
    return translate(unary_union(parts).buffer(0), cx, cy)


def double_flat_poly(cx=0.0, cy=0.0, s=ACC_STROKE):
    """A double flat: two flat signs side by side."""
    return translate(unary_union([flat_poly(-1.25, 0, s),
                                  flat_poly(1.25, 0, s)]), cx, cy)


ACC_POLY = {"#": sharp_poly, "b": flat_poly,
            "##": double_sharp_poly, "bb": double_flat_poly}


def accidental_poly(accidental, cx, cy, s=ACC_STROKE):
    return ACC_POLY[accidental](cx, cy, s)


def heading_poly(letter, accidental, cx, cy):
    """The tile's name: capital letter, plus its accidental if any."""
    glyph = letter_poly(letter)
    if not accidental:
        return translate(glyph, cx, cy)
    acc = accidental_poly(accidental, 0, 0, ACC_STROKE * HEADING_ACC_SCALE)
    acc = shapely_scale(acc, HEADING_ACC_SCALE, HEADING_ACC_SCALE,
                        origin=(0, 0))
    lx0, _, lx1, _ = glyph.bounds
    ax0, ay0, ax1, ay1 = acc.bounds
    total = (lx1 - lx0) + HEADING_ACC_GAP + (ax1 - ax0)
    glyph = translate(glyph, -total / 2 - lx0, 0)
    acc = translate(acc, -total / 2 + (lx1 - lx0) + HEADING_ACC_GAP - ax0,
                    -(ay0 + ay1) / 2)
    return translate(unary_union([glyph, acc]), cx, cy)


# ------------------------------------------------------- 3D primitives
def prism(poly, z0, z1):
    """Extrude a Polygon or MultiPolygon between two heights."""
    parts = []
    for g in getattr(poly, "geoms", [poly]):
        m = trimesh.creation.extrude_polygon(g, z1 - z0)
        m.apply_translation([0, 0, z0])
        parts.append(m)
    return trimesh.util.concatenate(parts)


def chamfered_tile():
    c = CHAMFER
    parts = []
    for dx, dy, dz in ((c, c, 0), (c, 0, c), (0, c, c)):
        b = trimesh.creation.box((TILE_W - 2 * dx, TILE_H - 2 * dy,
                                  TILE_T - 2 * dz))
        b.apply_translation([TILE_W / 2, TILE_H / 2, TILE_T / 2])
        parts.append(b)
    return trimesh.util.concatenate(parts).convex_hull


# ----------------------------------------------------------- the glyphs
def note_body(cx, position, accidental):
    """Everything that stays put: notehead, ledger lines, accidental.

    The accidental slot is reserved on every tile, naturals included, so
    all 21 tiles carry their noteheads at the same x and a laid-out
    scale keeps an even spacing.
    """
    cy = note_y(position)
    polys = [ellipse_poly(cx, cy, HEAD_A, HEAD_B, HEAD_TILT)]
    for p in ledger_positions(position):
        ly = note_y(p)
        polys.append(rect_poly(cx - LEDGER_LEN / 2, ly - LEDGER_W / 2,
                               cx + LEDGER_LEN / 2, ly + LEDGER_W / 2))
    if accidental:
        acc = accidental_poly(accidental, cx + ACC_DX, cy)
        polys.extend(getattr(acc, "geoms", [acc]))
    return polys


def stem_poly(cx, position, length):
    cy = note_y(position)
    half_w = math.hypot(HEAD_A * math.cos(HEAD_TILT),
                        HEAD_B * math.sin(HEAD_TILT))
    if position < 2:  # below the middle line -> stem up on the right
        return rect_poly(cx + half_w - STEM_W, cy, cx + half_w, cy + length)
    return rect_poly(cx - half_w, cy - length, cx - half_w + STEM_W, cy)


def note_column_polys(xs, positions, accidental=""):
    """All glyph polygons, with stems trimmed clear of neighbours."""
    bodies = [note_body(cx, pos, accidental)
              for cx, pos in zip(xs, positions)]
    polys = []
    for i, (cx, pos) in enumerate(zip(xs, positions)):
        others = unary_union(
            [p for j, body in enumerate(bodies) if j != i for p in body])
        length = STEM_LEN
        stem = stem_poly(cx, pos, length)
        while stem.buffer(0.3).intersects(others) and length > STEM_MIN:
            length -= 0.1
            stem = stem_poly(cx, pos, length)
        polys.extend(bodies[i])
        polys.append(stem)
    return polys


def column_xs(n):
    return [NOTE_X + (i - (n - 1) / 2) * NOTE_SPREAD for i in range(n)]


def build_tile(letter, accidental="", octaves=None):
    letter = letter.upper()
    octaves = octaves or DEFAULT_OCTAVES[letter]
    positions = sorted(staff_position(letter, o) for o in octaves)
    xs = column_xs(len(positions))

    raised = unary_union(note_column_polys(xs, positions, accidental))
    head = heading_poly(letter, accidental, TILE_W / 2, HEADING_Y)

    # Nothing may run off the face or collide with the heading.
    name = letter + accidental
    margin = CHAMFER + 0.1
    x0, y0, x1, y1 = unary_union([raised, head]).bounds
    if x0 < margin or y0 < margin or x1 > TILE_W - margin \
            or y1 > TILE_H - margin:
        raise ValueError(
            f"{name}: artwork runs off the face "
            f"(x {x0:.1f}..{x1:.1f}, y {y0:.1f}..{y1:.1f})")
    if raised.intersects(head.buffer(0.5)):
        raise ValueError(f"{name}: notes collide with the heading")

    tile = chamfered_tile()
    z_face = TILE_T

    # Engravings: 5 staff lines edge to edge (through the chamfers) and
    # the heading. Cut before embossing so raised glyphs bridge the
    # grooves intact.
    cuts = [rect_poly(-2, STAFF_Y + k * GAP - STAFF_LINE_W / 2,
                      TILE_W + 2, STAFF_Y + k * GAP + STAFF_LINE_W / 2)
            for k in range(-2, 3)]
    cuts.append(head)
    tile = tile.difference(prism(unary_union(cuts), z_face - ENGRAVE_D,
                                 z_face + 1), engine="manifold")

    # Embossed crotchets, ascending left to right across the width. The
    # glyphs are merged in 2D before extruding: unioning overlapping
    # prisms instead leaves ramp slivers where their walls intersect.
    tile = tile.union(prism(raised, z_face - 1, z_face + EMBOSS_H),
                      engine="manifold")

    if not tile.is_volume:
        raise ValueError(f"{name}: resulting mesh is not a printable solid")
    return tile, xs, positions


# -------------------------------------------------------- design proof
def draw_tile(ax, letter, accidental, xs, positions, label=True):
    from matplotlib.patches import Rectangle

    ax.add_patch(Rectangle((0, 0), TILE_W, TILE_H, fill=False, lw=1.2,
                           ec="#888"))
    for k in range(-2, 3):
        y = STAFF_Y + k * GAP
        ax.plot([0, TILE_W], [y, y], color="black", lw=1.2,
                solid_capstyle="butt")
    head = heading_poly(letter, accidental, TILE_W / 2, HEADING_Y)
    for g in getattr(head, "geoms", [head]):
        ax.fill(*g.exterior.xy, color="black", lw=0)
        for ring in g.interiors:
            ax.fill(*ring.xy, color="white", lw=0)
    for poly in note_column_polys(xs, positions, accidental):
        ax.fill(*poly.exterior.xy, color="#1a4a8a", lw=0)
        for ring in poly.interiors:
            ax.fill(*ring.xy, color="white", lw=0)
    ax.set_xlim(-1, TILE_W + 1)
    ax.set_ylim(-1, TILE_H + 1)
    ax.set_aspect("equal")
    ax.axis("off")
    if label:
        ax.set_title(letter + ACC_SYMBOL[accidental], fontsize=12)


def draw_proof(letter, accidental, xs, positions, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.4, 10))
    draw_tile(ax, letter, accidental, xs, positions, label=False)
    ax.set_title(f"Dominoid '{letter}{ACC_SYMBOL[accidental]}' — "
                 f"{TILE_W:g} x {TILE_H:g} x {TILE_T:g} mm\n"
                 f"black = engraved {ENGRAVE_D} mm (paint-fill), "
                 f"blue = embossed {EMBOSS_H} mm", fontsize=9)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def draw_set(tiles, path):
    """One contact sheet of every tile built this run."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(tiles)
    fig, axes = plt.subplots(1, n, figsize=(1.55 * n, 8.4))
    for ax, (letter, accidental, xs, positions) in zip(
            np.atleast_1d(axes), tiles):
        draw_tile(ax, letter, accidental, xs, positions)
    fig.suptitle("Dominoid — the full set of note tiles "
                 f"({TILE_W:g} x {TILE_H:g} x {TILE_T:g} mm each)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- CLI
def parse_name(token):
    """'C', 'F#', 'Bb', 'Fs', 'E-flat' -> (letter, accidental)."""
    t = token.strip().replace("-", "").replace("_", "")
    letter = t[:1].upper()
    if letter not in _LETTERS:
        raise ValueError(f"{token!r}: not a note letter A-G")
    rest = t[1:].lower().replace("♯", "#").replace("♭", "b")
    if rest in ("", "nat", "natural"):
        return letter, ""
    if rest in ("#", "s", "sharp"):
        return letter, "#"
    if rest in ("b", "f", "flat"):
        return letter, "b"
    if rest in ("##", "x", "ss", "doublesharp"):
        return letter, "##"
    if rest in ("bb", "ff", "doubleflat"):
        return letter, "bb"
    raise ValueError(f"{token!r}: accidental must be sharp, flat, "
                     f"double sharp, double flat or none")


def full_set():
    return [(letter, acc) for acc in ACCIDENTALS for letter in _LETTERS]


def main(argv):
    names = [parse_name(a) for a in argv] if argv else full_set()
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    built = []
    for letter, accidental in names:
        octaves = DEFAULT_OCTAVES[letter]
        tile, xs, positions = build_tile(letter, accidental, octaves)
        stem = f"dominoid_{letter}{ACC_SUFFIX[accidental]}"
        tile.export(out / f"{stem}.stl")
        tile.export(out / f"{stem}.obj")
        draw_proof(letter, accidental, xs, positions,
                   out / f"{stem}_face.png")
        built.append((letter, accidental, xs, positions))
        spelt = ", ".join(f"{letter}{ACC_SYMBOL[accidental]}{o}"
                          for o in octaves)
        print(f"{stem}.stl/.obj  ({spelt}; {len(tile.faces)} triangles; "
              f"{tile.volume / 1000:.1f} cm^3)")
    if len(built) > 1:
        draw_set(built, out / "dominoid_set.png")
        print(f"\n{len(built)} tiles -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
