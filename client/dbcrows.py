"""The pandaren rows of each client DBC, and how they go onto a base file.

The rows live in client/rows/<Name>.csv: one column per 4-byte field, named
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

Three files are computed from the base instead of shipped as rows: CharBaseInfo
(the race/class matrix), CharStartOutfit (the preview outfit, cloned from the
source races) and SkillRaceClassInfo (the source races' masks mirrored).
"""
import csv
import os
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
}
COMPUTED = ('CharBaseInfo', 'CharStartOutfit', 'SkillRaceClassInfo')
ALL = list(SCHEMAS) + list(COMPUTED)


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


def apply_rows(name, base_path, rows_dir, out_path, log):
    sc = SCHEMAS[name]
    b = Builder(base_path)
    ours = read_rows(os.path.join(rows_dir, name + '.csv'), b.n, set(sc['strings']))
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
            if not same and not sc.get('replace'):
                sys.exit(f'{name}: ID {v[0]} is already used by a different row in the base '
                         f'file. Another patch claims it; the server SQL uses the same ID, '
                         f'so this cannot be renumbered here.')
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


COMPUTE = {
    'CharBaseInfo': build_charbaseinfo,
    'CharStartOutfit': build_charstartoutfit,
    'SkillRaceClassInfo': build_skillraceclassinfo,
}
