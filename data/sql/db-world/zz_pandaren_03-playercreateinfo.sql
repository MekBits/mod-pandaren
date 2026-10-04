-- Pandaren: race/class matrix, start position, action bar and start skills.
--
-- Classes: Warrior (1), Hunter (3), Rogue (4), Priest (5), Shaman (7), Mage (8).
-- MoP's own pandaren list minus Monk. No Paladin, Warlock, Druid or Death
-- Knight, as in MoP.
--
-- Twelve combinations. playercreateinfo decides what the server ACCEPTS; the
-- client's CharBaseInfo.dbc (in the client patch) decides what character
-- creation OFFERS. They fail separately and silently: offered but not here is
-- "Character creation failed", here but not offered cannot be chosen.
--
-- Start zones:
--   Alliance -> Shadowglen, Teldrassil (night elf), map 1 zone 141
--   Horde    -> Valley of Trials, Durotar (orc), map 1 zone 14
-- Valley of Trials thereby hosts orcs, trolls and pandaren on one spawn point.

DELETE FROM `playercreateinfo` WHERE `race` IN (20, 21);

INSERT INTO `playercreateinfo`
  (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`)
VALUES
  -- Alliance, Shadowglen: the night elf coordinates
  (20, 1, 1, 141, 10311.3, 832.463, 1326.41, 5.69632),
  (20, 3, 1, 141, 10311.3, 832.463, 1326.41, 5.69632),
  (20, 4, 1, 141, 10311.3, 832.463, 1326.41, 5.69632),
  (20, 5, 1, 141, 10311.3, 832.463, 1326.41, 5.69632),
  (20, 7, 1, 141, 10311.3, 832.463, 1326.41, 5.69632),
  (20, 8, 1, 141, 10311.3, 832.463, 1326.41, 5.69632),
  -- Horde, Valley of Trials: the orc and troll coordinates
  (21, 1, 1,  14, -618.518, -4251.67, 38.718, 0),
  (21, 3, 1,  14, -618.518, -4251.67, 38.718, 0),
  (21, 4, 1,  14, -618.518, -4251.67, 38.718, 0),
  (21, 5, 1,  14, -618.518, -4251.67, 38.718, 0),
  (21, 7, 1,  14, -618.518, -4251.67, 38.718, 0),
  (21, 8, 1,  14, -618.518, -4251.67, 38.718, 0);

-- --------------------------------------------------------------------------
-- The action bar is cloned from the source race:
--   Horde: TROLL (8), not orc. Trolls have all six classes and stand on the
--     orc coordinates in Valley of Trials; orcs have no Priest.
--   Alliance: NIGHT ELF (4) for Warrior/Hunter/Rogue/Priest, DRAENEI (11) for
--     Shaman and Mage.
--
-- The bar must come from the same race as the start outfit in 07, or the
-- buttons do not match the bags. Night elves have no shaman or mage of their
-- own (modules that add them use generic rows without the food and drink
-- buttons), while the draenei kit contains 4540 Tough Hunk of Bread and 159
-- Refreshing Spring Water.
DELETE FROM `playercreateinfo_action` WHERE `race` IN (20, 21);

INSERT INTO `playercreateinfo_action` (`race`, `class`, `button`, `action`, `type`)
SELECT 20, `class`, `button`, `action`, `type`
  FROM `playercreateinfo_action` WHERE `race` = 4  AND `class` IN (1,3,4,5);

INSERT INTO `playercreateinfo_action` (`race`, `class`, `button`, `action`, `type`)
SELECT 20, `class`, `button`, `action`, `type`
  FROM `playercreateinfo_action` WHERE `race` = 11 AND `class` IN (7,8);

INSERT INTO `playercreateinfo_action` (`race`, `class`, `button`, `action`, `type`)
SELECT 21, `class`, `button`, `action`, `type`
  FROM `playercreateinfo_action` WHERE `race` = 8  AND `class` IN (1,3,4,5,7,8);

-- Replace the source race's own racial on the bar. A pandaren does not have
-- 58984 Shadowmeld, 26297 Berserking, 20544 or Gift of the Naaru -- 28880 and
-- the class versions 59542-59548 the draenei bars carry -- so the button would
-- be dead on every new character. Quaking Palm (80004) is the only active
-- pandaren racial; the other three are passive.
--
-- The spell is created in 08, after this file. That is fine:
-- `action` is a plain integer without a foreign key, and the server only
-- looks it up at character creation.
UPDATE `playercreateinfo_action` SET `action` = 80004
  WHERE `race` IN (20, 21) AND `type` = 0
    AND `action` IN (58984, 26297, 20544, 28880, 59542, 59543, 59544, 59545, 59547, 59548);

-- 26972 Summon Panda Cub is on the troll rogue bar: a vanity pet no character
-- is given, so the button would be dead.
DELETE FROM `playercreateinfo_action`
  WHERE `race` IN (20, 21) AND `type` = 0 AND `action` = 26972;

-- Check -- both must return ZERO rows:
--   SELECT COUNT(*) FROM playercreateinfo_action
--    WHERE race IN (20, 21) AND action IN (58984, 26297, 20544, 26972,
--                                          28880, 59542, 59543, 59544, 59545, 59547, 59548);
--   SELECT class, COUNT(*) FROM playercreateinfo_action
--    WHERE race IN (20, 21) AND action = 80004 GROUP BY race, class HAVING COUNT(*) > 1;
--
-- A combination whose source race has no racial on its bar ends up WITHOUT an
-- 80004 button (the racial is still in the spellbook). Test for "at most
-- one", not "exactly one".

-- --------------------------------------------------------------------------
-- Start skills: mirror the source race.
--
-- playercreateinfo_skills can gate weapon skills by race (stock 3.3.5a data
-- does not, mod-individual-progression does). A race whose start outfit lacks
-- the matching proficiency gets a weapon it cannot use, with no error. The
-- faction language comes the same way: the Alliance mask carries skill 98
-- (Common), the Horde mask 109 (Orcish).
--
-- The mirror must NOT be blind. The source races' race-gated rows contain:
--   113 SKILL_LANG_DARNASSIAN  +  126 SKILL_RACIAL_NIGHT_ELF   (night elf)
--   315 SKILL_LANG_TROLL       +  733 SKILL_RACIAL_TROLL       (troll)
-- SKILL_RACIAL_* is the racial skill line that hands out the racials (as
-- skill 789 "Racial - Worgen" does for worgen). Mirroring it would give
-- Alliance pandaren SHADOWMELD and Horde pandaren BERSERKING.
--
-- Only rows for all classes (classMask 0) or at least one of the six
-- pandaren classes (221 = 1|4|8|16|64|128). Without that limit a row for a
-- class pandaren cannot be (a warlock-only row naming trolls, say) gets the
-- bit too. That does nothing in game, but the updater reruns this file on
-- every change, and it must not touch rows other modules own.
--
-- Bits: race 20 -> 1<<19 = 524288, race 21 -> 1<<20 = 1048576.
-- `|` is idempotent, so the file can be rerun safely.
UPDATE `playercreateinfo_skills` SET `raceMask` = `raceMask` | 524288
  WHERE (`raceMask` &   8) <> 0 AND `skill` NOT IN (113, 126)
    AND (`classMask` = 0 OR (`classMask` & 221) <> 0);
UPDATE `playercreateinfo_skills` SET `raceMask` = `raceMask` | 1048576
  WHERE (`raceMask` & 128) <> 0 AND `skill` NOT IN (315, 733)
    AND (`classMask` = 0 OR (`classMask` & 221) <> 0);

-- Check. From this mirror race 20 has skill 98 (Common) and race 21 skill 109
-- (Orcish), plus whatever race-gated weapon skills the source races have
-- (12 then gives both races the union). NONE of 113, 126, 315, 733 in either.
--
--   SELECT raceMask, classMask, skill FROM playercreateinfo_skills
--    WHERE (raceMask & 524288) <> 0 ORDER BY skill;
--   SELECT raceMask, classMask, skill FROM playercreateinfo_skills
--    WHERE (raceMask & 1048576) <> 0 ORDER BY skill;
--   SELECT 'LEAK', skill FROM playercreateinfo_skills
--    WHERE (raceMask & 1572864) <> 0 AND skill IN (113,126,315,733);
--
-- The pandaren racials and their skill line 791 come from
-- zz_pandaren_08-racial-spells.sql.
