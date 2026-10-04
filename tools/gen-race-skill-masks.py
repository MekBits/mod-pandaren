#!/usr/bin/env python3
"""Generate the SkillRaceClassInfo and SkillLineAbility rows pandaren need.

`Player::LearnDefaultSkill` opens with

    SkillRaceClassInfoEntry const* rcInfo = GetSkillRaceClassInfo(skillId, getRace(), getClass());
    if (!rcInfo)
        return;                                  // no log, no error

and `GetSkillRaceClassInfo` skips any row whose RaceMask is non-zero and lacks
`1 << (race - 1)`. A skill with no matching row is therefore not merely
ungranted, it cannot exist:

  * `Player::IsSpellFitByClassAndRace` needs the same lookup, and the trainer
    calls it for both listing and teaching, so the trainer has nothing to offer.
  * `Player::_LoadSkills` deletes any character_skills row without one, with an
    ERROR line, so anything acquired anyway is stripped at the next login.

Without these rows a pandaren learns none of its racials, cannot speak its
faction language, cannot learn a mount and has no shaman talent trees.

A `_dbc` table is an OVERRIDE table: it holds only the rows somebody has already
overridden, and an UPDATE reaches those and no others. Every row that lives only
in the .dbc file has to be INSERTED, with the value it effectively has. So the
input is the server's .dbc files plus the current contents of the two override
tables, and the output writes whole rows.

A row that is already in the table when the SQL runs (another module overrode it
after this file was generated) is not replaced: ON DUPLICATE KEY UPDATE applies
the same mirror rule to the mask the row has, so the other module's change
survives and the pandaren bits are added on top.

    gen-race-skill-masks.py --dbc <server dbc dir> [--srci-overrides <dump>]
                            [--sla-overrides <dump>] --out <file.sql>

The override dumps are optional; without them the tables are taken to be empty,
as they are on a fresh AzerothCore database. Produce them with either

    mysql -N -e 'SELECT * FROM skillraceclassinfo_dbc' acore_world > srci.tsv

or, from a mysqldump, the INSERT line itself. Both forms are accepted.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbc import DBC  # noqa: E402

# Mirror the source race, per class, the same sources zz_pandaren_03 and
# zz_pandaren_07 use for the action bar and start outfit:
#
#   race 20, Warrior/Hunter/Rogue/Priest  <- NIGHT ELF
#   race 20, Shaman/Mage                  <- DRAENEI (night elves have neither)
#   race 21, all six classes              <- TROLL
#
# A row with ClassMask 0 counts for every class, but only the night elf decides
# race 20 for it: draenei-only rows for all classes would hand race 20 things a
# night elf warrior cannot have. Testing for an "all races" value instead would
# not work: SkillRaceClassInfo alone carries 2047, 32767, 262143, 524287,
# 2097151 and 4294967295, all meaning "everyone" to whoever wrote them.
BIT_NIGHTELF, BIT_DRAENEI, BIT_TROLL = 1 << 3, 1 << 10, 1 << 7
RACE_A, RACE_H = 1 << 19, 1 << 20    # races 20 and 21
CLASSES_NIGHTELF = 1 | 4 | 8 | 16    # warrior, hunter, rogue, priest
CLASSES_DRAENEI = 64 | 128           # shaman, mage
SOURCE = {(20, 1): 4, (20, 3): 4, (20, 4): 4, (20, 5): 4, (20, 7): 11, (20, 8): 11,
          (21, 1): 8, (21, 3): 8, (21, 4): 8, (21, 5): 8, (21, 7): 8, (21, 8): 8}

# A mask naming exactly ONE race is that race's own line: its racial skill and
# its racial language. Those are not mirrored, or Alliance pandaren would learn
# Shadowmeld and speak Darnassian. Counted over races 1-12, so a module that
# adds races 9 and 12 does not change the answer.
PLAYABLE = 0xFFF


def mirror(mask, classes):
    """The row's mask with the pandaren bits, or None when it gets none.

    A row that already has the bits (generated from a database this file has
    run on) is still returned: the file must insert it on a fresh database.
    """
    if mask <= 0 or mask >= (1 << 31):    # 0 and -1 both mean everyone
        return None
    if bin(mask & PLAYABLE).count('1') == 1:
        return None
    add = 0
    if (mask & BIT_NIGHTELF and (classes == 0 or classes & CLASSES_NIGHTELF)) or \
            (mask & BIT_DRAENEI and classes & CLASSES_DRAENEI):
        add |= RACE_A
    if mask & BIT_TROLL:
        add |= RACE_H
    return (mask | add) if add else None


def sql_mirror(col, ccol):
    """mirror() as an ON DUPLICATE KEY UPDATE assignment on the existing row."""
    m, c = f'`{col}`', f'`{ccol}`'
    many = f'BIT_COUNT({m} & {PLAYABLE}) > 1'
    alliance = (f'(({m} & {BIT_NIGHTELF}) <> 0 AND ({c} = 0 OR ({c} & {CLASSES_NIGHTELF}) <> 0)'
                f' OR ({m} & {BIT_DRAENEI}) <> 0 AND ({c} & {CLASSES_DRAENEI}) <> 0)')
    return (f'{m} = {m}'
            f' | IF({m} > 0 AND {many} AND {alliance}, {RACE_A}, 0)'
            f' | IF({m} > 0 AND {many} AND ({m} & {BIT_TROLL}) <> 0, {RACE_H}, 0)')


def signed(v):
    """DBC fields are unsigned; both _dbc tables declare RaceMask as signed int."""
    return v - (1 << 32) if v >= (1 << 31) else v


def load_overrides(path, ncols):
    """Read an override table as {id: [ints]}, from TSV or a mysqldump INSERT."""
    if not path:
        return {}
    text = open(path, encoding='utf-8', errors='replace').read()
    rows = {}
    if 'INSERT INTO' in text:
        for m in re.finditer(r'VALUES\s*(.*?);', text, re.S):
            for tup in re.finditer(r'\(([^()]*)\)', m.group(1)):
                f = [int(x) for x in tup.group(1).split(',')]
                rows[f[0]] = f
    else:
        for line in text.splitlines():
            if not line.strip():
                continue
            f = [int(x) for x in line.split('\t')]
            rows[f[0]] = f
    bad = [i for i, f in rows.items() if len(f) != ncols]
    if bad:
        sys.exit(f'{path}: {len(bad)} row(s) have the wrong column count '
                 f'(expected {ncols}, e.g. id {bad[0]} has {len(rows[bad[0]])})')
    return {i: [x & 0xFFFFFFFF for x in f] for i, f in rows.items()}


def effective(dbc_path, overrides, ncols):
    """The rows the server actually has (the .dbc file, overridden by the
    table), and the file's own rows."""
    d = DBC(dbc_path)
    if d.recsize // 4 != ncols:
        sys.exit(f'{dbc_path}: {d.recsize // 4} fields, expected {ncols}')
    filerows = {}
    for r in d.rows:
        v = list(d.ints(r))
        filerows[v[0]] = v
    rows = dict(filerows)
    rows.update({i: list(f) for i, f in overrides.items()})
    return rows, filerows


SRCI_COLS = ['ID', 'SkillID', 'RaceMask', 'ClassMask', 'Flags',
             'MinLevel', 'SkillTierID', 'SkillCostIndex']
SLA_COLS = ['ID', 'SkillLine', 'Spell', 'RaceMask', 'ClassMask',
            'ExcludeRace', 'ExcludeClass', 'MinSkillLineRank', 'SupercededBySpell',
            'AcquireMethod', 'TrivialSkillLineRankHigh', 'TrivialSkillLineRankLow',
            'CharacterPoints_1', 'CharacterPoints_2']


def emit(body, table, cols, rows, filerows, maskpos, names, label):
    """Append an INSERT ... ON DUPLICATE KEY UPDATE for every row that needs bits.

    A row is written when the file's row or the table's row lacks the bits. A
    row that has them only because this file ran before is still written, or a
    fresh database would not get it.

    Field 1 is the skill line in both tables (SkillID / SkillLine), so one name
    lookup serves both; the name is the only way a reviewer can tell that 98 is
    the faction language and not an item id.
    """
    changed = []
    for v in sorted(rows.values()):
        new = mirror(v[maskpos], v[maskpos + 1])
        if new is None:
            continue
        in_file = filerows.get(v[0])
        if in_file is not None and not (new & ~in_file[maskpos]) and not (new & ~v[maskpos]):
            continue
        w = list(v)
        w[maskpos] = new
        changed.append(w)
    if not changed:
        sys.exit(f'{table}: nothing to change -- that cannot be right, check the inputs')
    body += ['', '-- ' + '-' * 72, f'-- {label}', f'-- {len(changed)} rows.', '',
             'INSERT INTO `%s` (`%s`) VALUES' % (table, '`, `'.join(cols))]
    # The comma has to come BEFORE the trailing comment, or the comment eats it.
    for i, w in enumerate(changed):
        note = names.get(w[1], '')
        sep = ',' if i < len(changed) - 1 else ''
        body.append('  (%s)%s%s' % (', '.join(str(signed(x)) for x in w), sep,
                                    ('   -- ' + note) if note else ''))
    body.append('ON DUPLICATE KEY UPDATE ' + sql_mirror(cols[maskpos], cols[maskpos + 1]) + ';')
    return body, changed


CLASSES = {1: 'Warrior', 3: 'Hunter', 4: 'Rogue', 5: 'Priest', 7: 'Shaman', 8: 'Mage'}


def verify(rows, maskpos, names, label):
    """Re-run GetSkillRaceClassInfo's own test and require source-race parity.

    A generator that reports "183 rows" proves nothing; the question is whether
    a pandaren of each class can reach every skill line its source race can, as
    that class.
    """
    def match(skill, race, cls):
        out = []
        for v in rows.values():
            if v[1] != skill:
                continue
            if v[maskpos] and not (v[maskpos] & (1 << (race - 1))):
                continue
            cm = v[maskpos + 1]
            if cm and not (cm & (1 << (cls - 1))):
                continue
            out.append(v)
        return out

    skills = sorted({v[1] for v in rows.values()})
    lost = {}
    for pand in (20, 21):
        for cls in CLASSES:
            src = SOURCE[(pand, cls)]
            for sk in skills:
                hit = match(sk, src, cls)
                if not hit or match(sk, pand, cls):
                    continue
                # Reached only through a single-race mask: the source race's own
                # line, which is supposed to stay out of reach.
                if all(bin(v[maskpos] & PLAYABLE).count('1') == 1 for v in hit):
                    continue
                lost.setdefault((pand, sk), set()).add(CLASSES[cls])
    print(f'    {label}: ', end='')
    if not lost:
        print('parity with the source races for all 6 classes  [OK]')
        return 0
    print(f'{len(lost)} SKILL LINE(S) STILL UNREACHABLE')
    for (pand, sk), cs in sorted(lost.items()):
        print(f'      race {pand} skill {sk} {names.get(sk, "(not in SkillLine.dbc)")!r}'
              f' -- {", ".join(sorted(cs))}')
    return len(lost)


def find(dbcdir, name):
    for fn in os.listdir(dbcdir):
        if fn.lower() == name.lower():
            return os.path.join(dbcdir, fn)
    sys.exit(f'{dbcdir}: {name} not found')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dbc', required=True, help='the server\'s dbc directory')
    ap.add_argument('--srci-overrides')
    ap.add_argument('--sla-overrides')
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default='an unmodified 3.3.5a client',
                    help='what the input is, for the file header')
    a = ap.parse_args()

    sl = DBC(find(a.dbc, 'SkillLine.dbc'))
    names = {}
    for r in sl.rows:
        v = sl.ints(r)
        names[v[0]] = sl.s(v[3])

    srci, srci_file = effective(find(a.dbc, 'SkillRaceClassInfo.dbc'),
                     load_overrides(a.srci_overrides, len(SRCI_COLS)), len(SRCI_COLS))
    sla, sla_file = effective(find(a.dbc, 'SkillLineAbility.dbc'),
                    load_overrides(a.sla_overrides, len(SLA_COLS)), len(SLA_COLS))

    body = [
        '-- GENERATED by tools/gen-race-skill-masks.py -- do not edit by hand.',
        '--',
        '-- The race masks zz_pandaren_04 cannot reach, because they live in the .dbc',
        '-- FILE and not in the override table. An UPDATE only hits rows someone has',
        '-- already overridden; the rest must be INSERTed with the value they have.',
        '--',
        '-- Without this file a pandaren learns none of its four racials, cannot',
        '-- speak its faction language, cannot learn a mount and has no shaman',
        '-- talent trees. All silently: LearnDefaultSkill returns without logging,',
        '-- and _LoadSkills then deletes any skill without a SkillRaceClassInfo row.',
        '--',
        '-- The rule mirrors the source race: night elf for race 20 (draenei for its',
        '-- shamans and mages, which night elves cannot be), troll for race 21.',
        "-- Masks naming exactly one race are left alone: that race's own racial and",
        '-- language line, and mirroring it would give Alliance pandaren Shadowmeld',
        '-- and Darnassian.',
        '--',
        f'-- The rows are generated from {a.source}. If your server\'s DBC files',
        '-- or override tables differ (another race module that ships its own DBC',
        '-- files), regenerate this file from yours.',
        '--',
        '-- A row already in the table (another module overrode it and ran first) is',
        '-- not replaced: ON DUPLICATE KEY UPDATE applies the same rule to the mask',
        '-- it already has. That also makes a rerun a no-op.',
    ]

    body, srci_changed = emit(body, 'skillraceclassinfo_dbc', SRCI_COLS, srci, srci_file, 2, names,
                              'SkillRaceClassInfo: the gate for every skill')
    body, sla_changed = emit(body, 'skilllineability_dbc', SLA_COLS, sla, sla_file, 3, names,
                             'SkillLineAbility: which spells a skill line hands out')

    body += ['',
             '-- Check. Neither may return more than 0:',
             '--',
             '--   SELECT COUNT(*) FROM skillraceclassinfo_dbc',
             '--    WHERE RaceMask > 0 AND (RaceMask & 8) <> 0',
             '--      AND (ClassMask = 0 OR (ClassMask & %d) <> 0)' % CLASSES_NIGHTELF,
             '--      AND BIT_COUNT(RaceMask & 4095) > 1 AND (RaceMask & %d) = 0;' % RACE_A,
             '--   SELECT COUNT(*) FROM skilllineability_dbc',
             '--    WHERE RaceMask > 0 AND (RaceMask & 128) <> 0',
             '--      AND BIT_COUNT(RaceMask & 4095) > 1 AND (RaceMask & %d) = 0;' % RACE_H,
             '--',
             '-- And in game: create a pandaren and list its skills.',
             '--   SELECT skill FROM acore_characters.character_skills WHERE guid = <new pandaren>;',
             '-- Must contain 791 (racial line), 98 or 109 (language), 777 and 778.',
             '']
    open(a.out, 'w', encoding='utf-8', newline='\n').write('\n'.join(body))
    print(f'  {a.out}')
    print(f'    skillraceclassinfo_dbc: {len(srci_changed)} rows')
    print(f'    skilllineability_dbc:   {len(sla_changed)} rows')

    for changed, store, maskpos, label in (
            (srci_changed, srci, 2, 'SkillRaceClassInfo'),
            (sla_changed, sla, 3, 'SkillLineAbility')):
        for w in changed:
            store[w[0]] = w
        if verify(store, maskpos, names, label):
            sys.exit('generated file does not close the gap -- do not ship it')


if __name__ == '__main__':
    main()
