# mod-pandaren

An [AzerothCore](https://www.azerothcore.org) module that makes pandaren a
playable race in 3.3.5a: race **20** on the Alliance and race **21** on the
Horde, one people with the same models and options, each locked to its faction.
The models, textures, customization options and character-select scene are
Mists of Pandaria 5.4.8's own, converted to the 3.3.5a formats.

| | |
|---|---|
| Classes | Warrior, Hunter, Rogue, Priest, Shaman, Mage (MoP's list without Monk) |
| Start | Alliance: Shadowglen (night elf). Horde: Valley of Trials (orc and troll) |
| Racials | Quaking Palm, Inner Peace, Gourmand, Bouncy, with MoP's own icons (see below) |
| Options | male 14 skin colours, 21 faces, 19 hairstyles, 14 hair colours, 31 beards; female 14/20/10/12 |
| Achievements | Realm First! Level 80 Pandaren for each faction; pandaren in Know Thy Enemy, Check Your Head and Shake Your Bunny-Maker |
| Voice and gear | MoP's own emote, error and combat voices, footsteps and blood; MoP's helmet models and death skeleton |
| Content | Quests, vendors, trainers and phases that have one version per race also work for pandaren (they follow night elf and troll) |

It has two halves, and both are needed:

- **the server module** (this repository): SQL applied by the database updater,
  and one small achievement criteria script. No core patch.
- **the client patch**: `patch-Z.MPQ` from the
  [releases](https://github.com/MekBits/mod-pandaren/releases). Character
  creation reads the races, options and models from the client's own files and
  never asks the server.

## Installation

### Server

```bash
cd azerothcore-wotlk/modules
git clone https://github.com/MekBits/mod-pandaren.git
```

Rebuild, and let the database updater apply `data/sql/db-world/`. The module has
no config file; its only C++ is the criteria script the achievements use (and
the updater only reads SQL from modules that are compiled in).

The core needs the override tables `charsections_dbc` and `emotestextsound_dbc`,
which its update `2026_09_21_05` creates (azerothcore-wotlk and the
mod-playerbots fork both have it). `30` and `31` write to them; on an older core
the updater stops at the first of the two.

On the next start `Server.log` shows 12 more player create definitions than
before (`Loaded 74 Player Create Definitions` on an unmodified database), and
no `not found in DBC` or `wrong teamid`. `chrraces_dbc` is only read at startup.

### Updating from v1.1

Update the server and the client together: build the server, let the updater
run, and give every player the new `patch-Z.MPQ` (it replaces the v1.1 file).

The updater re-runs the files whose content changed (`02`, `08`) and the new
ones (`20`-`23`, `30`, `31`). Nothing is done by hand, and the result is the
same as on a fresh database. Pandaren characters made under v1.1 keep working;
they get the racials the next time they log in. If you built your own patch
with `build_patch.py`, build it again (see
[A client with other patches](#a-client-with-other-patches)).

### Client

1. Copy `patch-Z.MPQ` into the client's `Data/` directory.
2. The client must run a `Wow.exe` with the interface signature check removed:
   the patch changes the character-creation UI (four GlueXML files), and an
   unmodified client refuses with *"Your game/login interface files are
   corrupt"*. Clients that play custom races already have one.

**Install the client patch everywhere before the server SQL runs.** Once
`playercreateinfo` has the rows, pandaren characters (and, with
mod-playerbots, pandaren bots) can exist, and a client without the patch cannot
draw them.

### A client with other patches

The released `patch-Z.MPQ` is built against an unmodified 3.3.5a client. The
client reads `patch-<letter>.MPQ` in letter order and a later letter replaces a
whole file, so if another patch changes the same files (other playable races,
HD character models, a modified character-creation screen), patch-Z would
throw away what it added. Build your own instead, from the files your client
actually loads:

```bash
python3 client/build_patch.py --client "/path/to/WoW" --assets patch-Z.MPQ --out patch-Z.MPQ
```

It reads the 23 DBCs and the glue files from your client (ignoring any patch
with the letter it builds for), adds the pandaren rows, and takes the models,
textures, icons, voices and helmets from the released `patch-Z.MPQ`. It needs
`tools/mpqx` and `tools/mpqpack`; see
[Building the MPQ tools](#building-the-mpq-tools).

If your own patch-Z carries more than pandaren, build on top of it instead:
`--over <your patch-Z.MPQ>` reads it as part of the client and carries every
file in it that the build does not generate, and
`--only Achievement,Achievement_Criteria,SpellIcon,Spell`
(for example) generates just those DBCs and carries the rest unchanged. A
DBC that only works together with others brings them along: asking for
`CreatureDisplayInfoExtra` builds `CharSections`, `CharHairGeosets`,
`CharacterFacialHairStyles` and `CreatureDisplayInfo` too.

## Compatibility

- **mod-worgoblin** (worgen and goblin): tested together, with the SQL in the
  updater's order (worgoblin's first) and this module's run a second time, and
  with a client patch built by `build_patch.py` on a client that has
  worgoblin's patch. The `zz_` prefix runs this module's SQL after every other
  module's, which matters for modules that insert rows without deleting them
  first; a row another module already put in a `*_dbc` table only gets the
  pandaren bits added.
- **Modules that ship their own server DBC files** (ARAC, for instance, which
  opens more race/class combinations): `05`, `07` and `09` are generated from
  an unmodified client's DBC files. Generate them from yours instead (see
  [Generated SQL](#generated-sql)), or the factions, outfits and skill lines
  they list fall back to stock values. `30` is generated the same way from the
  skeleton and ice troll displays your client has.
- **Content masks** (`04`, `20`-`23`): every change is an `|` on the race masks
  that are there, so it adds to whatever another module has done, and running a
  file again changes nothing. A module that adds race-gated quests, vendors or
  phases after this one is not covered: the checks at the end of `20` and `22`
  list what is left.
- **mod-individual-progression**: it rewrites the start outfits and weapon
  skills of the classic races. Generate `07` against the database after it has
  run, and `12` gives both pandaren races the union of the night elf and troll
  weapon skills. The client patch's outfit preview still shows the client's
  own kits; only the preview differs, not what a character gets.
- **mod-playerbots**: bots of races 20 and 21 are created like any other.
  Its faction check uses a fixed list of the original races, so it treats
  race 20 as Horde;
  [mod-playerbots#2875](https://github.com/mod-playerbots/mod-playerbots/pull/2875)
  takes the faction from ChrRaces instead.

## How it works

### Race 20 and 21, not 22 and 23

Character creation in the 3.3.5a client caches one object per race and sex in
a fixed array of 22 × 2, without a bounds check, so a race above 21 writes past
its end and crashes the client. Races 13-19 are used by creatures (naga,
broken, vrykul, ...) through `CreatureDisplayInfoExtra`, so taking one of them
would turn those creatures into pandaren. 20 and 21 (Northrend Skeleton and Ice
Troll) have the fewest rows in use, but they are not free: 30 rows of race 20
(41 displays, skeletons) and all 89 of race 21 (104 displays, the Drakkari of
Zul'Drak and Grizzly Hills) are NPCs. Their baked texture covers only the body;
the client takes hair, beards, skin extras and helmets from the extra row's
race, which would now be pandaren. The patch therefore moves those NPCs to
vrykul (16) and troll (8), whose lookups give what 3.3.5 gave them, and `30`
makes the same change on the server (it reads the race for holiday costumes and
for mounting while transformed). `tools/npcdisplays.py` has the details.

### The server side is SQL overrides

AzerothCore loads each DBC from the file and then from its `*_dbc` table, row by
row, and rows above the file's highest ID extend the table. Everything here is
such an override, so no DBC file on the server is replaced.

| File | What |
|---|---|
| `01` | the two `chrraces_dbc` rows |
| `02` | model and display rows (generated from the client rows) |
| `03` | `playercreateinfo`, action bars and start skills, mirrored from the source races |
| `04` | stat modifiers, and the race masks on quests, items and skill lines |
| `05` | base reputation (generated) |
| `06` | shaman totem models |
| `07` | start outfits (generated) |
| `08` | the racial spells, their skill line and its `SkillRaceClassInfo` row (generated) |
| `09` | the skill-line race masks that live only in the DBC files (generated) |
| `10` | barber chairs (generated from the client rows) |
| `11` | the race-gated Argent Tournament valiant quests |
| `12` | the same weapon skills for both factions |
| `13` | the achievements (generated) |
| `20` | the faction masks outside quests and items: phases and auras (`spell_area`), gossip and AI conditions, a level 71 letter, the Northrend ghost flyer, and the refusal texts of the race riding trainers |
| `21` | the Darnassus and Sen'jin riding trainers and mount vendors (Jartsam, Lelanai, Xar'Ti, Zjolnir) |
| `22` | the quests only night elf, or only orc/troll/goblin, may take: the start zones' "Welcome!", the flight intros, and the copies for every Alliance or Horde race but one |
| `23` | content with one version per race: Hallow's End "Honoring a Hero", the Argent Tournament quartermasters, the Caverns of Time illusion |
| `30` | the skeleton and ice troll NPC displays moved off races 20 and 21 (generated) |
| `31` | the pandaren emote sounds (generated from the client rows) |

Every file can run again: the updater re-runs a whole file whenever it changes.

A few things that fail silently if they are wrong:

- **ChrRaces has two faction fields, and they count differently.**
  `BaseLanguage` (7 = Alliance, 1 = Horde) is what `Player::TeamIdForRace()`
  reads; `Alliance` (0 = Alliance, 1 = Horde) is what `RaceMgr::LoadRaces()`
  reads. Both values are legal either way round, so a mismatch gives no error.
- **Races 20 and 21 are outside every "all races" mask** in WotLK data (32767 is
  races 1-15). Without `04` a pandaren cannot take thousands of quests or use
  thousands of items, and starts Neutral with its own capital without `05`.
- **`Player::LearnDefaultSkill` returns without a word** when a skill has no
  `SkillRaceClassInfo` row for the race and class, and `_LoadSkills` deletes
  such skills at login. Without `09` a pandaren gets none of its racials, no
  language and no mounts.
- **`Player::learnSkillRewardedSpells` skips a `SkillLineAbility` row** whose
  `AcquireMethod` is not 1 or 2, again without a log line. The racial rows in
  `08` have `AcquireMethod` 2 and `MinSkillLineRank` 1, as worgen's have; with
  the column left at 0 a pandaren has no racials.
- **Anything gated to one race, or to a group of races, matches no pandaren.**
  A quest for night elves only, a trainer that talks to its own race, a phase
  for "every Alliance race" all go by race masks, and the stock races are the
  only bits in them. `04` and `20`-`23` give pandaren the bits of their source
  race; the content simply does not appear otherwise, without an error.

### Source races

Wherever a rule has to say what a pandaren may do, it mirrors a race that
exists: night elf for race 20 (draenei for its shamans and mages, which night
elves cannot be), troll for race 21 (trolls have all six classes and stand on
the orc coordinates in Valley of Trials). That covers start outfits, action
bars, start skills, reputation, skill lines and the Argent Tournament (Darnassus
and Sen'jin).

### Racials

| Racial | How |
|---|---|
| Quaking Palm | stun with mechanic *sapped* (breaks on damage), 4 s, 2 min cooldown |
| Inner Peace | **adapted:** +10 % experience from kills. MoP's version doubles rested experience, but the rest pool is capped in `Player::SetRestBonus` with no hook |
| Gourmand | +15 Cooking |
| Bouncy | 10 yards off the fall distance |
| Epicurean | **left out:** "double the benefit of food" has no aura and no hook in 3.3.5a, and a racial that silently does nothing is worse than none |

Each racial is a copy of an existing 3.3.5a spell with named fields changed
(`tools/gen-racial-spells.py`), so attribute and interrupt flags come from a
spell that already works.

### Achievements

The realm firsts by race get **Realm First! Level 80 Pandaren**, one for each
faction (1431 Alliance, 1432 Horde): pandaren are one people, but two race ids
that never meet in a group. The achievements that list races one by one get a
Pandaren criterion: Know Thy Enemy (the other faction's pandaren), Check Your
Head and Shake Your Bunny-Maker. All of them require every criterion, so the new
one is required like the others; a character that has already completed one
keeps it.

Check Your Head and Shake Your Bunny-Maker check the target's race with a data
row that takes one race. Their Pandaren criterion uses the criteria script
`achievement_pandaren_target` (`src/`) instead, which takes either race 20 or 21;
the gender and level rows of Shake Your Bunny-Maker still apply. Holiday
achievements that list fixed race and class combinations (Let It Snow, Fistful
of Love, Turkey Lurkey) are left as Blizzard wrote them.

The icons are MoP's own: `Achievement_Character_Pandaren_Female` for the realm
firsts, `PandarenRacial_*` for the racials.

### Not included

Monk, the neutral starting faction, the Wandering Isle and pandaren NPCs:
none of them exists in a 3.3.5a client.

## Generated SQL

The generators need Python 3 and nothing else. `--dbc` is a directory of the
DBC files your server loads (the client's `DBFilesClient`, extracted).

```bash
# 05: base reputation
python3 tools/gen-faction-dbc.py --dbc <dbc>/Faction.dbc \
    --out data/sql/db-world/zz_pandaren_05-faction-reputation.sql

# 07: start outfits (--overrides: the current charstartoutfit_dbc)
python3 tools/gen-startoutfit.py --dbc <dbc> --overrides charstartoutfit.tsv \
    --columns <azerothcore>/data/sql/base/db_world/charstartoutfit_dbc.sql \
    --out data/sql/db-world/zz_pandaren_07-startoutfit.sql

# 08: racial spells
python3 tools/gen-racial-spells.py --dbc <dbc> \
    --columns <azerothcore>/data/sql/base/db_world/spell_dbc.sql \
    --spell-overrides spell.tsv --rows client/rows \
    --sql data/sql/db-world/zz_pandaren_08-racial-spells.sql

# 09: skill-line masks (--*-overrides: the current override tables)
python3 tools/gen-race-skill-masks.py --dbc <dbc> \
    --srci-overrides srci.tsv --sla-overrides sla.tsv \
    --out data/sql/db-world/zz_pandaren_09-race-skill-masks.sql

# 13: achievements (also writes their client rows)
python3 tools/gen-achievements.py --dbc <client dbc> \
    --columns <azerothcore>/data/sql/base/db_world --rows client/rows \
    --sql data/sql/db-world/zz_pandaren_13-achievements.sql

# 30: the skeleton and ice troll NPC displays (the same function moves them in the client patch)
python3 tools/gen-npc-displays.py --dbc <client dbc> \
    --out data/sql/db-world/zz_pandaren_30-npc-displays.sql

# 02, 10 and 31 come from the client rows, so the two sides cannot drift apart
python3 tools/gen-shared-sql.py --rows client/rows --out data/sql/db-world
```

An override table is dumped with
`mysql -N -e 'SELECT * FROM <table>' acore_world > <file>.tsv`. Left out, the
tables are taken to be empty, as on a fresh database (`spell_dbc` is not:
AzerothCore ships rows of its own). `09` checks its own result: it re-runs
`GetSkillRaceClassInfo`'s lookup and refuses to write a file in which a
pandaren cannot reach a skill line its source race can.

## The client patch

| File | |
|---|---|
| `Character\Pandaren\` | the models and textures |
| `Interface\Glues\Models\UI_Pandaren\` | the character-select scene |
| `DBFilesClient\` | 23 DBCs: the client's own rows plus pandaren's (`client/rows/*.csv`), and the skeleton and ice troll NPCs moved off races 20 and 21 |
| `Interface\Icons\` | MoP's racial and achievement icons |
| `Interface\GlueXML\` | two more race buttons, icons, flavour text and racials |
| `UI-CharacterCreate-Races.blp` | the race icon atlas with the two pandaren icons |
| `Sound\Character\PCPandaren*\` | MoP's pandaren voices: combat, emotes and error lines (WAV, 22 kHz mono, as the 3.3.5a voices) |
| `Item\ObjectComponents\Head\` | MoP's helmet models for pandaren (`_PaM`, `_PaF`) |
| `World\Generic\PassiveDoodads\DeathSkeletons\` | the pandaren death skeletons |

The models are MoP's M2s (version 272) converted to 3.3.5a's version 264. The
pandaren head is drawn on a larger face area than 3.3.5a's fixed character
texture layout allows, so it was re-mapped into the 3.3.5a face area and every
face texture re-rasterized through the new mapping; nothing was dropped from
the option set. The female model has geosets for ten of MoP's seventeen
hairstyles, so those ten are offered.

The character-creation buttons are laid out at runtime from the client's own
faction data rather than from fixed anchors, so the screen works with any
number of races per faction.

### Voices, helmets and the death skeleton

The rows are MoP's: `CreatureSoundData` 4012 and 4080 for the combat sounds,
`EmotesTextSound` 1400-1575 for `/laugh`, `/cheer` and the other emotes,
`VocalUISounds` 1100-1233 for the "Not enough rage" lines, and 144 new
`SoundEntries` for the files, plus `BaseFootprint` and red blood on the model.
Where MoP has no pandaren line for an emote (`/bored`, five error lines) the
tauren's is used, and `/moo` is silent. MoP's `/whistle` uses a file the 3.3.5a
client already has, so none is shipped.

The patch carries pandaren versions of 279 helmet models (`_PaM` and `_PaF`,
converted from MoP's). The seven helmets MoP has no pandaren version of (the
tuskarr and vrykul helmets, the Black Bunny Ears and the Raid Robe hood) are
worn invisibly. A helmet must also say what it hides, so `HelmetGeosetVisData`
gets the pandaren bits (bits 19 and 20 of each field, taken from the bits MoP
sets for its own pandaren).

### Skill lines on the client

The client decides from its own `SkillLineAbility` which spells belong to the
player's race, and which languages the player can speak: a chat line in Common
or Orcish whose row lacks the race's bit is refused by the client itself
("You can't speak that language"). The builder therefore gives the rows that
several races share the pandaren bits by the same rule as `09` (night elf for
race 20, troll for race 21), the way it already did for `SkillRaceClassInfo`.

### Building the MPQ tools

`tools/mpqx.cpp` (read) and `tools/mpqpack.cpp` (write) use
[StormLib](https://github.com/ladislav-zezula/StormLib). On Linux or WSL:

```bash
git clone https://github.com/ladislav-zezula/StormLib.git
cmake -S StormLib -B StormLib/build -DSTORM_USE_BUNDLED_LIBRARIES=ON -DWITH_BUNDLED_LIBTOMMATH=ON
cmake --build StormLib/build -j
for t in mpqx mpqpack; do
    g++ -O2 -std=c++17 -I StormLib/src tools/$t.cpp StormLib/build/libstorm.a -o tools/$t
done
```

## Testing

What catches the silent failures:

- Create a pandaren of each class on both factions, log in and check that the
  start weapon can be used. Bots are no use for this: mod-playerbots equips
  them itself.
- `SELECT skill FROM acore_characters.character_skills WHERE guid = <new pandaren>`
  must contain 791 (the racial line), 98 or 109 (the language), 777 and 778.
  Racials are never in `character_spell`; they are re-derived at every login.
- Count the options in character creation (see the table at the top).
- Say something in chat, use `/laugh` and `/cheer`, and wear a helmet of cloth,
  leather, mail and plate: the voice, the emote sound and the helmet shape are
  the signs that the sound and helmet rows reached the client.
- Look at a Drakkari ice troll in Zul'Drak and at a skeleton NPC from
  Northrend: hair, beards and bones as before, no pandaren fur.
- Visit a barber with each sex, and check you get the style you picked.
- Play in the world as well as in character creation: the world renderer has
  failure modes the creation screen does not.

## Removing it

| What | How |
|---|---|
| Everything | restore a database backup from before the SQL, and delete `patch-Z.MPQ` everywhere |
| The races alone | `DELETE FROM chrraces_dbc WHERE ID IN (20, 21)` and restart. Existing pandaren become unplayable, not deleted |

Do not delete only the client patch while the server SQL is in place: there
would be pandaren that the client cannot draw.

## License

The code and SQL in this repository are licensed under the GNU AGPL v3, see
[LICENSE](LICENSE).

The client patch contains models, textures, sounds and data from *World of
Warcraft: Mists of Pandaria* 5.4.8, © Blizzard Entertainment, converted to the
3.3.5a formats. They are not covered by the license above.
