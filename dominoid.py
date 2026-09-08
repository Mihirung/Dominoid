#!/usr/bin/env python3
"""Dominoid: parametric 'musical domino' tiles for resin printing.

Each tile is a solid portrait tile (20 mm wide, 70 mm high, 5 mm thick)
whose face carries a five-line staff engraved edge to edge across the
width, so tiles standing side by side chain into one continuous staff.
One note letter is shown as crotchets in three octave positions, ledger
lines included, reading low to high left to right, with the letter as a
heading at the top.

Engraved features (staff, heading) are recessed so they can be
paint-filled black after printing; note glyphs (heads, stems, ledger
lines) are embossed so they can be felt and dry-brushed black.

Usage:
    python3 dominoid.py            # generates the C prototype
    python3 dominoid.py D E F      # generates other natural-note tiles

Output: output/dominoid_<letter>.stl (mm units) and a 2D design proof
output/dominoid_<letter>_face.png.
"""

import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon
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
NOTE_SPREAD = 5.0             # x offset between octave columns

HEADING_R_OUT = 4.5           # heading letter outer radius
HEADING_STROKE = 1.5          # heading letter stroke width
HEADING_Y = 58.0              # heading letter centre height

# Diatonic index for staff-position arithmetic (E4 = bottom line = 0).
_LETTERS = "CDEFGAB"

# Octaves per letter, chosen around the written clarinet range (C gets
# middle C, third-space C and high C, as requested).
DEFAULT_OCTAVES = {
    "C": (4, 5, 6), "D": (4, 5, 6), "E": (4, 5, 6), "F": (4, 5, 6),
    "G": (3, 4, 5), "A": (3, 4, 5), "B": (3, 4, 5),
}


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


def letter_c_poly(cx, cy, r_out, stroke, opening_deg=70, n=128):
    """A geometric capital C: an annular arc open on the right."""
    half = math.radians(opening_deg / 2.0)
    t_out = np.linspace(half, 2 * math.pi - half, n)
    t_in = t_out[::-1]
    r_in = r_out - stroke
    pts = np.r_[np.c_[cx + r_out * np.cos(t_out), cy + r_out * np.sin(t_out)],
                np.c_[cx + r_in * np.cos(t_in), cy + r_in * np.sin(t_in)]]
    return Polygon(pts)


def rect_poly(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


# ------------------------------------------------------- 3D primitives
def prism(poly, z0, z1):
    m = trimesh.creation.extrude_polygon(poly, z1 - z0)
    m.apply_translation([0, 0, z0])
    return m


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
def head_and_ledgers(cx, position):
    cy = note_y(position)
    polys = [ellipse_poly(cx, cy, HEAD_A, HEAD_B, HEAD_TILT)]
    for p in ledger_positions(position):
        ly = note_y(p)
        polys.append(rect_poly(cx - LEDGER_LEN / 2, ly - LEDGER_W / 2,
                               cx + LEDGER_LEN / 2, ly + LEDGER_W / 2))
    return polys


def stem_poly(cx, position, length):
    cy = note_y(position)
    half_w = math.hypot(HEAD_A * math.cos(HEAD_TILT),
                        HEAD_B * math.sin(HEAD_TILT))
    if position < 2:  # below the middle line -> stem up on the right
        return rect_poly(cx + half_w - STEM_W, cy, cx + half_w, cy + length)
    return rect_poly(cx - half_w, cy - length, cx - half_w + STEM_W, cy)


def note_column_polys(xs, positions):
    """All glyph polygons, with stems trimmed clear of neighbours."""
    bodies = [head_and_ledgers(cx, pos) for cx, pos in zip(xs, positions)]
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


def build_tile(letter, octaves):
    letter = letter.upper()
    positions = sorted(staff_position(letter, o) for o in octaves)
    xs = [TILE_W / 2 + (i - (len(positions) - 1) / 2) * NOTE_SPREAD
          for i in range(len(positions))]
    for pos in positions:
        if (note_y(pos) + HEAD_B + STEM_LEN > TILE_H - CHAMFER
                or note_y(pos) - HEAD_B - STEM_LEN < CHAMFER):
            raise ValueError(
                f"{letter}{octaves}: note at staff position {pos} "
                f"does not fit the {TILE_H} mm face")

    tile = chamfered_tile()
    z_face = TILE_T

    # Engravings: 5 staff lines edge to edge (through the chamfers) and
    # the heading letter. Cut before embossing so raised glyphs bridge
    # the grooves intact.
    cuts = []
    for k in range(-2, 3):
        y = STAFF_Y + k * GAP
        cuts.append(prism(rect_poly(-2, y - STAFF_LINE_W / 2,
                                    TILE_W + 2, y + STAFF_LINE_W / 2),
                          z_face - ENGRAVE_D, z_face + 1))
    cuts.append(prism(letter_c_poly(TILE_W / 2, HEADING_Y,
                                    HEADING_R_OUT, HEADING_STROKE),
                      z_face - ENGRAVE_D, z_face + 1))
    tile = tile.difference(trimesh.util.concatenate(cuts), engine="manifold")

    # Embossed crotchets, ascending left to right across the width.
    raised = [prism(poly, z_face - 1, z_face + EMBOSS_H)
              for poly in note_column_polys(xs, positions)]
    tile = tile.union(trimesh.util.concatenate(raised), engine="manifold")

    assert tile.is_watertight, "resulting mesh is not watertight"
    return tile, xs, positions


# -------------------------------------------------------- design proof
def draw_proof(letter, xs, positions, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Arc

    fig, ax = plt.subplots(figsize=(4.6, 11))
    ax.add_patch(Rectangle((0, 0), TILE_W, TILE_H, fill=False, lw=1.5,
                           ec="#888"))
    for k in range(-2, 3):
        y = STAFF_Y + k * GAP
        ax.plot([0, TILE_W], [y, y], color="black", lw=1.6,
                solid_capstyle="butt")
    d = 2 * HEADING_R_OUT - HEADING_STROKE
    ax.add_patch(Arc((TILE_W / 2, HEADING_Y), d, d, theta1=35, theta2=325,
                     color="black", lw=7))
    for poly in note_column_polys(xs, positions):
        x, y = poly.exterior.xy
        ax.fill(x, y, color="#1a4a8a", lw=0)
    ax.set_xlim(-6, TILE_W + 6)
    ax.set_ylim(-6, TILE_H + 4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Dominoid '{letter}' — {TILE_W:g} × {TILE_H:g} × "
                 f"{TILE_T:g} mm\nblack = engraved {ENGRAVE_D} mm (paint-"
                 f"fill), blue = embossed {EMBOSS_H} mm", fontsize=10)
    ax.annotate("", xy=(TILE_W, -3), xytext=(0, -3),
                arrowprops=dict(arrowstyle="<->", color="#888"))
    ax.text(TILE_W / 2, -5.4, f"{TILE_W:g} mm", ha="center", color="#555")
    ax.annotate("", xy=(-3, TILE_H), xytext=(-3, 0),
                arrowprops=dict(arrowstyle="<->", color="#888"))
    ax.text(-4.4, TILE_H / 2, f"{TILE_H:g} mm", va="center", ha="right",
            rotation=90, color="#555")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main(argv):
    letters = [a.upper() for a in argv] or ["C"]
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    for letter in letters:
        octaves = DEFAULT_OCTAVES[letter]
        tile, xs, positions = build_tile(letter, octaves)
        stl = out / f"dominoid_{letter}.stl"
        tile.export(stl)
        draw_proof(letter, xs, positions, out / f"dominoid_{letter}_face.png")
        names = ", ".join(f"{letter}{o}" for o in octaves)
        print(f"{stl}  ({names}; {len(tile.faces)} triangles; "
              f"volume {tile.volume / 1000:.1f} cm^3)")


if __name__ == "__main__":
    main(sys.argv[1:])
