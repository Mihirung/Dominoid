# Dominoid

Musical domino tiles for resin printing.

The idea (Dad's): a set of solid tiles, each carrying a five-line staff
engraved edge to edge, so that tiles laid side by side form one continuous
staff. Each tile shows a single note letter as crotchets in its octave
positions, ledger lines included, with the letter as a heading at the top.
Using a circle-of-fifths chart to pick the notes of any scale (major,
minor, melodic and so on), you lay out or rack the tiles and the scale
appears as written notation — building it yourself teaches the sharps,
flats, scale degrees and raised sevenths far better than reading a chart.
Great for practising clarinet scales; LEDs per note may follow.

## The C prototype

`output/dominoid_C.stl` — 70 × 20 × 10 mm solid tile, millimetre units,
0.6 mm chamfered edges.

- **Engraved 0.4 mm deep** (recessed, for black paint-fill): the five
  staff lines, 0.35 mm wide, edge to edge across the long face; the
  capital C heading at the top.
- **Embossed 0.5 mm proud** (raised, tactile, dry-brush black): three
  crotchets for C in treble clef — middle C (C4, on one ledger line
  below the staff, stem up), third-space C (C5, stem down) and high C
  (C6, on the second ledger line above, both ledger lines shown, stem
  down). Stems bridge over the staff grooves so the grooves stay clean
  for paint.

![Design proof](output/dominoid_C_face.png)

![Heightmap of the STL](output/dominoid_C_render.png)

## Printing and finishing

- White resin, 0.05 mm layers or finer. Each tile uses about 14 cm³
  (roughly 16–17 g) of resin.
- Print with the decorated face up, tilted 15–25° with light supports on
  the back face, so the engraving and emboss stay crisp and free of
  suction marks.
- After wash and cure: work black acrylic (or a fine paint pen) into the
  engraved staff and heading, wipe the surface clean while wet, then
  brush the raised crotchets black.

## Generating tiles

```
pip install numpy scipy trimesh manifold3d shapely mapbox_earcut matplotlib
python3 dominoid.py          # the C prototype
python3 dominoid.py D E F    # any natural notes, one tile each
```

`dominoid.py` is parametric: tile dimensions, staff gauge, engrave and
emboss depths, and the octaves shown per letter are all constants at the
top. It places ledger lines and stem directions automatically from staff
position, and refuses geometry that will not fit the face.

Still to come for a full set: accidental tiles (sharp and flat glyphs), a
display rack, and the per-note LEDs.
