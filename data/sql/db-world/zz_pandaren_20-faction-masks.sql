-- Pandaren: faction race masks outside quest_template and item_template.
--
-- 04 opens "all races", "all Alliance" and "all Horde" masks in quests and
-- items. Three more tables gate on the same masks:
--
--   spell_area         phases and detection auras: the Battle for the
--                      Undercity (59062, 60815, 60877, 60943), Icecrown's quest
--                      phases (30181, 49416, 49417, 59073, 59087), the Ebon
--                      Hold's Chapter V and the return to the capital (58354,
--                      58530, 58551), the Pit of Saron approach's faction aura
--                      (70056, 70057), the Caverns of Time's human illusion
--                      for Horde (35480, 35481) and an Alcaz Island survey
--                      credit (42316)
--   conditions         type 16 (CONDITION_RACE): gossip and SmartAI that pick
--                      the Alliance or Horde branch ("Honest" Max's flying
--                      mounts, the Injured Rainspeaker Oracle)
--   mail_level_reward  the level 71 letter about cold weather flying
--
-- Without the bits a pandaren falls through both branches: no phase, no
-- gossip option, no letter, and nothing logs it.
--
-- The rule is 04's, on the ten stock races:
--   (mask & 1101) = 1101  ->  "all Alliance"  -> race 20 (524288)
--   (mask &  690) =  690  ->  "all Horde"     -> race 21 (1048576)
-- A mask with all ten is "all races" and gets both.
--
-- Every other race mask in acore_world is a race id, a pandaren row of its
-- own (01-12), or not read (playercreateinfo_spell_custom with
-- PlayerStart.CustomSpells = 0):
--   faction_dbc                 05
--   skilllineability_dbc,
--   skillraceclassinfo_dbc      04, 09
--   playercreateinfo_skills     03, 12
--   playercreateinfo_cast_spell only raceMask 0
--   talenttab_dbc               only RaceMask 0
--
-- Every expression uses `|` and tests bits, never whole values, so it is
-- idempotent and gives the same result before or after mod-worgoblin's
-- matching rules for goblin and worgen. ConditionValue1 and racemask are part
-- of their tables' primary keys; no table has the target row twice.

UPDATE `spell_area` SET `racemask` = `racemask` | 524288
  WHERE `racemask` > 0 AND (`racemask` & 1101) = 1101;
UPDATE `spell_area` SET `racemask` = `racemask` | 1048576
  WHERE `racemask` > 0 AND (`racemask` & 690) = 690;

UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 524288
  WHERE `ConditionTypeOrReference` = 16 AND (`ConditionValue1` & 1101) = 1101;
UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 1048576
  WHERE `ConditionTypeOrReference` = 16 AND (`ConditionValue1` & 690) = 690;

UPDATE `mail_level_reward` SET `raceMask` = `raceMask` | 524288
  WHERE (`raceMask` & 1101) = 1101;
UPDATE `mail_level_reward` SET `raceMask` = `raceMask` | 1048576
  WHERE (`raceMask` & 690) = 690;

-- --------------------------------------------------------------------------
-- "Every stock race but one".
--
-- The ten race riding trainers show a refusal text to everyone who is not
-- their race (14/4014-4022, 8275, 8553: 1787 = all but dwarf, 1783 = all but
-- night elf, ...). Pandaren are in none of those masks and got no text at
-- all. A pandaren is "not dwarf" like everyone else, except where the missing
-- race is its source race: pandaren-A count as night elf (Jartsam, 21), and
-- pandaren-H as troll (Xar'Ti).
--   all but one, and the one is not night elf (8)  -> race 20
--   all but one, and the one is not troll (128)    -> race 21
-- The faction rule above has already given each mask the other faction's
-- bit; this adds the same-faction bit.

UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 524288
  WHERE `ConditionTypeOrReference` = 16
    AND BIT_COUNT(`ConditionValue1` & 1791) = 9 AND (`ConditionValue1` & 8) <> 0;
UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 1048576
  WHERE `ConditionTypeOrReference` = 16
    AND BIT_COUNT(`ConditionValue1` & 1791) = 9 AND (`ConditionValue1` & 128) <> 0;

-- --------------------------------------------------------------------------
-- The Northrend ghost flyer.
--
-- A dead player in Icecrown, the Storm Peaks, Wintergrasp and Wyrmrest Temple
-- (areas 210, 67, 4197, 4161) flies as a ghost through spell_area: 55164 Swift
-- Spectral Gryphon for "all but night elf" (65527 = races 1-16 without 4) and
-- 55173 Swift Flying Wisp for night elves (8), whose ghost is a wisp.
-- The wisp ghost is not data: Player::BuildPlayerRepop casts 20584 only for
-- RACE_NIGHTELF, so a pandaren-A ghost is a regular ghost. Both pandaren get
-- the gryphon, and the wisp stays night elf only.

UPDATE `spell_area` SET `racemask` = `racemask` | 1572864
  WHERE `spell` = 55164 AND `racemask` > 0;

-- --------------------------------------------------------------------------
-- Check. Must return 0 rows:
--
--   SELECT 'spell_area', spell, area, racemask FROM spell_area
--    WHERE racemask > 0 AND (((racemask & 1101) = 1101 AND (racemask & 524288) = 0)
--       OR ((racemask & 690) = 690 AND (racemask & 1048576) = 0))
--   UNION ALL
--   SELECT 'conditions', SourceTypeOrReferenceId, SourceGroup, ConditionValue1 FROM conditions
--    WHERE ConditionTypeOrReference = 16
--      AND (((ConditionValue1 & 1101) = 1101 AND (ConditionValue1 & 524288) = 0)
--        OR ((ConditionValue1 & 690) = 690 AND (ConditionValue1 & 1048576) = 0))
--   UNION ALL
--   SELECT 'mail_level_reward', level, 0, raceMask FROM mail_level_reward
--    WHERE ((raceMask & 1101) = 1101 AND (raceMask & 524288) = 0)
--       OR ((raceMask & 690) = 690 AND (raceMask & 1048576) = 0);
--
--   SELECT DISTINCT racemask FROM spell_area WHERE spell = 55164;  -- 1638391
