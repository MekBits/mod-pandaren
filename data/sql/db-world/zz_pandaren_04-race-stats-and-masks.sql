-- Pandaren: stat modifiers and every race mask that would otherwise lock them out.

-- --------------------------------------------------------------------------
-- player_race_stats: modifiers on top of the class base stats.
--
-- Every existing race sums to ZERO (night elf -4/+4/0/0/0, orc +3/-3/+1/-3/+2,
-- troll +1/+2/0/-4/+1, draenei +1/-3/0/0/+2), and pandaren follow the same
-- budget. The split is a design choice, not ported data: MoP's numbers
-- belong to a different stat scale. Both factions get the SAME values.
DELETE FROM `player_race_stats` WHERE `Race` IN (20, 21);
INSERT INTO `player_race_stats` (`Race`, `Strength`, `Agility`, `Stamina`, `Intellect`, `Spirit`)
VALUES
  (20, 0, -1, 2, -2, 1),
  (21, 0, -1, 2, -2, 1);

-- --------------------------------------------------------------------------
-- Race masks.
--
-- Pandaren are bits 19 and 20, outside every "all races" value in WotLK data
-- (32767 is races 1-15). Without this file a pandaren cannot take thousands
-- of quests, use thousands of items or learn dozens of skill lines -- all
-- silently.
--
--   Race 20 -> 1<<19 = 524288
--   Race 21 -> 1<<20 = 1048576
--   Both    =          1572864
--
-- Quests and items. The rule looks only at the ten stock races (1791 =
-- races 1-8, 10, 11), so it reads the same with or without a module that adds
-- worgen (12) and goblin (9):
--   (mask & 1791) = 1791  ->  "all races"     -> both bits
--   (mask & 1791) = 1101  ->  "all Alliance"  -> race 20   (1101, 3149, ...)
--   (mask & 1791) =  690  ->  "all Horde"     -> race 21   (690, 946, ...)
-- A mask containing all ten means "all", whether it is written 1791, 2047,
-- 32767 or 2147483647. Masks that leave out one of the ten ("all except
-- night elf", 65527) are not matched. 0 and -1 mean "no restriction" and are
-- not touched.
--
-- Every expression uses `|` and is idempotent.

-- Quests.
UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 1572864
  WHERE `AllowableRaces` > 0 AND (`AllowableRaces` & 1791) = 1791;
UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 524288
  WHERE `AllowableRaces` > 0 AND (`AllowableRaces` & 1791) = 1101;
UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 1048576
  WHERE `AllowableRaces` > 0 AND (`AllowableRaces` & 1791) = 690;

-- Items.
UPDATE `item_template` SET `AllowableRace` = `AllowableRace` | 1572864
  WHERE `AllowableRace` > 0 AND (`AllowableRace` & 1791) = 1791;
UPDATE `item_template` SET `AllowableRace` = `AllowableRace` | 524288
  WHERE `AllowableRace` > 0 AND (`AllowableRace` & 1791) = 1101;
UPDATE `item_template` SET `AllowableRace` = `AllowableRace` | 1048576
  WHERE `AllowableRace` > 0 AND (`AllowableRace` & 1791) = 690;

-- --------------------------------------------------------------------------
-- The two skill tables.
--
-- `skilllineability_dbc` and `skillraceclassinfo_dbc` are OVERRIDE tables:
-- they hold only the rows someone has already overridden. An UPDATE reaches
-- those rows and no others; the rest live in the .dbc FILE and can only be
-- inserted. zz_pandaren_09 inserts the rest; these UPDATEs catch rows other
-- modules put in the tables. Both use the same rule and converge in either
-- order.
--
-- The rule mirrors the source race, per class, instead of looking for "all
-- races": night elf for race 20 (draenei for shaman and mage, which night
-- elves cannot be), troll for race 21. A mask naming a single race is that
-- race's own racial or language line and is left alone (BIT_COUNT > 1).
-- Class bits: 29 = warrior, hunter, rogue, priest; 192 = shaman, mage.

UPDATE `skilllineability_dbc` SET `RaceMask` = `RaceMask` | 524288
  WHERE `RaceMask` > 0 AND BIT_COUNT(`RaceMask` & 4095) > 1
    AND ((`RaceMask` & 8) <> 0 AND (`ClassMask` = 0 OR (`ClassMask` & 29) <> 0)
      OR (`RaceMask` & 1024) <> 0 AND (`ClassMask` & 192) <> 0);
UPDATE `skilllineability_dbc` SET `RaceMask` = `RaceMask` | 1048576
  WHERE `RaceMask` > 0 AND BIT_COUNT(`RaceMask` & 4095) > 1 AND (`RaceMask` & 128) <> 0;

UPDATE `skillraceclassinfo_dbc` SET `RaceMask` = `RaceMask` | 524288
  WHERE `RaceMask` > 0 AND BIT_COUNT(`RaceMask` & 4095) > 1
    AND ((`RaceMask` & 8) <> 0 AND (`ClassMask` = 0 OR (`ClassMask` & 29) <> 0)
      OR (`RaceMask` & 1024) <> 0 AND (`ClassMask` & 192) <> 0);
UPDATE `skillraceclassinfo_dbc` SET `RaceMask` = `RaceMask` | 1048576
  WHERE `RaceMask` > 0 AND BIT_COUNT(`RaceMask` & 4095) > 1 AND (`RaceMask` & 128) <> 0;

-- --------------------------------------------------------------------------
-- Check. None of these may return more than 0 afterwards:
--
--   SELECT COUNT(*) FROM quest_template WHERE AllowableRaces > 0
--      AND (AllowableRaces & 1791) IN (1791, 1101, 690)
--      AND (AllowableRaces & 1572864) = 0;
--   SELECT COUNT(*) FROM item_template WHERE AllowableRace > 0
--      AND (AllowableRace & 1791) IN (1791, 1101, 690)
--      AND (AllowableRace & 1572864) = 0;
--
-- And a positive test -- both must give thousands:
--   SELECT COUNT(*) FROM quest_template WHERE (AllowableRaces & 524288) <> 0;
--   SELECT COUNT(*) FROM quest_template WHERE (AllowableRaces & 1048576) <> 0;
--
-- Faction base reputation (BaseRepRaceMask in faction_dbc) is in
-- zz_pandaren_05-faction-reputation.sql.
