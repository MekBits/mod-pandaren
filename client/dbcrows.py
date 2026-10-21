"""The pandaren rows of each client DBC, and how they go onto a base file.

The rows live in client/rows/<Name>.csv, and <Name>.<part>.csv when more than
one generator writes rows for the same file: one column per 4-byte field, named
c0..cN. String fields hold the text; every other field holds the raw unsigned
32-bit value (floats included, so nothing is rounded on the way through).

Each DBC is applied in one of these ways:

  race    Rows keyed by race. Base rows for races 20 and 21 are dropped first
          (some modules fill every race slot with placeholder rows), then ours
          are appended. IDs are renumbered from the base file's highest ID + 1:
          nothing else refers to them.
  fixed   Rows with fixed IDs that the server SQL uses too. An ID that is
          already in the base file with different content is an error, except
          where `replace` says the base row is ours to take.

  bits    Rows keyed by ID whose fields hold only the pandaren race bits. The
          base row's bits 19 and 20 are replaced by them, the rest is kept.

Four files are computed from the base instead of shipped as rows: CharBaseInfo
(the race/class matrix), CharStartOutfit (the preview outfit, cloned from the
source races), SkillRaceClassInfo (the source races' masks mirrored) and
CreatureDisplayInfoExtra (the skeleton and ice troll NPCs moved off races 20
and 21, tools/npcdisplays.py). Two are edited after the rows are in:
SkillLineAbility, where the races that share a skill line's spells (a language,
a weapon skill) get the pandaren bits as in the server SQL, and Achievement,
whose "Know Thy Enemy" text counts the races.
"""
import csv
import glob
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from dbc import DBC  # noqa: E402

RACES = (20, 21)
CLASSES = (1, 3, 4, 5, 7, 8)          # warrior, hunter, rogue, priest, shaman, mage
RACE_BIT = {20: 1 << 19, 21: 1 << 20}

# Source race per pandaren race and class, as in the server SQL.
SOURCE = {(20, c): (11 if c in (7, 8) else 4) for c in CLASSES}
SOURCE.update({(21, c): 8 for c in CLASSES})


def _r(a, b):
    return list(range(a, b))


SCHEMAS = {
    'ChrRaces': dict(mode='fixed', strings=[6, 11] + _r(14, 30) + _r(31, 47) + _r(48, 64) + [65, 66, 67],
                     replace=True),
    'CharSections': dict(mode='race', strings=[4, 5, 6], race=1, has_id=True),
    'CharHairGeosets': dict(mode='race', strings=[], race=1, has_id=True),
    'CharacterFacialHairStyles': dict(mode='race', strings=[], race=0, has_id=False),
    'NameGen': dict(mode='race', strings=[1], race=2, has_id=True),
    'BarberShopStyle': dict(mode='fixed', strings=_r(2, 18) + _r(19, 35)),
    'CreatureModelData': dict(mode='fixed', strings=[2]),
    'CreatureDisplayInfo': dict(mode='fixed', strings=[6, 7, 8, 9]),
    'Spell': dict(mode='fixed', strings=_r(136, 152) + _r(153, 169) + _r(170, 186) + _r(187, 203)),
    'SkillLine': dict(mode='fixed', strings=_r(3, 19) + _r(20, 36) + _r(37, 53)),
    'SkillLineAbility': dict(mode='fixed', strings=[]),
    'SpellIcon': dict(mode='fixed', strings=[1]),
    'Achievement': dict(mode='fixed', strings=_r(4, 20) + _r(21, 37) + _r(43, 59)),
    'Achievement_Criteria': dict(mode='fixed', strings=_r(9, 25)),
    # MoP's own sounds: emotes, error voices, combat sounds and the files behind them
    'EmotesTextSound': dict(mode='fixed', strings=[], ident=(1, 2)),
    'VocalUISounds': dict(mode='fixed', strings=[], ident=(1, 2)),
    'CreatureSoundData': dict(mode='fixed', strings=[]),
    'SoundEntries': dict(mode='fixed', strings=_r(2, 13) + [23]),
    'HelmetGeosetVisData': dict(mode='bits', strings=[], mask=sum(RACE_BIT.values())),
}
COMPUTED = ('CharBaseInfo', 'CharStartOutfit', 'SkillRaceClassInfo', 'CreatureDisplayInfoExtra')
ALL = list(SCHEMAS) + list(COMPUTED)

# DBCs that only make sense together. Asking for one builds all of them.
GROUPS = (('Achievement', 'Achievement_Criteria'),
          ('Spell', 'SpellIcon'),
          ('CreatureDisplayInfoExtra', 'CreatureDisplayInfo', 'CharSections', 'CharHairGeosets',
           'CharacterFacialHairStyles'))


def row_files(rows_dir, name):
    """<name>.csv and every <name>.<part>.csv."""
    files = [os.path.join(rows_dir, name + '.csv')] if \
        os.path.exists(os.path.join(rows_dir, name + '.csv')) else []
    files += sorted(glob.glob(os.path.join(glob.escape(rows_dir), name + '.*.csv')))
    if not files:
        sys.exit(f'{rows_dir}: no rows for {name}')
    return files


def read_rows(path, nfields, strings):
    """[(values, {col: text})] from a rows CSV."""
    out = []
    with open(path, newline='', encoding='utf-8') as f:
        rd = csv.reader(f)
        head = next(rd)
        if head != [f'c{i}' for i in range(nfields)]:
            sys.exit(f'{path}: expected {nfields} columns c0..c{nfields - 1}, got {len(head)}')
        for row in rd:
            vals, text = [], {}
            for i, x in enumerate(row):
                if i in strings:
                    vals.append(0)
                    text[i] = x
                else:
                    vals.append(int(x))
            out.append((vals, text))
    return out


def write_rows(path, d, rows, strings):
    """Write DBC rows (raw records of DBC d) as a rows CSV."""
    n = d.recsize // 4
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow([f'c{i}' for i in range(n)])
        for r in rows:
            v = d.ints(r)
            w.writerow([d.s(x) if i in strings else x for i, x in enumerate(v)])


class Builder:
    """A base DBC plus edits; strings are interned into a copy of its block."""

    def __init__(self, path):
        self.d = DBC(path)
        self.n = self.d.recsize // 4
        self.strings = bytearray(self.d.strings)
        self.cache = {}
        self.rows = [list(self.d.ints(r)) for r in self.d.rows]
        self.base_count = len(self.rows)

    def s(self, text):
        if not text:
            return 0
        if text not in self.cache:
            self.cache[text] = len(self.strings)
            self.strings.extend(text.encode('utf-8') + b'\0')
        return self.cache[text]

    def text(self, row, col):
        return self.d.s(row[col]) if row[col] < len(self.d.strings) else \
            bytes(self.strings[row[col]:self.strings.index(b'\0', row[col])]).decode('utf-8')

    def save(self, path):
        packed = [struct.pack('<%dI' % self.n, *[x & 0xFFFFFFFF for x in r]) for r in self.rows]
        self.d.write(path, rows=packed, strings=bytes(self.strings))


def identity(b, row, sc):
    """What a row is, independent of the fields a rebuild may change: the
    schema's `ident` fields, else its first string (a name or a path), else
    field 1."""
    if sc.get('ident'):
        return tuple(row[c] for c in sc['ident'])
    return b.text(row, min(sc['strings'])) if sc['strings'] else row[1]


def apply_rows(name, base_path, rows_dir, out_path, log, ours_replaceable=False):
    """ours_replaceable: the base may hold this module's rows from an earlier
    build (building --over it). A fixed ID whose row differs is then replaced
    when it is still the same thing (same name, path or parent), and refused
    otherwise, because then another patch uses the ID."""
    sc = SCHEMAS[name]
    b = Builder(base_path)
    ours = [r for path in row_files(rows_dir, name)
            for r in read_rows(path, b.n, set(sc['strings']))]
    if sc['mode'] == 'fixed':
        ids = [v[0] for v, _ in ours]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            sys.exit(f'{name}: ID(s) {dup} appear in more than one row file')
    dropped = 0
    if sc['mode'] == 'race':
        keep = [r for r in b.rows if r[sc['race']] not in RACES]
        dropped = len(b.rows) - len(keep)
        b.rows = keep
        nid = max((r[0] for r in b.rows), default=0) + 1
        for vals, text in ours:
            v = list(vals)
            if sc['has_id']:
                v[0] = nid
                nid += 1
            for c, t in text.items():
                v[c] = b.s(t)
            b.rows.append(v)
    elif sc['mode'] == 'bits':
        keepmask = ~sc['mask'] & 0xFFFFFFFF
        index = {r[0]: r for r in b.rows}
        for vals, _ in ours:
            row = index.get(vals[0])
            if row is None:
                sys.exit(f'{name}: the base file has no row {vals[0]}')
            for c in range(1, b.n):
                new = (row[c] & keepmask) | (vals[c] & sc['mask'])
                if new != row[c]:
                    row[c] = new
                    dropped += 1
    else:
        index = {r[0]: i for i, r in enumerate(b.rows)}
        for vals, text in ours:
            v = list(vals)
            for c, t in text.items():
                v[c] = b.s(t)
            i = index.get(v[0])
            if i is None:
                b.rows.append(v)
                continue
            old = b.rows[i]
            same = all((b.text(old, c) == b.text(v, c)) if c in sc['strings'] else old[c] == v[c]
                       for c in range(b.n))
            ours_before = ours_replaceable and identity(b, old, sc) == identity(b, v, sc)
            if not same and not sc.get('replace') and not ours_before:
                sys.exit(f'{name}: ID {v[0]} is already used by a different row in the base '
                         f'file. Another patch claims it. The IDs are fixed (the server SQL '
                         f'uses the same ones where the server reads the table), so they '
                         f'cannot be renumbered here.')
            b.rows[i] = v
            dropped += 1
    b.save(out_path)
    log(name, b.base_count, dropped, len(b.rows))


def build_charbaseinfo(base_path, out_path, log):
    data = open(base_path, 'rb').read()
    magic, count, fields, recsize, sblock = struct.unpack_from('<4s4I', data, 0)
    if (fields, recsize) != (2, 2):
        sys.exit(f'{base_path}: CharBaseInfo has {fields} fields in {recsize} bytes, expected 2/2')
    pairs = [tuple(data[20 + i * 2:22 + i * 2]) for i in range(count)]
    keep = [p for p in pairs if p[0] not in RACES]
    new = keep + [(r, c) for r in RACES for c in CLASSES]
    with open(out_path, 'wb') as f:
        f.write(struct.pack('<4s4I', b'WDBC', len(new), 2, 2, 1))
        for r, c in new:
            f.write(bytes((r, c)))
        f.write(b'\0')
    log('CharBaseInfo', count, count - len(keep), len(new))


def build_charstartoutfit(base_path, out_path, log):
    """The preview outfit: the source race's effective row, per class and sex.

    The client fills its map the way the server does, in ascending ID order with
    the last row winning, so the effective row is the highest ID for the key.
    """
    b = Builder(base_path)
    keep = [r for r in b.rows if (r[1] & 0xFF) not in RACES]
    dropped = len(b.rows) - len(keep)
    eff = {}
    for r in sorted(keep, key=lambda r: r[0]):
        eff[(r[1] & 0xFF, (r[1] >> 8) & 0xFF, (r[1] >> 16) & 0xFF)] = r
    nid = max(r[0] for r in keep) + 1
    for race in RACES:
        for cls in CLASSES:
            for sex in (0, 1):
                src = eff.get((SOURCE[(race, cls)], cls, sex))
                if src is None:
                    sys.exit(f'CharStartOutfit: no outfit for race {SOURCE[(race, cls)]} '
                             f'class {cls} sex {sex} in the base file')
                v = list(src)
                v[0] = nid
                v[1] = race | (cls << 8) | (sex << 16) | (src[1] & 0xFF000000)
                keep.append(v)
                nid += 1
    b.rows = keep
    b.save(out_path)
    log('CharStartOutfit', b.base_count, dropped, len(b.rows))


SRCI_ROW = [1068, 791, RACE_BIT[20] | RACE_BIT[21], 221, 1170, 0, 0, 0]
PLAYABLE = 0xFFF


def mirror(mask, classes):
    """The server SQL's rule (tools/gen-race-skill-masks.py), on one row."""
    if mask == 0 or mask >= (1 << 31) or bin(mask & PLAYABLE).count('1') == 1:
        return mask
    if (mask & (1 << 3) and (classes == 0 or classes & 29)) or (mask & (1 << 10) and classes & 192):
        mask |= RACE_BIT[20]
    if mask & (1 << 7):
        mask |= RACE_BIT[21]
    return mask


def build_skillraceclassinfo(base_path, out_path, log):
    b = Builder(base_path)
    changed = 0
    for r in b.rows:
        m = mirror(r[2], r[3])
        if m != r[2]:
            r[2] = m
            changed += 1
    ids = {r[0]: i for i, r in enumerate(b.rows)}
    if SRCI_ROW[0] in ids:
        if b.rows[ids[SRCI_ROW[0]]] != SRCI_ROW:
            sys.exit(f'SkillRaceClassInfo: ID {SRCI_ROW[0]} is already used by a different row')
    else:
        b.rows.append(list(SRCI_ROW))
    b.save(out_path)
    log('SkillRaceClassInfo', b.base_count, 0, len(b.rows), f'{changed} masks mirrored')


def mirror_skilllineability(path, log):
    """The spells a skill line hands out and the languages the client lets you
    speak are decided by SkillLineAbility's race mask, on the client as well as
    on the server. A language row (668 Common, 669 Orcish) without the race's
    bit gives "You can't speak that language". Same rule as the server's
    zz_pandaren_09 and as SkillRaceClassInfo above."""
    b = Builder(path)
    changed = 0
    for r in b.rows:
        m = mirror(r[3], r[4])
        if m != r[3]:
            r[3] = m
            changed += 1
    b.save(path)
    log('SkillLineAbility', b.base_count, 0, len(b.rows), f'{changed} masks mirrored')


def build_npc_displays(base_path, out_path, log):
    """The skeleton and ice troll NPCs off races 20 and 21 (tools/npcdisplays.py).

    Edits CharSections and CharacterFacialHairStyles next to out_path, which
    must be built already, and writes the moved CreatureDisplayInfoExtra there.
    """
    import npcdisplays
    extras, _, cs_ids, _ = npcdisplays.fix(os.path.dirname(out_path), base_path, out_path)
    count = len(DBC(out_path).rows)
    log('CreatureDisplayInfoExtra', count, len(extras), count,
        f'{len(extras)} rows moved to troll/vrykul, {len(cs_ids)} vrykul skin rows')


# Edits after a DBC's rows are in.
POST = {'SkillLineAbility': mirror_skilllineability}

NUMBERS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
           'nine', 'ten', 'eleven', 'twelve']
COUNTED = (246, 1005)                 # Know Thy Enemy, Alliance and Horde
COUNT_TEXT = re.compile(r'\b(%s) different races' % '|'.join(NUMBERS))


def count_races(dbcdir, log):
    """Rewrite "on five different races" to the number of race criteria.

    Every race module that adds a criterion to Know Thy Enemy makes the number in
    its description wrong, so it is counted from the criteria the built file has
    rather than written as a number. Text that does not say it this way is left
    alone.
    """
    a = Builder(os.path.join(dbcdir, 'Achievement.dbc'))
    c = DBC(os.path.join(dbcdir, 'Achievement_Criteria.dbc'))
    count = {}
    for r in c.rows:
        v = c.ints(r)
        if v[1] in COUNTED:
            count[v[1]] = count.get(v[1], 0) + 1
    changed = 0
    for row in a.rows:
        n = count.get(row[0], 0)
        if row[0] not in COUNTED or not n or n >= len(NUMBERS):
            continue
        for col in range(21, 37):
            text = a.text(row, col)
            new = COUNT_TEXT.sub(NUMBERS[n] + ' different races', text)
            if new != text:
                row[col] = a.s(new)
                changed += 1
    a.save(os.path.join(dbcdir, 'Achievement.dbc'))
    log('Achievement', a.base_count, 0, len(a.rows),
        f'Know Thy Enemy: {count.get(246, 0)} / {count.get(1005, 0)} races ({changed} texts)')


COMPUTE = {
    'CharBaseInfo': build_charbaseinfo,
    'CharStartOutfit': build_charstartoutfit,
    'SkillRaceClassInfo': build_skillraceclassinfo,
    'CreatureDisplayInfoExtra': build_npc_displays,
}
