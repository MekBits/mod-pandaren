"""Move the Northrend Skeleton and Ice Troll NPCs off race 20 and 21.

Pandaren take race IDs 20 and 21, but those IDs are not free: 30 of race 20's
CreatureDisplayInfoExtra rows (41 displays, Northrend Skeletons) and all 89 of
race 21's (104 displays, Ice Trolls -- the Drakkari across Zul'Drak and Grizzly
Hills) are in use. The baked texture of such a row covers only the body. For
everything else the client looks the NPC up by its extra row's race:

  hair and beard geosets   CharHairGeosets / CharacterFacialHairStyles
                           (race, sex, variation)
  hair texture (type 6)    CharSections hair row (race, sex, style, colour)
  skin extra (type 8)      CharSections skin row (race, sex, 0, skin), 2nd texture
  helmet model             <helm>_<ChrRaces.ClientPrefix><M|F>.m2

With pandaren's rows on 20/21 the skeletons and trolls would get pandaren
geosets and textures, and their helmets would look for _PaM models that are
not theirs.

So the rows get another race, chosen so the lookups give what stock 3.3.5 gave:

  Ice Troll (21)  -> Troll (8). Hair and facial geosets are identical for every
                     variation the NPCs use. The hair texture becomes the
                     troll's (Ice Troll's own Character\\IceTroll\\Hair00_0*.blp
                     has no slot left), and helmets load the troll's _TrM
                     models instead of the ice troll's _ItM.
  Skeleton (20)   -> Vrykul (16). Same hair geoset, and the hair texture is
                     the same file (stock race 20 already pointed at
                     Character\\Vrykul\\Hair00_0*.blp). Beards 2 and 3 are
                     Vrykul's 1 and 2. The vrykul helmets have _VrM models
                     (the skeleton had its own _NSM fit).

    The skeleton's bones are drawn with texture type 8, which stock race 20
    took from NorthrendSkeletonSkin00_0*_Extra.blp in its skin rows. Vrykul
    male skin colours 0-3 get those as their second texture; VrykulMale.m2
    binds no type-8 texture (types 6, 1, 2), so vrykul do not change.

CharacterFacialHairStyles can hold rows for races 16-19 that repeat a
(race, sex, variation) Blizzard's own row already has earlier in the file (a
client patched by another race module does). With two rows for one key the
result depends on which one the client keeps; the repeats are dropped, so
vrykul, tuskarr, forest trolls and taunka, and the skeletons now on 16, get
Blizzard's row whichever way the client reads.

Every new variation is found by geoset, not written down: STOCK below has what
stock 3.3.5 gave the NPC, and the target race's rows are searched for the
variation that gives the same. No match stops the run.

Only extras some CreatureDisplayInfo row points at are moved; the unreferenced
race-20 rows stay as dead data.

Moving away is the only option. A race ID above 21 for NPCs only would keep
their exact data, but the one per-race table measured in Wow.exe (character
creation's) holds 22 races, nothing shows the NPC path is any safer, and a
crash in Zul'Drak would hit everyone.

The same function runs in client/build_patch.py (on the DBCs of the patch being
built) and in tools/gen-npc-displays.py (for the server SQL), so the two sides
get the same rows. A second run changes nothing: once the rows are off 20/21
there is nothing left to move.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbc import DBC          # noqa: E402

TARGET = {20: 16, 21: 8}
MALE = 0

# Stock 3.3.5 (patch-enUS.MPQ) rows for the races pandaren replaced, male only:
# every NPC extra on 20/21 is male. Hair: variation -> (geoset, showScalp).
# Facial: variation -> the five geoset fields (the first is group 1, beards).
STOCK = {
    20: {'hair': {0: (0, 0)},
         'facial': {v: (v, 0, 0, 0, 0) for v in range(5)},
         'skin_extra': {c: 'Character\\NorthrendSkeleton\\Male\\NorthrendSkeletonSkin00_%02d_Extra.blp' % c
                        for c in range(4)}},
    21: {'hair': {0: (0, 0), 1: (2, 0), 2: (3, 0), 3: (4, 0), 4: (5, 0), 5: (6, 0)},
         'facial': {v: (0, v + 2, 0, 0, 0) for v in range(5)},
         'skin_extra': {}},
}
NPC_RACES = range(13, 20)

# CreatureDisplayInfoExtra fields
X_RACE, X_SEX, X_HAIR, X_FACIAL, X_BAKE = 1, 2, 5, 7, 20
X_COLUMNS = (['ID', 'DisplayRaceID', 'DisplaySexID', 'SkinID', 'FaceID', 'HairStyleID',
              'HairColorID', 'FacialHairID'] + ['NPCItemDisplay%d' % i for i in range(1, 12)]
             + ['Flags', 'BakeName'])
# CharSections fields
C_RACE, C_SEX, C_SECTION, C_TEX2, C_VAR, C_COLOUR = 1, 2, 3, 5, 8, 9


def find(dbc_dir, name):
    for fn in os.listdir(dbc_dir):
        if fn.lower() == name.lower():
            return os.path.join(dbc_dir, fn)
    sys.exit(f'{dbc_dir}: {name} missing')


def first_rows(path, key, value):
    """(key -> value) taking the first row per key, as a forward scan would."""
    d = DBC(path)
    out = {}
    for r in d.rows:
        v = d.ints(r)
        out.setdefault(key(v), value(v))
    return out


def variation(table, race, sex, want, what):
    """The target race's variation whose geosets equal `want`; lowest wins."""
    hits = sorted(var for (ra, se, var), got in table.items() if (ra, se) == (race, sex) and got == want)
    if not hits:
        sys.exit(f'no {what} variation for race {race} gives {want}')
    return hits[0]


def drop_repeated_facial(path):
    """Drop repeated (race, sex, variation) rows of the NPC races. Returns the count."""
    d = DBC(path)
    seen, keep, dropped = set(), [], 0
    for r in d.rows:
        v = d.ints(r)
        k = (v[0], v[1], v[2])
        if k in seen and v[0] in NPC_RACES:
            dropped += 1
            continue
        seen.add(k)
        keep.append(r)
    if dropped:
        d.write(path, rows=keep)
    return dropped, len(keep)


def remap_extras(src, dst, used, hair, facial):
    """CreatureDisplayInfoExtra with the used race-20/21 rows moved. Returns [(values, bake)]."""
    d = DBC(src)
    n = d.recsize // 4
    rows, changed = [], []
    for r in d.rows:
        v = list(d.ints(r))
        race = v[X_RACE]
        if race in TARGET and v[0] in used:
            if v[X_SEX] != MALE:
                sys.exit(f'extra {v[0]}: race {race} sex {v[X_SEX]}, STOCK only has male rows')
            if v[X_HAIR] not in STOCK[race]['hair'] or v[X_FACIAL] not in STOCK[race]['facial']:
                sys.exit(f'extra {v[0]}: race {race} hair {v[X_HAIR]} facial {v[X_FACIAL]} '
                         f'is not a stock 3.3.5 variation, so its geosets are unknown')
            to = TARGET[race]
            v[X_HAIR] = variation(hair, to, MALE, STOCK[race]['hair'][v[X_HAIR]], 'hair')
            v[X_FACIAL] = variation(facial, to, MALE, STOCK[race]['facial'][v[X_FACIAL]], 'facial')
            v[X_RACE] = to
            r = struct.pack('<%dI' % n, *v) + r[n * 4:]
            changed.append((v, d.s(v[X_BAKE])))
        rows.append(r)
    d.write(dst, rows=rows)
    return changed


def add_skin_extra(path):
    """Second texture on the target race's male skin rows, where it is empty.

    Returns the CharSections DBC and the IDs of the rows that carry it.
    """
    d = DBC(path)
    strings = bytearray(d.strings)
    n = d.recsize // 4
    rows, changed = list(d.rows), []
    want = {(TARGET[race], c): tex for race, s in STOCK.items() for c, tex in s['skin_extra'].items()}
    for i, r in enumerate(rows):
        v = list(d.ints(r))
        k = (v[C_RACE], v[C_COLOUR])
        if v[C_SEX] != MALE or v[C_SECTION] != 0 or v[C_VAR] != 0 or k not in want:
            continue
        have = d.s(v[C_TEX2])
        if have == want[k]:
            changed.append(v)
            continue
        if have:
            sys.exit(f'CharSections {v[0]}: second texture is {have!r}, not empty')
        v[C_TEX2] = len(strings)
        strings.extend(want[k].encode('utf-8') + b'\0')
        rows[i] = struct.pack('<%dI' % n, *v) + r[n * 4:]
        changed.append(v)
    if len(changed) != len(want):
        sys.exit(f'CharSections: {len(changed)} skin rows for the skeleton textures, expected {len(want)}')
    d.write(path, rows=rows, strings=bytes(strings))
    return DBC(path), [c[0] for c in changed]


def fix(dbc_dir, extra_src, extra_dst):
    """Move the NPC displays, editing CharSections and CharacterFacialHairStyles in
    dbc_dir in place and writing CreatureDisplayInfoExtra from extra_src to
    extra_dst. Returns (moved extras, CharSections DBC, its changed IDs, log lines).
    """
    log = []
    facial_path = find(dbc_dir, 'CharacterFacialHairStyles.dbc')
    dropped, left = drop_repeated_facial(facial_path)
    log.append(f'CharacterFacialHairStyles: -{dropped} repeated NPC-race rows, {left} left')
    hair = first_rows(find(dbc_dir, 'CharHairGeosets.dbc'), lambda v: (v[1], v[2], v[3]),
                      lambda v: (v[4], v[5]))
    facial = first_rows(facial_path, lambda v: (v[0], v[1], v[2]), lambda v: tuple(v[3:8]))
    cdi = DBC(find(dbc_dir, 'CreatureDisplayInfo.dbc'))
    used = {cdi.ints(r)[3] for r in cdi.rows}
    extras = remap_extras(extra_src, extra_dst, used, hair, facial)
    log.append(f'CreatureDisplayInfoExtra: {len(extras)} rows moved '
               f'({sum(1 for v, _ in extras if v[X_RACE] == 8)} to 8, '
               f'{sum(1 for v, _ in extras if v[X_RACE] == 16)} to 16)')
    cs, cs_ids = add_skin_extra(find(dbc_dir, 'CharSections.dbc'))
    log.append(f'CharSections: {len(cs_ids)} skin rows carry the skeleton extra texture')
    return extras, cs, cs_ids, log
