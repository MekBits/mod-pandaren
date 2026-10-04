#!/usr/bin/env python3
"""Generate the pandaren start outfits (charstartoutfit_dbc 925-948).

The outfits are cloned from the source races, not taken from MoP: MoP items do
not necessarily exist in 3.3.5, and Cataclysm removed weapon skills, so 4.x data
has no proficiency to inherit.

    race 20  Warrior/Hunter/Rogue/Priest  <- night elf
             Shaman/Mage                  <- draenei (night elves have neither)
    race 21  all six classes              <- troll (stands on the orc
                                             coordinates in Valley of Trials)

WHICH ROW IS THE SOURCE'S OUTFIT is not a free choice. `DBCStores.cpp` builds

    sCharStartOutfitMap[race | class << 8 | gender << 16] = outfit

by plain assignment in ascending ID order, over the .dbc file and the override
table together. The HIGHEST ID wins, not "override beats file". So the effective
outfit is worked out over both, the same way the server does it, and the
pandaren rows (925-948) sit above everything in a 3.3.5a file.

    gen-startoutfit.py --dbc <server dbc dir> [--overrides <dump>]
                       --columns <charstartoutfit_dbc.sql> --out <file.sql>

--overrides is the current charstartoutfit_dbc (TSV or a mysqldump INSERT);
without it the table is taken to be empty, as on a fresh database. A module
that rewrites the source races' outfits (mod-individual-progression does)
changes what a pandaren should get, so generate against the database those
rows are in.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbc import DBC  # noqa: E402

FIRST_ID = 925
CLASSES = [(1, 'Warrior'), (3, 'Hunter'), (4, 'Rogue'), (5, 'Priest'), (7, 'Shaman'), (8, 'Mage')]
SOURCE = {20: {1: 4, 3: 4, 4: 4, 5: 4, 7: 11, 8: 11}, 21: {c: 8 for c, _ in CLASSES}}
RACE_NAME = {4: 'night elf', 8: 'troll', 11: 'draenei'}
SLOTS = 24


def read_columns(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'CREATE TABLE[^(]*`charstartoutfit_dbc`\s*\((.*?)\n\)', text, re.S)
    if not m:
        sys.exit(f'{path}: no CREATE TABLE `charstartoutfit_dbc`')
    cols = re.findall(r'^\s*`([A-Za-z0-9_]+)`', m.group(1), re.M)
    if cols[:5] != ['ID', 'RaceID', 'ClassID', 'SexID', 'OutfitID'] or len(cols) != 5 + 3 * SLOTS:
        sys.exit(f'{path}: unexpected columns {cols[:6]}... ({len(cols)})')
    return cols


def load_overrides(path):
    """Rows as [ID, race, class, sex, outfit, items..., displays..., invtypes...]."""
    if not path:
        return {}
    text = open(path, encoding='utf-8', errors='replace').read()
    rows = {}
    if 'INSERT INTO' in text:
        tuples = [t.group(1) for m in re.finditer(r'VALUES\s*(.*?);', text, re.S)
                  for t in re.finditer(r'\(([^()]*)\)', m.group(1))]
        lines = [t.split(',') for t in tuples]
    else:
        lines = [ln.split('\t') for ln in text.splitlines() if ln.strip()]
    for f in lines:
        v = [int(x) for x in f]
        if len(v) != 5 + 3 * SLOTS:
            sys.exit(f'{path}: row {v[:1]} has {len(v)} columns')
        rows[v[0]] = v
    return rows


def from_dbc(path):
    d = DBC(path)
    if d.recsize != 4 * (2 + 3 * SLOTS):
        sys.exit(f'{path}: record size {d.recsize}, expected {4 * (2 + 3 * SLOTS)}')
    rows = {}
    for r in d.rows:
        v = d.ints(r)
        packed = v[1]
        rows[v[0]] = [v[0], packed & 0xFF, (packed >> 8) & 0xFF, (packed >> 16) & 0xFF,
                      (packed >> 24) & 0xFF] + [x - (1 << 32) if x >= (1 << 31) else x
                                                for x in v[2:]]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dbc', required=True)
    ap.add_argument('--overrides')
    ap.add_argument('--columns', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    cols = read_columns(a.columns)
    path = next((os.path.join(a.dbc, f) for f in os.listdir(a.dbc)
                 if f.lower() == 'charstartoutfit.dbc'), None)
    if not path:
        sys.exit(f'{a.dbc}: CharStartOutfit.dbc not found')
    rows = from_dbc(path)
    rows.update(load_overrides(a.overrides))

    ids = range(FIRST_ID, FIRST_ID + 2 * sum(len(s) for s in SOURCE.values()))
    # Rows in our range must be pandaren rows (the file DELETEs the range), and
    # no pandaren row may sit above it (the highest ID would win over ours).
    foreign = [i for i in ids if i in rows and rows[i][1] not in SOURCE]
    above = [i for i, v in rows.items() if v[1] in SOURCE and i >= ids.stop]
    if foreign or above:
        sys.exit(f'IDs {ids.start}-{ids.stop - 1}: other races\' rows {foreign}, pandaren rows '
                 f'above the range {above}; move FIRST_ID')

    # The server's own rule: ascending ID, last assignment wins.
    effective = {}
    for i in sorted(rows):
        if i in ids:
            continue
        v = rows[i]
        effective[(v[1], v[2], v[3])] = v

    out, nid = [], FIRST_ID
    for race in (20, 21):
        for cls, cname in CLASSES:
            for sex, sname in ((0, 'male'), (1, 'female')):
                src = SOURCE[race][cls]
                v = effective.get((src, cls, sex))
                if v is None:
                    sys.exit(f'no outfit for race {src} class {cls} sex {sex}')
                comment = (f'-- race {race} {cname:<7} {sname:<6} <- {RACE_NAME[src]} '
                           f'(ID {v[0]})')
                vals = [nid, race, cls, sex, 0] + v[5:]
                out.append((comment, vals))
                nid += 1

    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f"""-- GENERATED by tools/gen-startoutfit.py -- do not edit by hand.
--
-- Pandaren start outfits, cloned from the source races:
--   race 20  Warrior/Hunter/Rogue/Priest <- night elf, Shaman/Mage <- draenei
--   race 21  all six classes             <- troll
--
-- The source row is the EFFECTIVE outfit: sCharStartOutfitMap is filled in
-- ascending ID order over CharStartOutfit.dbc and charstartoutfit_dbc
-- together, so the highest ID for a race/class/sex wins. These rows come from
-- an unmodified 3.3.5a file and an empty table. A module that changes the
-- source races' outfits (mod-individual-progression does) changes what a
-- pandaren should start with: regenerate against your database.
--
-- The client's CharStartOutfit.dbc only draws the preview in character
-- creation; what a character gets is decided here.

DELETE FROM `charstartoutfit_dbc` WHERE `ID` BETWEEN {ids.start} AND {ids.stop - 1};

INSERT INTO `charstartoutfit_dbc` (`{'`, `'.join(cols)}`) VALUES
""")
        for i, (comment, vals) in enumerate(out):
            sep = ',' if i < len(out) - 1 else ';'
            f.write(f'{comment}\n  ({", ".join(str(x) for x in vals)}){sep}\n')
        f.write("""
-- Check:
--   SELECT RaceID, ClassID, SexID, COUNT(*) FROM charstartoutfit_dbc
--    WHERE ID BETWEEN 925 AND 948 GROUP BY 1,2,3;   -- expect 24 rows, all 1
--
-- And in game: log in with a real character of each class and check that the
-- weapon can be used. Bots are no use -- mod-playerbots equips them itself, so
-- their inventory says nothing about what Player::Create hands out.
""")
    print(f'{a.out}: {len(out)} outfits')


if __name__ == '__main__':
    main()
