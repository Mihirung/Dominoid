"""Build the automaton's printable parts (STL, mm) and the two sheet
parts as SVG for laser or hand cutting.

    python3 build.py            # writes automaton/output/parts/*
"""

from pathlib import Path

import trimesh
from shapely.geometry import Point
from shapely.affinity import translate
from shapely.ops import unary_union

import geometry as gm

OUT = Path(__file__).parent / "output" / "parts"


# ------------------------------------------------------------ helpers
def prism(poly, z0, z1):
    parts = []
    for g in getattr(poly, "geoms", [poly]):
        if g.is_empty or not hasattr(g, "exterior"):
            continue
        m = trimesh.creation.extrude_polygon(g, z1 - z0)
        m.apply_translation([0, 0, z0])
        parts.append(m)
    return trimesh.util.concatenate(parts)


def csg(base, add=(), cut=()):
    m = base
    if add:
        m = m.union(trimesh.util.concatenate(list(add)), engine="manifold")
    if cut:
        m = m.difference(trimesh.util.concatenate(list(cut)), engine="manifold")
    assert m.is_watertight, "part is not watertight"
    return m


def single_piece(poly, name):
    n = len(list(getattr(poly, "geoms", [poly])))
    assert n == 1, f"{name} is {n} separate pieces"


def pin(pt, z_top, z_bottom):
    """Follower pin: 3 mm peg pointing back (toward the base)."""
    return prism(pt.buffer(gm.PIN_D / 2, 32), z_bottom, z_top)


def export(mesh, name):
    OUT.mkdir(parents=True, exist_ok=True)
    mesh.export(OUT / f"{name}.stl")
    print(f"{name}.stl  {len(mesh.faces)} tris  {mesh.volume / 1000:.1f} cm^3")


# --------------------------------------------------------------- discs
def disc(groove, name, z):
    body = prism(gm.disc_outline(), z[0], z[1])
    slot = prism(gm.disc_groove(groove), z[1] - gm.GROOVE_DEPTH, z[1] + 1)
    notch = prism(gm.disc_notch(), z[0] - 1, z[1] + 1)
    export(csg(body, cut=[slot, notch]), name)


# ------------------------------------------------------------ carriage
def carriage():
    plate, heads, pt = gm.carriage_shape(0)
    single_piece(plate, "carriage")
    z0, z1 = gm.Z["carriage"]
    body = prism(plate, z0, z1)
    raised = [prism(h, z1 - 0.5, z1 + gm.EMBOSS) for h in heads]
    raised.append(pin(pt, z0 + 0.5, gm.Z["discT"][1] - gm.GROOVE_DEPTH + 0.3))
    export(csg(body, add=raised), "carriage")


# --------------------------------------------------------------- combs
def comb(sharp):
    spine, body, glyphs, pt = gm.comb_shape(0, sharp)
    key = "combS" if sharp else "combF"
    single_piece(body, key)
    z0, z1 = gm.Z[key]
    zs1 = gm.Z[key + "_spine"][1]
    disc_top = gm.Z["discS" if sharp else "discF"][1]
    thin = prism(body, z0, z1)
    thick = prism(spine, z0, zs1)
    raised = [prism(g, z1 - 0.5, z1 + gm.EMBOSS) for g in glyphs]
    raised.append(pin(pt, z0 + 0.5, disc_top - gm.GROOVE_DEPTH + 0.3))
    export(csg(thin, add=[thick] + raised), key)


# ----------------------------------------------------- shaft and lever
def shaft_and_spacers():
    z0 = -3.0
    z1 = gm.Z["lever"][1]
    d = gm.d_bore(0, 0, gm.SHAFT_D, 1.0)
    export(prism(d, z0, z1), "shaft")
    ring = Point(0, 0).buffer(6, 48).difference(gm.d_bore(0, 0))
    export(prism(ring, 0, 2.5), "spacer_2p5_x2")
    export(prism(ring, 0, 3.5), "spacer_3p5")


def lever():
    z0, z1 = gm.Z["lever"]
    s = translate(gm.lever_shape(0), -gm.CX, -gm.CY)
    body = prism(s, z0, z1)
    bore = prism(gm.d_bore(0, 0), z0 - 1, z1 + 1)
    export(csg(body, cut=[bore]), "lever")


# ---------------------------------------------------------- the sheets
def front_panel():
    z0, z1 = gm.Z["panel"]
    outline = gm.panel_outline()
    single_piece(outline, "front panel")
    body = prism(outline, z0, z1)
    engr = prism(unary_union([gm.engraved_staff(), gm.ring_ticks()]),
                 z1 - 0.4, z1 + 1)
    # back-face guides: L-ribs for the carriage, keeper and side ribs for
    # the two comb spines (see geometry.py for the layer heights)
    ribs = []
    zc = gm.Z["carriage"][0]
    for x_rib, x_foot in ((80.0, 81.5), (172.5, 170.0)):
        ribs.append(prism(gm.rect(min(x_rib, x_rib + 1.5), 100,
                                  max(x_rib, x_rib + 1.5), 190), zc - 0.5, z0))
        ribs.append(prism(gm.rect(min(x_foot, x_foot + 2.5), 100,
                                  max(x_foot, x_foot + 2.5), 190),
                          zc - 0.5, zc))
    zs = gm.Z["combS_spine"][1]
    ribs.append(prism(gm.rect(40, 177.25, 78, 178.75), zs + 0.3, z0))   # keeper
    ribs.append(prism(gm.rect(40, 174.5, 78, 176), gm.Z["combS"][1] + 0.3, z0))
    zf = gm.Z["combF_spine"][1]
    ribs.append(prism(gm.rect(40, 111.25, 72, 112.75), zf + 0.3, z0))   # keeper
    ribs.append(prism(gm.rect(40, 114, 78, 115.5), gm.Z["combF"][1] + 0.3, z0))
    export(csg(body, add=ribs, cut=[engr]), "front_panel")


def base_plate():
    outline = gm.rect(0, 0, gm.W, gm.H)
    outline = outline.difference(Point(gm.CX, gm.CY).buffer(gm.SHAFT_D / 2 + 0.3, 48))
    body = prism(outline, -3, 0)
    feats = []
    for x, y in gm.standoff_positions():
        post = Point(x, y).buffer(3.5, 32).difference(Point(x, y).buffer(1.4, 24))
        feats.append(prism(post, 0, gm.Z["panel"][0]))
    # spine channels: floor under each spine, one side wall each
    feats.append(prism(gm.rect(40, 176, 78, 180), 0, gm.Z["combS"][0] - 0.3))
    feats.append(prism(gm.rect(40, 180, 78, 181.5), 0, gm.Z["combS_spine"][1]))
    feats.append(prism(gm.rect(40, 110, 78, 114), 0, gm.Z["combF"][0] - 0.3))
    feats.append(prism(gm.rect(40, 108.5, 78, 110), 0, gm.Z["combF_spine"][1] + 0.5))
    export(csg(body, add=feats), "base_plate")


# ----------------------------------------------------------------- svg
def svg_path(poly):
    d = []
    for g in getattr(poly, "geoms", [poly]):
        if g.is_empty or not hasattr(g, "exterior"):
            continue
        for ring in [g.exterior] + list(g.interiors):
            pts = list(ring.coords)
            d.append("M " + " L ".join(f"{x:.2f} {gm.H - y:.2f}" for x, y in pts) + " Z")
    return " ".join(d)


def write_svg(name, layers, texts=()):
    """layers: (id, colour, geometry); cut lines in red, engraving blue."""
    body = []
    for lid, col, geom in layers:
        body.append(f'<path id="{lid}" d="{svg_path(geom)}" fill="none" '
                    f'stroke="{col}" stroke-width="0.2" fill-rule="evenodd"/>')
    for txt, x, y, size in texts:
        body.append(f'<text x="{x:.1f}" y="{gm.H - y + size * 0.35:.1f}" '
                    f'font-size="{size}" text-anchor="middle" fill="#00f" '
                    f'font-family="Noto Music, DejaVu Sans, sans-serif">{txt}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{gm.W}mm" '
           f'height="{gm.H}mm" viewBox="0 0 {gm.W} {gm.H}">\n'
           + "\n".join(body) + "\n</svg>\n")
    (OUT / f"{name}.svg").write_text(svg)
    print(f"{name}.svg")


def sheets_svg():
    labels = [(n.replace("b", "♭").replace("#", "♯"), x, y, 5)
              for n, x, y in gm.label_positions()]
    labels.append(("\U0001D11E", 22, gm.Y_E4 + 2 * gm.G, 26))
    for i in range(8):
        labels.append((str(i + 1), gm.NOTE_X0 + gm.NOTE_DX * i, gm.WIN_Y[0] - 5, 4))
    write_svg("front_panel",
              [("outline", "#f00", gm.rect(0, 0, gm.W, gm.H)),
               ("cuts", "#f00", gm.panel_cuts()),
               ("engrave", "#00f", unary_union([gm.engraved_staff(),
                                                 gm.ring_ticks()]))],
              labels)
    base = gm.rect(0, 0, gm.W, gm.H)
    holes = [Point(gm.CX, gm.CY).buffer(gm.SHAFT_D / 2 + 0.3, 48)]
    holes += [Point(x, y).buffer(1.4, 24) for x, y in gm.standoff_positions()]
    guides = unary_union([gm.rect(40, 176, 78, 181.5), gm.rect(40, 108.5, 78, 114)])
    write_svg("base_plate",
              [("outline", "#f00", base), ("holes", "#f00", unary_union(holes)),
               ("glue_guides_here", "#00f", guides)])


if __name__ == "__main__":
    disc(gm.TONIC_GROOVE, "disc_T_tonic", gm.Z["discT"])
    disc(gm.SHARP_GROOVE, "disc_S_sharps", gm.Z["discS"])
    disc(gm.FLAT_GROOVE, "disc_F_flats", gm.Z["discF"])
    carriage()
    comb(True)
    comb(False)
    shaft_and_spacers()
    lever()
    front_panel()
    base_plate()
    sheets_svg()
