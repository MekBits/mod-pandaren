-- Pandaren: race conditions that pick one version per race.
--
-- Some content has a version for each of the ten races and picks one with a
-- type 16 condition (CONDITION_RACE) or a spell_area race mask. A pandaren
-- matches none and gets nothing. It takes its source race's version, as in
-- 03, 11 and 21: night elf for race 20, troll for race 21.
--
--   17 0 24108 / 24101   Hallow's End, "Honoring a Hero" (8149, 8150): the
--                        tribute item's script (spell_scripts 24194, 24195)
--                        casts every race's tribute spell, and the condition
--                        lets one through. Without it the quest cannot be
--                        completed.
--   23 33653 46744/46759 Argent Tournament, Darnassus quartermaster: the
--                        Swift Moonsaber for night elves, and the
--                        NegativeCondition copy for everyone else, which
--                        requires exalted with Darnassus
--   23 33554 46743/46760 the same at Sen'jin's quartermaster (Swift Purple
--                        Raptor, exalted with Darkspear Trolls)
--   spell_area 35482, 35483
--                        the Caverns of Time's human illusion for night elves
--                        and draenei (1032), in Old Hillsbrad and the Culling
--                        of Stratholme. 20 gives pandaren-H the Horde one.
--
-- Not changed: menu 7311 (Paelarin, the Silvermoon bowyer who will not trade
-- with trolls) is about trolls, not about whoever mirrors their data; menu
-- 10416 (an Argent Tournament vendor option, troll or achievement) is not
-- used by any creature.
--
-- `|` is idempotent.

UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 524288
  WHERE `ConditionTypeOrReference` = 16 AND (`ConditionValue1` & 1791) = 8
    AND ((`SourceTypeOrReferenceId` = 17 AND `SourceGroup` = 0 AND `SourceEntry` = 24108)
      OR (`SourceTypeOrReferenceId` = 23 AND `SourceGroup` = 33653 AND `SourceEntry` IN (46744, 46759)));

UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 1048576
  WHERE `ConditionTypeOrReference` = 16 AND (`ConditionValue1` & 1791) = 128
    AND ((`SourceTypeOrReferenceId` = 17 AND `SourceGroup` = 0 AND `SourceEntry` = 24101)
      OR (`SourceTypeOrReferenceId` = 23 AND `SourceGroup` = 33554 AND `SourceEntry` IN (46743, 46760)));

UPDATE `spell_area` SET `racemask` = `racemask` | 524288
  WHERE `spell` IN (35482, 35483) AND (`racemask` & 1791) = 1032;

-- --------------------------------------------------------------------------
-- Check:
--
--   SELECT SourceTypeOrReferenceId, SourceGroup, SourceEntry, ConditionValue1, NegativeCondition
--     FROM conditions WHERE ConditionTypeOrReference = 16 AND SourceTypeOrReferenceId IN (17, 23)
--      AND (ConditionValue1 & 1791) IN (8, 128) AND (ConditionValue1 & 1572864) <> 0;
--   -- 6 rows: 24108, 46744, 46759 with race 20; 24101, 46743, 46760 with race 21
--
--   SELECT spell, area, racemask FROM spell_area WHERE spell IN (35480, 35481, 35482, 35483);
--   -- 35480/35481 have race 21 (from 20), 35482/35483 race 20
--
-- In game: a pandaren on Hallow's End places the tribute at Uther's Tomb or
-- Grom's monument, and the quest completes.
