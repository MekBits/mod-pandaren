-- Pandaren shaman: totem models.
--
-- `player_totem_model` has 4 rows per race (one per totem type) for races
-- 1-11; worgen have no Shaman. Pandaren have Shaman on both sides, so both
-- races need their four. Without them the shaman's totems have no model --
-- nothing fails at startup, it only shows when a totem is dropped.
--
-- The models mirror the source race, like everything else in this module:
--   race 20 <- night elf (4): 30754 / 30753 / 30755 / 30736
--   race 21 <- troll (8):     30762 / 30761 / 30763 / 30760
-- The night elf set is shared by human, dwarf, night elf and gnome; trolls
-- have their own, and troll is the Horde source race throughout.

DELETE FROM `player_totem_model` WHERE `RaceID` IN (20, 21);

INSERT INTO `player_totem_model` (`TotemID`, `RaceID`, `ModelID`) VALUES
  (1, 20, 30754), (2, 20, 30753), (3, 20, 30755), (4, 20, 30736),
  (1, 21, 30762), (2, 21, 30761), (3, 21, 30763), (4, 21, 30760);

-- Check -- 4 rows per race:
--   SELECT RaceID, COUNT(*) FROM player_totem_model
--    WHERE RaceID IN (20, 21) GROUP BY RaceID;
