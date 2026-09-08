"""Assembly proof: front view and x-ray of the automaton at a given key."""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

import geometry as gm


def fill(ax, geom, hole="white", **kw):
    geoms = getattr(geom, "geoms", [geom])
    for g in geoms:
        if g.is_empty or not hasattr(g, "exterior"):
            continue
        x, y = g.exterior.xy
        ax.fill(x, y, **kw)
        for ring in g.interiors:
            rx, ry = ring.xy
            ax.fill(rx, ry, color=hole, lw=0)


def draw_front(ax, k):
    fill(ax, gm.rect(0, 0, gm.W, gm.H), color="#e9e6df", lw=0)
    win = gm.panel_cuts()
    fill(ax, win, color="white", lw=0)
    plate, heads, _ = gm.carriage_shape(k)
    fill(ax, plate.intersection(win), color="white", lw=0)
    for h in heads:
        fill(ax, h.intersection(win), color="black", lw=0)
    for sharp in (True, False):
        spine, body, glyphs, _ = gm.comb_shape(k, sharp)
        n = gm.visible_glyph_count(k, sharp)
        fill(ax, body.intersection(win), color="#f2f0ea", lw=0)
        for g in glyphs[:n]:
            fill(ax, g.intersection(win), color="black", lw=0)
    fill(ax, gm.staff_bars(), color="black", lw=0)
    fill(ax, gm.engraved_staff(), color="black", lw=0)
    fill(ax, gm.ring_ticks(), color="#555", lw=0)
    for name, x, y in gm.label_positions():
        ax.text(x, y, name, ha="center", va="center", fontsize=8,
                color="#333")
    fill(ax, gm.lever_shape(k), color="#1a4a8a", lw=0)
    ax.text(22, gm.Y_E4 + 2 * gm.G, "\U0001D11E", fontsize=34,
            ha="center", va="center", family="DejaVu Sans")
    ax.set_title(f"front view — key of {gm.KEY_NAMES[k]}")


def draw_xray(ax, k):
    phi = gm.pointer_angle(k)
    ax.add_patch(Circle((gm.CX, gm.CY), gm.R_DISC, fill=False, ec="#999"))
    for groove, col in ((gm.FLAT_GROOVE, "#c98"), (gm.SHARP_GROOVE, "#9c8"),
                        (gm.TONIC_GROOVE, "#89c")):
        fill(ax, gm.disc_groove(groove, phi), color=col, lw=0, alpha=0.8)
    fill(ax, gm.disc_notch(phi), color="#444", lw=0)
    for sharp, col in ((False, "#a66"), (True, "#6a6")):
        spine, body, glyphs, pin = gm.comb_shape(k, sharp)
        fill(ax, body, color=col, lw=0, alpha=0.6)
        for g in glyphs:
            fill(ax, g, color=col, lw=0)
        ax.add_patch(Circle((pin.x, pin.y), gm.PIN_D / 2, color="black"))
    plate, heads, pin = gm.carriage_shape(k)
    fill(ax, plate, color="#66a", lw=0, alpha=0.35)
    for h in heads:
        fill(ax, h, color="#225", lw=0)
    ax.add_patch(Circle((pin.x, pin.y), gm.PIN_D / 2, color="black"))
    x, y = gm.rect(0, 0, gm.W, gm.H).exterior.xy
    ax.plot(x, y, color="#999", lw=1)
    for w in gm.panel_windows():
        wx, wy = w.exterior.xy
        ax.plot(wx, wy, color="#999", lw=0.8, ls="--")
    fill(ax, gm.lever_shape(k), color="#1a4a8a", lw=0, alpha=0.5)
    ax.set_title(f"x-ray — lever at {phi:g}°")


def main(keys):
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2 * len(keys), figsize=(6.4 * 2 * len(keys),
                                                        7.4))
    for i, k in enumerate(keys):
        for ax, fn in ((axes[2 * i], draw_front), (axes[2 * i + 1], draw_xray)):
            fn(ax, k)
            ax.set_xlim(-5, gm.W + 5)
            ax.set_ylim(-5, gm.H + 5)
            ax.set_aspect("equal")
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "assembly_proof.png", dpi=110)
    print(out / "assembly_proof.png")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [0, 5, -3])
