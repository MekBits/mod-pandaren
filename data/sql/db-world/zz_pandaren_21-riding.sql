-- Pandaren: a riding trainer and a mount vendor.
--
-- The ten race riding trainers and race mount vendors talk to their own race
-- or to anyone exalted with the city. The trainer table does not gate them
-- (trainer.Requirement is 0 for all mount trainers); the gossip conditions
-- do, as type 16 (CONDITION_RACE) with ElseGroup 1 = exalted:
--
--   14 <menu> <text>   which greeting the NPC shows
--   15 <menu> 0        the "train" / "buy" option
--
-- No race was pandaren, so a pandaren got neither option anywhere until
-- exalted, and Apprentice Riding was out of reach.
--
-- THE CITY FOLLOWS FROM 05 AND 11: the race's home city is where it starts at
-- 4000 reputation and the city it represents in the Argent Tournament.
--   race 20  ->  Darnassus          Jartsam (4753, menu 4019),
--                                   Lelanai (4730, menu 3185), sabers
--   race 21  ->  Darkspear Trolls   Xar'Ti (7953, menu 4022),
--                                   Zjolnir (7952, menu 3162), raptors
-- Both Darkspear NPCs are in Sen'jin Village, Durotar, next to the Valley of
-- Trials.
--
-- The source race's mask gets the pandaren bit in every race condition of the
-- four menus. In the vendors' NegativeCondition rows ("not a night elf"),
-- that keeps the refusal text from the pandaren. The trainers' refusal masks
-- ("every stock race but night elf") are in 20.
--
-- `|` is idempotent.

UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 524288
  WHERE `ConditionTypeOrReference` = 16 AND (`ConditionValue1` & 1791) = 8
    AND `SourceTypeOrReferenceId` IN (14, 15) AND `SourceGroup` IN (4019, 3185);

UPDATE `conditions` SET `ConditionValue1` = `ConditionValue1` | 1048576
  WHERE `ConditionTypeOrReference` = 16 AND (`ConditionValue1` & 1791) = 128
    AND `SourceTypeOrReferenceId` IN (14, 15) AND `SourceGroup` IN (4022, 3162);

-- --------------------------------------------------------------------------
-- Check. Each must give 3 rows for the vendor (two texts, one option) and
-- 2 for the trainer (one text, one option):
--
--   SELECT SourceTypeOrReferenceId, SourceGroup, SourceEntry, ConditionValue1, NegativeCondition
--     FROM conditions WHERE ConditionTypeOrReference = 16 AND SourceGroup IN (4019, 3185, 4022, 3162)
--      AND (ConditionValue1 & 1791) IN (8, 128);
--   -- 4019, 3185: 524296   4022, 3162: 1048704
--
-- In game: a pandaren at riding level talks to its trainer, gets the "train"
-- option and learns Apprentice Riding; its vendor sells; every other race
-- trainer gives it the refusal text.
