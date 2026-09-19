"""Does the 21-tile set spell every scale a Bb clarinettist plays?"""
LET = "CDEFGAB"
PITCH = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
ACC_TXT = {-2:"bb", -1:"b", 0:"", 1:"#", 2:"##"}
MODES = {
    "major":          (0,2,4,5,7,9,11),
    "natural minor":  (0,2,3,5,7,8,10),
    "harmonic minor": (0,2,3,5,7,8,11),
    "melodic minor":  (0,2,3,5,7,9,11),
}
# Written keys for a Bb clarinet = concert key up a major 2nd, so all 12
# pitch classes appear. These are the conventional written spellings.
MAJOR_TONICS  = ["C","G","D","A","E","B","F#","Db","Ab","Eb","Bb","F"]
MINOR_TONICS  = ["A","E","B","F#","C#","G#","D","G","C","F","Bb","Eb"]

def spell(tonic, mode):
    letter, acc = tonic[0], {"":0,"#":1,"b":-1}[tonic[1:]]
    i0, root = LET.index(letter), (PITCH[letter] + acc) % 12
    out = []
    for i, iv in enumerate(MODES[mode]):
        L = LET[(i0 + i) % 7]
        want = (root + iv) % 12
        a = (want - PITCH[L]) % 12
        a = a - 12 if a > 6 else a           # fold to -5..6
        out.append((L, a))
    return out

need, impossible = set(), []
for mode, tonics in (("major", MAJOR_TONICS),
                     *[(m, MINOR_TONICS) for m in
                       ("natural minor","harmonic minor","melodic minor")]):
    for t in tonics:
        notes = spell(t, mode)
        if any(abs(a) > 1 for _, a in notes):
            impossible.append((f"{t} {mode}",
                               " ".join(L + ACC_TXT.get(a, f"?{a}") for L, a in notes)))
        need.update(notes)

have = {(L, a) for L in LET for a in (-1, 0, 1)}
missing = {n for n in need if abs(n[1]) > 1}
print(f"distinct note names required : {len(need)}")
print(f"tiles in the set             : {len(have)}")
print(f"required and NOT in the set  : "
      f"{sorted(L+ACC_TXT.get(a,str(a)) for L,a in missing) or 'none'}")
print(f"\nin the set but never needed  : "
      f"{sorted(L+ACC_TXT[a] for L,a in (have - need)) or 'none'}")
print(f"\nscales needing a double accidental ({len(impossible)}):")
for name, sp in impossible:
    print(f"   {name:22s} {sp}")
