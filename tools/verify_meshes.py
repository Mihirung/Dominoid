import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import numpy as np, trimesh, dominoid as dm
from shapely.ops import unary_union
from shapely import contains_xy
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

res = 0.05
names = dm.full_set()
fig, axes = plt.subplots(3, 7, figsize=(16, 21))
bad = []
for idx, (L, acc) in enumerate(names):
    stem = f"dominoid_{L}{dm.ACC_SUFFIX[acc]}"
    m = trimesh.load(f"output/{stem}.stl")
    tris = m.vertices[m.faces]; nz = m.face_normals[:, 2]; zs = tris[:, :, 2]

    # 1. printable solid?
    solid = m.is_volume
    # 2. ramp slivers in the interior (emboss wall artefacts)
    sl = (nz > 1e-6) & ((zs.max(axis=1) - zs.min(axis=1)) > 1e-6)
    cen = tris[sl].mean(axis=1)
    inner = (cen[:,0]>1.2)&(cen[:,0]<18.8)&(cen[:,1]>1.2)&(cen[:,1]<68.8)
    t = tris[sl][inner]
    ramp = 0.0 if len(t)==0 else float(np.linalg.norm(
        np.cross(t[:,1]-t[:,0], t[:,2]-t[:,0]), axis=1).sum()/2)
    # 3. emboss footprint vs design
    top = tris[(np.abs(zs - 5.5) < 1e-6).all(axis=1)]
    W, H = int(20/res), int(70/res); grid = np.zeros((H, W), bool)
    for tr in top:
        x0,x1 = max(int(tr[:,0].min()/res),0), min(int(tr[:,0].max()/res)+1,W)
        y0,y1 = max(int(tr[:,1].min()/res),0), min(int(tr[:,1].max()/res)+1,H)
        if x0>=x1 or y0>=y1: continue
        X,Y = np.meshgrid((np.arange(x0,x1)+.5)*res, (np.arange(y0,y1)+.5)*res)
        d=(tr[1,1]-tr[2,1])*(tr[0,0]-tr[2,0])+(tr[2,0]-tr[1,0])*(tr[0,1]-tr[2,1])
        if abs(d)<1e-12: continue
        a=((tr[1,1]-tr[2,1])*(X-tr[2,0])+(tr[2,0]-tr[1,0])*(Y-tr[2,1]))/d
        b=((tr[2,1]-tr[0,1])*(X-tr[2,0])+(tr[0,0]-tr[2,0])*(Y-tr[2,1]))/d
        grid[y0:y1,x0:x1] |= (a>=-1e-9)&(b>=-1e-9)&((1-a-b)>=-1e-9)
    pos = sorted(dm.staff_position(L,o) for o in dm.DEFAULT_OCTAVES[L])
    want = unary_union(dm.note_column_polys(dm.column_xs(len(pos)), pos, acc))
    X,Y = np.meshgrid((np.arange(W)+.5)*res, (np.arange(H)+.5)*res)
    wg = contains_xy(want, X, Y)
    extra = (grid&~wg).sum()*res*res; missing = (wg&~grid).sum()*res*res

    ok = solid and ramp < 0.05 and extra < 0.05 and missing < 0.05
    if not ok: bad.append((stem, solid, ramp, extra, missing))
    print(f"{stem:22s} solid={solid} ramp={ramp:6.3f} extra={extra:.3f} "
          f"missing={missing:.3f}  {'ok' if ok else 'BAD'}")

    # heightmap panel
    zbuf = np.full((H, W), np.nan)
    for tr in tris[nz > 1e-6]:
        x0,x1 = max(int(tr[:,0].min()/res),0), min(int(tr[:,0].max()/res)+1,W)
        y0,y1 = max(int(tr[:,1].min()/res),0), min(int(tr[:,1].max()/res)+1,H)
        if x0>=x1 or y0>=y1: continue
        X2,Y2 = np.meshgrid((np.arange(x0,x1)+.5)*res, (np.arange(y0,y1)+.5)*res)
        d=(tr[1,1]-tr[2,1])*(tr[0,0]-tr[2,0])+(tr[2,0]-tr[1,0])*(tr[0,1]-tr[2,1])
        if abs(d)<1e-12: continue
        a=((tr[1,1]-tr[2,1])*(X2-tr[2,0])+(tr[2,0]-tr[1,0])*(Y2-tr[2,1]))/d
        b=((tr[2,1]-tr[0,1])*(X2-tr[2,0])+(tr[0,0]-tr[2,0])*(Y2-tr[2,1]))/d
        c=1-a-b; ins=(a>=-1e-9)&(b>=-1e-9)&(c>=-1e-9); Z=a*tr[0,2]+b*tr[1,2]+c*tr[2,2]
        patch=zbuf[y0:y1,x0:x1]
        np.copyto(patch, Z, where=ins&(np.isnan(patch)|(Z>patch)))
    ax = axes[idx // 7][idx % 7]
    ax.imshow(zbuf, origin="lower", extent=(0,20,0,70), cmap="gray",
              vmin=4.3, vmax=5.7, interpolation="nearest")
    ax.set_title(L + dm.ACC_SYMBOL[acc], fontsize=15)
    ax.set_xticks([]); ax.set_yticks([])
fig.suptitle("Dominoid — all 21 tiles, rendered from the finished STL geometry "
             "(dark = engraved, light = embossed)", fontsize=14, y=0.997)
fig.tight_layout()
fig.savefig(str(__import__("pathlib").Path(__file__).resolve().parent.parent / "output" / "dominoid_set_stl.png"), dpi=85, bbox_inches="tight")
print("\n" + ("ALL 21 TILES PASS" if not bad else f"{len(bad)} FAILED: {bad}"))
