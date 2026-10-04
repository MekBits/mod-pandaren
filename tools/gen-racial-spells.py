#!/usr/bin/env python3
"""Build the pandaren racial spells: the server SQL and, optionally, client DBCs.

One definition drives both sides. The client shows what its own Spell.dbc says
and the server applies what `spell_dbc` says, and when the two disagree nothing
errors -- the spell simply does nothing, or shows the wrong text.

Each racial is a CLONE of a shipping WotLK spell with named fields overridden,
never a row authored from 234 blank fields. The template supplies all the
attribute bits, interrupt flags and recovery categories that make a spell behave
like a spell, and those are exactly the parts that are invisible when wrong.

    Gourmand      <- 20552 Cultivation  (aura 98 MOD_SKILL_TALENT, misc = skill)
    Bouncy        <- 24350 Safe Fall    (aura 144 SAFE_FALL, honoured in
                                         Player::HandleFall via GetTotalAuraModifier)
    Inner Peace   <- 20552 Cultivation  (aura 200 MOD_XP_PCT, honoured in
                                         KillRewarder.cpp:181)
    Quaking Palm  <- 20549 War Stomp    (a racial with the right 2-minute
                                         recovery, no power cost and a stun aura;
                                         Sap would have dragged in its
                                         stealth-only Stances mask)

EPICUREAN IS DELIBERATELY ABSENT. Its effect is "double the stat benefit from
food", and WotLK has no aura for that and no hook to build it on: there is no
all-aura amount hook (AllSpellScript has OnCalcMaxDuration but no OnCalcAmount)
and `Player::GiveXP` is not the relevant path. Implementing it means patching the
core. Shipping a fifth racial that silently does nothing would be worse than
shipping four, so it is left out.

Note also that Inner Peace is an ADAPTATION, not a port. MoP's version doubles
rested experience; WotLK's rest pool is capped inside Player::SetRestBonus with
no hook, so this grants a flat kill-XP bonus instead. The tooltip says what it
actually does rather than what MoP's said.

    gen-racial-spells.py --dbc <dbc dir> --columns <spell_dbc.sql or column list>
                         [--sla-overrides <dump>] [--srci-overrides <dump>]
                         [--spell-overrides <dump>] --sql <file> [--out <dbc dir>]

--columns is AzerothCore's data/sql/base/db_world/spell_dbc.sql (the CREATE
TABLE is read from it) or a file with the comma-separated column list.

The --*-overrides files are the current contents of those override tables, and
they exist to prove the IDs handed out here are free in the TABLE as well as in
the .dbc: a free ID is free in both. Produce them as gen-race-skill-masks.py
documents. Left out, the tables are taken to be empty, as on a fresh database
(spell_dbc is not: AzerothCore ships rows of its own, so pass it).

--out writes Spell.dbc, SkillLine.dbc and SkillLineAbility.dbc with the new
rows appended; client/build_patch.py does the same for a client.
"""
import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbc import DBC          # noqa: E402

NAME0, RANK0, DESC0, TIP0 = 136, 153, 170, 187
STRING_FIELDS = (set(range(136, 152)) | set(range(153, 169)) |
                 set(range(170, 186)) | set(range(187, 203)))
FLOAT_FIELDS = ({47} | set(range(77, 80)) | set(range(101, 104)) |
                set(range(119, 122)) | set(range(216, 219)) | set(range(229, 232)))

SKILL_LINE = 791                     # free: SkillLine.dbc tops out at 790 (mod-worgoblin uses 789/790)
SKILL_LINE_NAME = 'Racial - Pandaren'
SKILL_CATEGORY = 9                   # what 126/733/789 use -- the racial category
RACE_MASK = (1 << 19) | (1 << 20)    # races 20 and 21
CLASS_MASK = 1 | 4 | 8 | 16 | 64 | 128   # 221: warrior, hunter, rogue, priest, shaman, mage

# A FREE ID IS FREE IN THE FILE **AND** IN THE OVERRIDE TABLE.
#
# SkillLineAbility.dbc tops out at 31448, but 31500 is taken in the table:
# mod-worgoblin puts worgen's Two Forms (spell 68996) there, and it is the only
# row that teaches it. Overwriting it would take human form away from every
# worgen at their next login, silently, because racials are
# PLAYERSPELL_TEMPORARY and re-derived from skills every time.
SLA_FIRST_ID = 31600

# SkillRaceClassInfo row for the new skill line. Without it the racials do not
# exist: Player::LearnDefaultSkill (Player.cpp:12122) bails on `if (!rcInfo)
# return;` before granting the skill, so learnSkillRewardedSpells never runs.
# ID 1068 is free in the 3.3.5a file and in every module we know of; the script
# checks both the file and the table. Flags 1170 is what the racial lines in
# the file use, except orc, blood elf and draenei's 146.
SRCI_ID = 1068
SRCI_FLAGS = 1170

RACIALS = [
    dict(id=80001, name='Gourmand', template=20552,
         desc='Cooking skill increased by $s1.',
         over={133: 1467,          # Cooking's icon
               110: 185,           # EffectMiscValue0 = SKILL_COOKING
               80: 14}),           # EffectBasePoints0; effective amount is +1
    dict(id=80002, name='Bouncy', template=24350,
         desc='Reduces falling damage.',
         over={133: 1726,
               80: 9}),            # 10 yards knocked off the fall distance
    dict(id=80003, name='Inner Peace', template=20552,
         desc='Experience gained from killing creatures increased by $s1%.',
         over={133: 51,            # Inner Fire's icon
               95: 200,            # EffectApplyAuraName0 = SPELL_AURA_MOD_XP_PCT
               110: 0,             # no skill id
               80: 9}),            # +10%
    dict(id=80004, name='Quaking Palm', template=20549,
         desc='Strikes the target with lightning speed, incapacitating them for $d.',
         over={133: 249,           # Sap's icon -- a hand
               3: 30,              # Mechanic = MECHANIC_SAPPED, so damage breaks it
               28: 1,              # instant, not War Stomp's cast time
               32: 4718594,        # Sap's AuraInterruptFlags: break on damage
               40: 35,             # SpellDuration index 35 == 4000 ms
               46: 2,              # melee range, not War Stomp's self
               86: 6,              # TARGET_UNIT_TARGET_ENEMY, not the AoE ring
               92: 0}),            # no radius
]


def taken_ids(path):
    """IDs already present in a `_dbc` override table, from TSV or a mysqldump."""
    if not path:
        return set()
    text = open(path, encoding='utf-8', errors='replace').read()
    if 'INSERT INTO' in text:
        return {int(t.group(1))
                for m in re.finditer(r'VALUES\s*(.*?);', text, re.S)
                for t in re.finditer(r'\(\s*(-?\d+)', m.group(1))}
    return {int(line.split('\t')[0]) for line in text.splitlines() if line.strip()}


def clone(d, template_id, spell):
    """Copy the template row, then apply overrides and strings."""
    src = None
    for r in d.rows:
        if d.ints(r)[0] == template_id:
            src = list(d.ints(r))
            break
    if src is None:
        sys.exit(f'template spell {template_id} not found')
    src[0] = spell['id']
    for f, v in spell['over'].items():
        src[f] = v & 0xFFFFFFFF
    return src


def find(dbcdir, name):
    for fn in os.listdir(dbcdir):
        if fn.lower() == name.lower():
            return os.path.join(dbcdir, fn)
    sys.exit(f'{dbcdir}: {name} not found')


def read_columns(path):
    """spell_dbc's columns, from AzerothCore's CREATE TABLE or a comma list."""
    text = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'CREATE TABLE[^(]*`spell_dbc`\s*\((.*?)\n\)', text, re.S)
    if m:
        cols = re.findall(r'^\s*`([A-Za-z0-9_]+)`', m.group(1), re.M)
    else:
        cols = [c.strip() for c in text.strip().split(',')]
    bad = [c for c in cols if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', c)]
    if bad or not cols or cols[0] != 'ID':
        sys.exit(f'{path}: column list looks wrong: first={cols[:1]} malformed={bad[:5]}')
    return cols


def ids_in_dbc(path):
    d = DBC(path)
    return {d.ints(r)[0] for r in d.rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dbc', required=True, help='dbc directory (server or client)')
    ap.add_argument('--columns', required=True)
    ap.add_argument('--sla-overrides', help='current skilllineability_dbc contents')
    ap.add_argument('--srci-overrides', help='current skillraceclassinfo_dbc contents')
    ap.add_argument('--spell-overrides', help='current spell_dbc contents')
    ap.add_argument('--sql', required=True)
    ap.add_argument('--out', help='also write client DBCs with the rows appended')
    a = ap.parse_args()

    # A free ID is free in the file AND in the override table. When the table
    # holds every one of this module's IDs, they are this file's rows from an
    # earlier run, not someone else's.
    for dbc_name, path, ids, table in (
            ('SkillLineAbility.dbc', a.sla_overrides,
             range(SLA_FIRST_ID, SLA_FIRST_ID + len(RACIALS)), 'skilllineability_dbc'),
            ('SkillRaceClassInfo.dbc', a.srci_overrides, [SRCI_ID], 'skillraceclassinfo_dbc'),
            ('Spell.dbc', a.spell_overrides, [s['id'] for s in RACIALS], 'spell_dbc')):
        in_table = taken_ids(path) & set(ids)
        if in_table == set(ids):
            print(f'  {table}: IDs {min(ids)}-{max(ids)} are already installed, taken as ours')
            in_table = set()
        clash = sorted((in_table | ids_in_dbc(find(a.dbc, dbc_name))) & set(ids))
        if clash:
            sys.exit(f'{table}: ID(s) {clash} are already used. '
                     f'Move the constant in this script; do not delete their rows.')
    if a.out:
        os.makedirs(a.out, exist_ok=True)

    cols = read_columns(a.columns)

    # ---- Spell.dbc ------------------------------------------------------
    d = DBC(find(a.dbc, 'Spell.dbc'))
    if d.fields != 234 or len(cols) != 234:
        sys.exit(f'expected 234 fields/columns, got {d.fields}/{len(cols)}')
    existing = {d.ints(r)[0] for r in d.rows}
    strings = bytearray(d.strings)
    cache = {}

    # offset -> text, so the SQL can resolve strings we just added. Reading them
    # back through the original DBC would silently yield '' -- DBC.s() returns
    # empty for any offset past the block it was loaded with, and every spell
    # would have shipped nameless.
    text_at = {}

    def intern(s):
        if not s:
            return 0
        if s not in cache:
            cache[s] = len(strings)
            text_at[cache[s]] = s
            strings.extend(s.encode('utf-8') + b'\0')
        return cache[s]

    newrows, sqlrows = [], []
    for sp in RACIALS:
        if sp['id'] in existing:
            sys.exit(f"spell id {sp['id']} already exists; pick another")
        v = clone(d, sp['template'], sp)
        # Fill every locale slot, not just enUS: the client picks by its own
        # locale and an empty slot shows as a blank spell name.
        for k in range(16):
            v[NAME0 + k] = intern(sp['name'])
            v[DESC0 + k] = intern(sp['desc'])
            v[RANK0 + k] = 0
            v[TIP0 + k] = 0
        newrows.append(struct.pack('<234I', *v))
        sqlrows.append(v)
    if a.out:
        d.write(os.path.join(a.out, 'Spell.dbc'), rows=d.rows + newrows, strings=bytes(strings))
        print(f'  Spell.dbc: {len(d.rows)} + {len(newrows)} = {len(d.rows) + len(newrows)} rows')

    # ---- SkillLine.dbc --------------------------------------------------
    sl = DBC(find(a.dbc, 'SkillLine.dbc'))
    slstr = bytearray(sl.strings)
    off = len(slstr)
    slstr.extend(SKILL_LINE_NAME.encode('utf-8') + b'\0')
    v = [0] * (sl.recsize // 4)
    v[0], v[1] = SKILL_LINE, SKILL_CATEGORY
    for k in range(16):
        v[3 + k] = off                       # DisplayName_Lang
    v[19] = 16712190                         # locale mask, as the stock rows use
    if SKILL_LINE in {sl.ints(r)[0] for r in sl.rows}:
        sys.exit(f'SkillLine.dbc: id {SKILL_LINE} already exists')
    if a.out:
        sl.write(os.path.join(a.out, 'SkillLine.dbc'),
                 rows=sl.rows + [struct.pack('<%dI' % (sl.recsize // 4), *v)],
                 strings=bytes(slstr))
        print(f'  SkillLine.dbc: +1 row (id {SKILL_LINE} {SKILL_LINE_NAME!r})')

    # ---- SkillLineAbility.dbc -------------------------------------------
    sla = DBC(find(a.dbc, 'SkillLineAbility.dbc'))
    n = sla.recsize // 4
    slarows, slasql = [], []
    for i, sp in enumerate(RACIALS):
        v = [0] * n
        v[0], v[1], v[2], v[3] = SLA_FIRST_ID + i, SKILL_LINE, sp['id'], RACE_MASK
        slarows.append(struct.pack('<%dI' % n, *v))
        slasql.append((SLA_FIRST_ID + i, sp['id']))
    if a.out:
        sla.write(os.path.join(a.out, 'SkillLineAbility.dbc'), rows=sla.rows + slarows)
        print(f'  SkillLineAbility.dbc: +{len(slarows)} rows from {SLA_FIRST_ID}')

    # ---- SQL ------------------------------------------------------------
    def lit(f, x):
        if f in STRING_FIELDS:
            if x == 0:
                return "''"
            txt = text_at.get(x) or d.s(x)
            if not txt:
                sys.exit(f'string field {f} resolved to empty at offset {x}')
            return "'" + txt.replace('\\', '\\\\').replace("'", "\\'") + "'"
        if f in FLOAT_FIELDS:
            return '%g' % struct.unpack('<f', struct.pack('<I', x))[0]
        return str(x - (1 << 32) if x >= (1 << 31) else x)

    body = ['-- GENERATED by tools/gen-racial-spells.py -- do not edit by hand.',
            '--',
            '-- Four racials. Epicurean is deliberately left out: its effect needs a',
            '-- core patch, and a fifth racial that silently does nothing would be',
            "-- worse than four that work. See the script's docstring.",
            '--',
            '-- The client side is in the client patch (Spell.dbc, SkillLine.dbc,',
            '-- SkillLineAbility.dbc). Both sides must be there: the client shows its',
            '-- own text, the server applies its own effect, and if they disagree',
            '-- nothing fails -- the spell just does nothing.',
            '',
            'DELETE FROM `spell_dbc` WHERE `ID` IN (%s);' % ', '.join(str(s['id']) for s in RACIALS),
            '',
            'INSERT INTO `spell_dbc` (`%s`) VALUES' % '`, `'.join(cols)]
    body.append(',\n'.join(
        '  (' + ', '.join(lit(f, x) for f, x in enumerate(v)) + ')' for v in sqlrows) + ';')

    body += ['',
             '-- The racial skill line. Racials are handed out by the player GETTING the',
             '-- skill at creation (playercreateinfo_skills), after which',
             '-- learnSkillRewardedSpells() teaches everything in SkillLineAbility --',
             '-- exactly how skill 789 "Racial - Worgen" works.',
             'DELETE FROM `skillline_dbc` WHERE `ID` = %d;' % SKILL_LINE,
             "INSERT INTO `skillline_dbc` (`ID`, `CategoryID`, `DisplayName_Lang_enUS`, `DisplayName_Lang_Mask`)",
             "  VALUES (%d, %d, '%s', 16712190);" % (SKILL_LINE, SKILL_CATEGORY, SKILL_LINE_NAME),
             '',
             '-- Skill line %d owns exactly %d-%d; the first DELETE removes any'
             % (SKILL_LINE, SLA_FIRST_ID, SLA_FIRST_ID + len(RACIALS) - 1),
             '-- other row on it. It goes by SKILL LINE, never by an ID range below %d:'
             % SLA_FIRST_ID,
             "-- 31500 is worgen's Two Forms in mod-worgoblin, the only row that",
             '-- teaches it. A free ID is free in the DBC file AND in the override table.',
             'DELETE FROM `skilllineability_dbc`',
             '  WHERE `SkillLine` = %d AND `ID` NOT BETWEEN %d AND %d;'
             % (SKILL_LINE, SLA_FIRST_ID, SLA_FIRST_ID + len(RACIALS) - 1),
             'DELETE FROM `skilllineability_dbc` WHERE `ID` BETWEEN %d AND %d;'
             % (SLA_FIRST_ID, SLA_FIRST_ID + len(RACIALS) - 1),
             'INSERT INTO `skilllineability_dbc` (`ID`, `SkillLine`, `Spell`, `RaceMask`, `ClassMask`) VALUES']
    body.append(',\n'.join('  (%d, %d, %d, %d, 0)' % (i, SKILL_LINE, s, RACE_MASK)
                           for i, s in slasql) + ';')
    body += ['',
             '-- And the gate in front of it all. `Player::LearnDefaultSkill` starts with',
             '--     SkillRaceClassInfoEntry const* rcInfo = GetSkillRaceClassInfo(...);',
             '--     if (!rcInfo) return;                      // no log, no error',
             '-- so without this one row skill %d is never granted, and none of the' % SKILL_LINE,
             '-- four racials is ever taught. `_LoadSkills` would also DELETE the skill',
             '-- at login if it arrived some other way.',
             '-- zz_pandaren_09 does the same for the existing skill lines.',
             'DELETE FROM `skillraceclassinfo_dbc` WHERE `ID` = %d;' % SRCI_ID,
             'INSERT INTO `skillraceclassinfo_dbc`',
             '  (`ID`, `SkillID`, `RaceMask`, `ClassMask`, `Flags`, `MinLevel`,'
             ' `SkillTierID`, `SkillCostIndex`)',
             '  VALUES (%d, %d, %d, %d, %d, 0, 0, 0);'
             % (SRCI_ID, SKILL_LINE, RACE_MASK, CLASS_MASK, SRCI_FLAGS),
             '',
             '-- Give the races the skill line at creation. raceMask %d = race 20|21.'
             % RACE_MASK,
             'DELETE FROM `playercreateinfo_skills` WHERE `raceMask` = %d AND `skill` = %d;'
             % (RACE_MASK, SKILL_LINE),
             'INSERT INTO `playercreateinfo_skills` (`raceMask`, `classMask`, `skill`, `rank`)',
             '  VALUES (%d, 0, %d, 0);' % (RACE_MASK, SKILL_LINE),
             '',
             '-- Check:',
             '--   SELECT ID, Name_Lang_enUS FROM spell_dbc WHERE ID BETWEEN 80001 AND 80004;',
             '--   SELECT * FROM skilllineability_dbc WHERE SkillLine = %d;' % SKILL_LINE,
             '--   and in game: a new pandaren must have all four in its spellbook.',
             '--   Racials are NOT in character_spell -- they are PLAYERSPELL_TEMPORARY and',
             '--   re-derived at every login. Count character_skills for %d instead.' % SKILL_LINE,
             '']
    open(a.sql, 'w', encoding='utf-8', newline='\n').write('\n'.join(body))
    print(f'  {a.sql}: {len(RACIALS)} spells + skill line + {len(slasql)} abilities')


if __name__ == '__main__':
    main()
