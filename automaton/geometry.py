"""Geometry of the scale automaton: every part as 2D shapely shapes, in
panel coordinates (mm, x right, y up, origin at the panel's bottom-left),
plus the cam-follower functions that drive them.

Layer stack, front face heights above the base plate (z, mm):
  disc F 0-3 | flat comb 3.5-5 (spine to 6.5) | disc S 5.5-8.5 |
  sharp comb 9-10.5 (spine to 12) | disc T 11-14 | carriage 14.5-16.5 |
  front panel 17.5-20.5 | lever 21-24.
"""

import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union

# ------------------------------------------------------------- panel
W, H = 180.0, 200.0
CX, CY = 125.0, 55.0            # cam shaft
R_DISC = 53.0
SHAFT_D = 6.0                   # D-shaft, 1 mm flat
G = 5.0                         # staff space
Y_E4 = 135.0                    # bottom staff line
STAFF_X = (10.0, 170.0)
SIG_WIN = (43.0, 126.0, 76.0, 168.0)    # x0, y0, x1, y1 (rect order)
WIN_Y = (126.0, 168.0)          # note column windows share this height
COL_HALF_W = 3.8                # each notehead has its own window
BAR_W = 1.2                     # physical staff bars across the windows
NOTE_X0, NOTE_DX = 89.0, 10.0
P_TAB = 5.0                     # signature column pitch
TAB_X0 = 73.5                   # tab j parks at TAB_X0 + P_TAB * j
STALK_W = 1.2
RING_R = 40.0                   # circle-of-fifths label radius
LEVER_LEN = 44.0

# cam bands
R_T0 = 35.0                     # tonic groove: r = R_T0 + (t + 1) * G
R_S0 = 20.0                     # spirals: r = R_S0 + P_TAB * |k|
GROOVE_W = 3.4                  # for a 3 mm pin
PIN_D = 3.0

# z stack (front faces)
Z = dict(discF=(0, 3), combF=(3.5, 5), combF_spine=(3.5, 6.5),
         discS=(5.5, 8.5), combS=(9, 10.5), combS_spine=(9, 12),
         discT=(11, 14), carriage=(14.5, 16.5), panel=(17.5, 20.5),
         lever=(21, 24))
GROOVE_DEPTH = 2.0
EMBOSS = 0.6

# ---------------------------------------------------------------- keys
# k: steps around the circle of fifths from C (sharps positive)
KEY_NAMES = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#",
             -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db"}
TONIC_POS = {"C": -1, "D": -0.5, "E": 0, "F": 0.5, "G": 1, "A": 1.5, "B": 2}
K_MIN, K_MAX = -5, 6
STEP_DEG = 30.0

SHARP_POS = [4, 2.5, 4.5, 3, 1.5, 3.5, 2]        # F C G D A E B
FLAT_POS = [2, 3.5, 1.5, 3, 1, 2.5, 0.5]         # B E A D G C F


def tonic(k):
    return TONIC_POS[KEY_NAMES[k][0]]


def ypos(p):
    return Y_E4 + p * G


def pointer_angle(k):
    """Lever angle, clockwise from 12 o'clock, degrees."""
    return STEP_DEG * k


# ----------------------------------------------------------- followers
def r_tonic(k):
    ks = np.arange(K_MIN, K_MAX + 1)
    return float(np.interp(k, ks, [R_T0 + (tonic(i) + 1) * G for i in ks]))


def r_sharp(k):
    return R_S0 + P_TAB * max(k, 0.0)


def r_flat(k):
    return R_S0 + P_TAB * max(-k, 0.0)


def carriage_lift(k):
    return r_tonic(k) - R_T0


def comb_shift(k, sharp=True):
    return (r_sharp(k) if sharp else r_flat(k)) - R_S0


def groove_polyline(r_fn, beta_deg, n_per_step=24):
    """Groove centreline in the disc's own frame (disc at k = 0).

    A follower fixed at world angle beta reads the groove at disc angle
    beta + phi, where phi = 30 deg * k is the clockwise lever angle.
    """
    ks = np.linspace(K_MIN, K_MAX, (K_MAX - K_MIN) * n_per_step + 1)
    pts = []
    for k in ks:
        psi = math.radians(beta_deg + pointer_angle(k))
        r = r_fn(k)
        pts.append((r * math.cos(psi), r * math.sin(psi)))
    return LineString(pts)


TONIC_GROOVE = groove_polyline(r_tonic, 90)
SHARP_GROOVE = groove_polyline(r_sharp, 180)
FLAT_GROOVE = groove_polyline(r_flat, 180)


# --------------------------------------------------------- primitives
def rect(x0, y0, x1, y1):
    return box(x0, y0, x1, y1)


def ellipse(cx, cy, a, b, tilt_deg=0, n=64):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    e = Polygon(np.c_[a * np.cos(t), b * np.sin(t)])
    return translate(rotate(e, tilt_deg, origin=(0, 0)), cx, cy)


def d_bore(cx, cy, d=SHAFT_D + 0.3, flat=1.0):
    return Point(cx, cy).buffer(d / 2, 48).intersection(
        rect(cx - d, cy - d, cx + d, cy + d / 2 - flat))


def notehead(cx, cy):
    return ellipse(cx, cy, 0.64 * G, 0.445 * G, 20)


def sharp_glyph(cx, cy):
    parts = [rect(-1.35, -4.5, -0.65, 4.5), rect(0.65, -4.5, 1.35, 4.5)]
    for yc in (-1.6, 1.6):
        parts.append(rotate(rect(-2.3, yc - 0.55, 2.3, yc + 0.55), 18,
                            origin=(0, yc)))
    return translate(unary_union(parts), cx, cy)


def flat_glyph(cx, cy):
    bowl = ellipse(0.1, 0, 1.9, 1.5).difference(ellipse(-0.2, 0, 1.0, 0.8))
    stem = rect(-1.9, -1.5, -1.2, 7.5)
    return translate(unary_union([bowl, stem]), cx, cy)


def letter_c(cx, cy, r_out, stroke, opening=70, n=96):
    half = math.radians(opening / 2)
    t = np.linspace(half, 2 * math.pi - half, n)
    r_in = r_out - stroke
    pts = np.r_[np.c_[r_out * np.cos(t), r_out * np.sin(t)],
                np.c_[r_in * np.cos(t[::-1]), r_in * np.sin(t[::-1])]]
    return translate(Polygon(pts), cx, cy)


# ---------------------------------------------------------- the parts
def disc_outline():
    return Point(CX, CY).buffer(R_DISC, 128).difference(d_bore(CX, CY))


def disc_groove(groove, phi_deg=0):
    """Groove slot in panel coordinates at lever angle phi (clockwise)."""
    g = rotate(groove, -phi_deg, origin=(0, 0))
    return translate(g.buffer(GROOVE_W / 2, 16), CX, CY)


def disc_notch(phi_deg=0):
    n = rect(-1.2, R_DISC - 2, 1.2, R_DISC + 1)
    return translate(rotate(n, -phi_deg, origin=(0, 0)), CX, CY)


def carriage_shape(k=0):
    """Carriage plate (with noteheads separately) at key k."""
    dy = carriage_lift(k)
    plate = unary_union([rect(82, 103, 172, 172), rect(121, 86, 129, 104)])
    heads = [notehead(NOTE_X0 + NOTE_DX * i, ypos(-1 + i / 2))
             for i in range(8)]
    pin = Point(CX, CY + R_T0)
    return (translate(plate, 0, dy), [translate(h, 0, dy) for h in heads],
            translate(pin, 0, dy))


def comb_shape(k=0, sharp=True):
    """Comb spine+arm, stalks, glyphs and pin at key k (all shifted)."""
    dx = -comb_shift(k, sharp)
    x_arm = CX - R_S0
    if sharp:
        spine = rect(43, 176, 111, 180)
        arm = rect(x_arm - 1.5, CY, x_arm + 1.5, 176)
        stalks, glyphs = [], []
        for j, p in enumerate(SHARP_POS, 1):
            x = TAB_X0 + P_TAB * j
            y = ypos(p)
            stalks.append(rect(x - STALK_W / 2, y + 4, x + STALK_W / 2, 176))
            glyphs.append(sharp_glyph(x, y))
    else:
        spine = rect(43, 110, 111, 114)
        arm = rect(x_arm - 1.5, CY, x_arm + 1.5, 110)
        stalks, glyphs = [], []
        for j, p in enumerate(FLAT_POS, 1):
            x = TAB_X0 + P_TAB * j
            y = ypos(p)
            stalks.append(rect(x - STALK_W / 2, 114, x + STALK_W / 2, y - 1))
            glyphs.append(flat_glyph(x, y))
    body = unary_union([spine, arm] + stalks)
    pin = Point(x_arm, CY)
    sh = lambda g: translate(g, dx, 0)
    return sh(spine), sh(body), [sh(g) for g in glyphs], sh(pin)


def visible_glyph_count(k, sharp=True):
    return max(k, 0) if sharp else max(-k, 0)


def panel_windows():
    """Window openings before the staff bars are left across them."""
    wins = [rect(*SIG_WIN)]
    for i in range(8):
        x = NOTE_X0 + NOTE_DX * i
        wins.append(rect(x - COL_HALF_W, WIN_Y[0], x + COL_HALF_W, WIN_Y[1]))
    return wins


def staff_bars():
    """Material left across the windows: staff lines and ledger stubs."""
    bars = []
    for i in range(5):
        y = Y_E4 + i * G
        bars.append(rect(0, y - BAR_W / 2, W, y + BAR_W / 2))
    # ledger stubs: degree 1 at position -1 (C major), degrees 7-8 at +5
    for col, p in ((0, -1), (6, 5), (7, 5)):
        x = NOTE_X0 + NOTE_DX * col
        bars.append(rect(x - COL_HALF_W, ypos(p) - BAR_W / 2,
                         x + COL_HALF_W, ypos(p) + BAR_W / 2))
    return unary_union(bars).intersection(unary_union(panel_windows()))


def panel_cuts():
    """Everything removed from the front panel sheet."""
    cuts = unary_union(panel_windows()).difference(staff_bars())
    holes = [Point(CX, CY).buffer(SHAFT_D / 2 + 0.4, 48)]
    holes += [Point(x, y).buffer(1.6, 24) for x, y in standoff_positions()]
    return unary_union([cuts] + holes)


def panel_outline():
    # unary_union dissolves the shared edges where a ledger stub meets
    # its mullions, which difference() leaves as touching pieces
    return unary_union(rect(0, 0, W, H).difference(panel_cuts()))


def standoff_positions():
    return [(6, 6), (W - 6, 6), (6, H - 6), (W - 6, H - 6), (6, 100),
            (W - 6, 130)]


def engraved_staff():
    lines = []
    for i in range(5):
        y = Y_E4 + i * G
        lines.append(rect(STAFF_X[0], y - 0.25, STAFF_X[1], y + 0.25))
    return unary_union(lines).difference(unary_union(panel_windows()))


def ring_ticks():
    ticks = []
    for k in range(K_MIN, K_MAX + 1):
        a = math.radians(90 - pointer_angle(k))
        t = rect(RING_R - 3, -0.4, RING_R + 1, 0.4)
        ticks.append(translate(rotate(t, math.degrees(a), origin=(0, 0)),
                               CX, CY))
    return unary_union(ticks)


def lever_shape(k=0):
    arm = Polygon([(-2.5, -6), (2.5, -6), (1.2, LEVER_LEN - 4),
                   (0, LEVER_LEN), (-1.2, LEVER_LEN - 4)])
    knob = Point(0, 30).buffer(4.5, 32)
    hub = Point(0, 0).buffer(7, 48)
    s = unary_union([arm, knob, hub])
    s = rotate(s, -pointer_angle(k), origin=(0, 0))
    return translate(s, CX, CY)


def label_positions():
    """(key name, x, y) around the dial."""
    out = []
    for k in range(K_MIN, K_MAX + 1):
        a = math.radians(90 - pointer_angle(k))
        out.append((KEY_NAMES[k], CX + RING_R * math.cos(a),
                    CY + RING_R * math.sin(a)))
    return out
