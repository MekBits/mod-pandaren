#!/usr/bin/env python3
"""Build the pandaren achievements: client rows and the matching server SQL.

The achievements that name races one by one get pandaren, and the realm firsts
get one per faction:

  1431 / 1432  Realm First! Level 80 Pandaren, Alliance / Horde (new)
  246 / 1005   Know Thy Enemy: a killing blow on a pandaren of the other faction
  291          Check Your Head: a pumpkin head on a pandaren
  2422         Shake Your Bunny-Maker: rabbit ears on a female pandaren, 18+

Pandaren are one race with two race ids (20 Alliance, 21 Horde). The criteria
that list races one by one check the target's race with a
`T_PLAYER_CLASS_RACE` data row, which takes a single race; ours use the
criteria script `achievement_pandaren_target` (src/) that takes either.

Every row is a clone of a row the base already has: the realm firsts of night
elf (1409) and troll (1412), and an existing criterion of each achievement.
The clone keeps flags, category and the criteria type; only the named fields
change. A new criterion on an achievement whose minimum criteria count is 0
(all four here) is required like the others, without touching the achievement.

    gen-achievements.py --dbc <client DBFilesClient dir>
                        --columns <azerothcore>/data/sql/base/db_world
                        --rows client/rows --sql data/sql/db-world/zz_pandaren_13-achievements.sql

Writes client/rows/Achievement.csv, Achievement_Criteria.csv and
SpellIcon.achievements.csv (MoP's Achievement_Character_Pandaren_Female icon),
and the SQL for achievement_dbc, achievement_criteria_dbc and
achievement_criteria_data.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbc import DBC  # noqa: E402

ICON_ID = 4400
ICON_PATH = 'Interface\\Icons\\Achievement_Character_Pandaren_Female'
SCRIPT = 'achievement_pandaren_target'

# Achievement: 0 ID, 1 Faction (-1 both, 0 Horde, 1 Alliance), 4-19 Title,
# 21-36 Description, 40 UI order, 42 icon, 60 minimum criteria.
A_TITLE, A_DESC, A_FACTION, A_ORDER, A_ICON, A_MIN = 4, 21, 1, 40, 42, 60
ACHIEVEMENTS = [
    dict(id=1431, template=1409, faction=1, order=163,
         title='Realm First! Level 80 Pandaren',
         desc='First pandaren of the Alliance on the realm to achieve level 80.'),
    dict(id=1432, template=1412, faction=0, order=164,
         title='Realm First! Level 80 Pandaren',
         desc='First pandaren of the Horde on the realm to achieve level 80.'),
]

# Achievement_Criteria: 0 ID, 1 Achievement, 2 Type, 3 Asset, 9-24 Description,
# 30 UI order.
C_ACH, C_TYPE, C_ASSET, C_DESC, C_ORDER = 1, 2, 3, 9, 30
CRITERIA = [
    # realm firsts: reach level 80, as a race (data type 21, S_PLAYER_CLASS_RACE)
    dict(id=13501, template=5234, achievement=1431, order=1, desc=None,
         data=[(21, 0, 20, '')]),
    dict(id=13502, template=5237, achievement=1432, order=1, desc=None,
         data=[(21, 0, 21, '')]),
    # Know Thy Enemy: type 53 HK_RACE, the race is the asset
    dict(id=13503, template=2369, achievement=246, asset=21, order=7, desc='Pandaren', data=[]),
    dict(id=13504, template=2374, achievement=1005, asset=20, order=7, desc='Pandaren', data=[]),
    # Check Your Head (spell 44212 on the target)
    dict(id=13505, template=5772, achievement=291, order=13, desc='Pandaren',
         data=[(11, 0, 0, SCRIPT)]),
    # Shake Your Bunny-Maker (spell 61815 on a female target of level 18+)
    dict(id=13506, template=9124, achievement=2422, order=13, desc='Pandaren',
         data=[(9, 18, 0, ''), (10, 1, 0, ''), (11, 0, 0, SCRIPT)]),
]
LOCALE_MASK = 16712190


def find(d, name):
    for fn in os.listdir(d):
        if fn.lower() == name.lower():
            return os.path.join(d, fn)
    sys.exit(f'{d}: {name} not found')


def columns(sqldir, table):
    text = open(os.path.join(sqldir, table + '.sql'), encoding='utf-8').read()
    m = re.search(r'CREATE TABLE[^(]*`%s`\s*\((.*?)\n\)' % table, text, re.S)
    if not m:
        sys.exit(f'{table}.sql: no CREATE TABLE')
    return re.findall(r'^\s*`([A-Za-z0-9_]+)`', m.group(1), re.M)


def strings_of(cols):
    return {i for i, c in enumerate(cols) if '_Lang_' in c and not c.endswith('_Mask')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dbc', required=True)
    ap.add_argument('--columns', required=True)
    ap.add_argument('--rows', required=True)
    ap.add_argument('--sql', required=True)
    a = ap.parse_args()

    ad, cd = DBC(find(a.dbc, 'Achievement.dbc')), DBC(find(a.dbc, 'Achievement_Criteria.dbc'))
    sid = DBC(find(a.dbc, 'SpellIcon.dbc'))
    A = {ad.ints(r)[0]: list(ad.ints(r)) for r in ad.rows}
    C = {cd.ints(r)[0]: list(cd.ints(r)) for r in cd.rows}
    if ICON_ID in {sid.ints(r)[0] for r in sid.rows}:
        sys.exit(f'SpellIcon {ICON_ID} is taken; move ICON_ID')
    for x in ACHIEVEMENTS:
        if x['id'] in A:
            sys.exit(f'Achievement {x["id"]} is taken; move it')
    for x in CRITERIA:
        if x['id'] in C:
            sys.exit(f'Achievement_Criteria {x["id"]} is taken; move it')
        ach = A.get(x['achievement'])
        if ach is not None and ach[A_MIN]:
            sys.exit(f'achievement {x["achievement"]} needs only some criteria; adding one '
                     f'would not make it required')

    acols = columns(a.columns, 'achievement_dbc')
    ccols = columns(a.columns, 'achievement_criteria_dbc')
    if len(acols) != ad.recsize // 4 or len(ccols) != cd.recsize // 4:
        sys.exit('achievement tables and DBCs do not have the same number of fields')
    astr, cstr = strings_of(acols), strings_of(ccols)

    arows = []
    for x in ACHIEVEMENTS:
        v = list(A[x['template']])
        t = {i: ad.s(v[i]) for i in astr}
        v[0], v[A_FACTION], v[A_ORDER], v[A_ICON] = x['id'], x['faction'] & 0xFFFFFFFF, x['order'], ICON_ID
        for i in astr:
            t[i] = ''
        t[A_TITLE], t[A_DESC] = x['title'], x['desc']
        arows.append((v, t))
    crows = []
    for x in CRITERIA:
        v = list(C[x['template']])
        t = {i: cd.s(v[i]) for i in cstr}
        v[0], v[C_ACH], v[C_ORDER] = x['id'], x['achievement'], x['order']
        if 'asset' in x:
            v[C_ASSET] = x['asset']
        if x['desc'] is not None:
            for i in cstr:
                t[i] = ''
            t[C_DESC] = x['desc']
        crows.append((v, t))

    def write_csv(name, n, rows):
        import csv
        with open(os.path.join(a.rows, name + '.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow([f'c{i}' for i in range(n)])
            for v, t in rows:
                w.writerow([t[i] if i in t else x for i, x in enumerate(v)])
    write_csv('Achievement', len(acols), arows)
    write_csv('Achievement_Criteria', len(ccols), crows)
    write_csv('SpellIcon.achievements', 2, [([ICON_ID, 0], {1: ICON_PATH})])

    def lit(v, t, i):
        if i in t:
            return "'" + t[i].replace('\\', '\\\\').replace("'", "\\'") + "'"
        x = v[i]
        return str(x - (1 << 32) if x >= (1 << 31) else x)

    def values(rows, n):
        return ',\n'.join('  (' + ', '.join(lit(v, t, i) for i in range(n)) + ')' for v, t in rows)

    aids = ', '.join(str(x['id']) for x in ACHIEVEMENTS)
    cids = ', '.join(str(x['id']) for x in CRITERIA)
    data = [(x['id'],) + d for x in CRITERIA for d in x['data']]
    body = f"""-- GENERATED by tools/gen-achievements.py -- do not edit by hand.
--
-- Pandaren in the achievements that name races one by one, and a realm first
-- per faction. The client patch carries the same rows (Achievement.dbc,
-- Achievement_Criteria.dbc); the server decides what completes them.
--
--   1431 / 1432  Realm First! Level 80 Pandaren, Alliance / Horde
--   246 / 1005   Know Thy Enemy: a killing blow on a pandaren of the other faction
--   291          Check Your Head
--   2422         Shake Your Bunny-Maker (female, level 18+)
--
-- Check Your Head and Shake Your Bunny-Maker check the target's race with a
-- data row that takes one race. Pandaren are two race ids, so their criteria
-- use the script {SCRIPT} (src/), which takes 20 or 21.
--
-- All four existing achievements require every criterion (minimum criteria
-- 0), so a new criterion is required without touching the achievement. A
-- player who has already completed one keeps it.

DELETE FROM `achievement_dbc` WHERE `ID` IN ({aids});
INSERT INTO `achievement_dbc` (`{'`, `'.join(acols)}`) VALUES
{values(arows, len(acols))};

DELETE FROM `achievement_criteria_dbc` WHERE `ID` IN ({cids});
INSERT INTO `achievement_criteria_dbc` (`{'`, `'.join(ccols)}`) VALUES
{values(crows, len(ccols))};

DELETE FROM `achievement_criteria_data` WHERE `criteria_id` IN ({cids});
INSERT INTO `achievement_criteria_data` (`criteria_id`, `type`, `value1`, `value2`, `ScriptName`) VALUES
""" + ',\n'.join("  (%d, %d, %d, %d, '%s')" % d for d in data) + """;

-- Check, after a restart: no `achievement_criteria_data` or "achievement"
-- errors for these IDs in Server.log, and in game the achievements list the
-- Pandaren criterion.
"""
    open(a.sql, 'w', encoding='utf-8', newline='\n').write(body)
    print(f'{a.sql}: {len(arows)} achievements, {len(crows)} criteria, {len(data)} data rows')


if __name__ == '__main__':
    main()
