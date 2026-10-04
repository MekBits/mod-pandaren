-- Pandaren: access to the Argent Tournament.
--
-- The tournament has 191 quests under QuestSortID -241. Most are faction-wide
-- (the Alliance or Horde mask) and opened by 04. The valiant quests are gated
-- by race, one city per race, and they are the entry to the whole chain. The
-- four that matter here:
--
--   13689  A Valiant Of Darnassus   mask    8  (night elf)
--   13735  A Champion Rises         mask    8
--   13693  A Valiant Of Sen'jin     mask  128  (troll)
--   13737  A Champion Rises         mask  128
--
-- Without them a pandaren can take "The Aspirant's Challenge" (faction-wide)
-- and go no further: no city takes it as valiant, so no champion, no city
-- mounts, no tabard and none of the dailies behind them.
--
-- THE CITY FOLLOWS FROM 05. A valiant represents its home city, and the home
-- city is the faction where the race starts at 4000 instead of 3100:
--   race 20  ->  69  Darnassus         4000   (other Alliance cities 3000-3100)
--   race 21  -> 530  Darkspear Trolls  4000   (Orgrimmar and Thunder Bluff 3100)
-- That matches the rest of the port: Horde pandaren mirror the troll
-- throughout, so Sen'jin, not Orgrimmar, even though they share the orc
-- coordinates.
--
-- `|` is idempotent.

UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 524288
  WHERE `ID` IN (13689, 13735);      -- Darnassus: valiant + champion

UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 1048576
  WHERE `ID` IN (13693, 13737);      -- Sen'jin: valiant + champion

-- --------------------------------------------------------------------------
-- Check.
--
-- Negative, must return ZERO rows -- no tournament quest may be open to night
-- elf or troll and closed to the pandaren that mirrors it:
--
--   SELECT ID, AllowableRaces, LogTitle FROM quest_template
--    WHERE QuestSortID = -241 AND AllowableRaces > 0
--      AND ((AllowableRaces &   8) <> 0 AND (AllowableRaces & 524288) = 0
--        OR (AllowableRaces & 128) <> 0 AND (AllowableRaces & 1048576) = 0);
--
-- Positive:
--
--   SELECT ID, AllowableRaces FROM quest_template WHERE ID IN (13689,13693,13735,13737);
--     13689 -> 524296      (8 | 524288)
--     13693 -> 1048704     (128 | 1048576)
--     13735 -> 524296
--     13737 -> 1048704
--
-- None of the four has a PrevQuest, ExclusiveGroup or skill requirement
-- beyond its predecessor in the chain (13679/13680 and 13725/13727), which
-- are faction-wide and already open. AllowableRaces is the only gate.
--
-- In game: a level 80 pandaren must be able to take "The Aspirant's
-- Challenge", then its city's valiant quest, and finally become champion.
