-- Pandaren: the same weapon skills on both factions.
--
-- 03 mirrors night elf and troll. Stock 3.3.5a data gives weapon skills per
-- class, so the two halves of the race already match and these rows change
-- nothing. With race-gated weapon skills (mod-individual-progression restores
-- the pre-3.3 rules), the two source races differ, and so would the two
-- halves of ONE race:
--
--   class    Alliance (20, from night elf)  Horde (21, from troll)
--   Warrior  43 Swords, 54 Maces            44 Axes, 176 Thrown
--   Hunter   --                             44 Axes
--
-- Language and racials must differ by faction, weapon skills should not.
-- The fix is the UNION, not a choice between the two: any other rule takes
-- something from one side.
--
-- Only Warrior and Hunter are affected; Rogue, Priest, Shaman and Mage have
-- identical sets on the two source races.
--
-- TRAP: Player::LearnDefaultSkill returns WITHOUT logging when there is no
-- SkillRaceClassInfo row for (skill, race, class). A row here without one
-- would look right in the database and do nothing in game. All five
-- combinations are allowed in SkillRaceClassInfo.dbc + `skillraceclassinfo_dbc`
-- -- night elves and trolls may already learn them from a Weapon Master.
--
-- NEW CHARACTERS ONLY. playercreateinfo_skills is read by
-- LearnDefaultSkills() inside Player::Create().
--
-- raceMask 524288 = race 20, 1048576 = race 21, 1572864 = both.
-- classMask 1 = Warrior, 4 = Hunter.

DELETE FROM `playercreateinfo_skills`
  WHERE `raceMask` IN (524288, 1048576, 1572864)
    AND `classMask` IN (1, 4)
    AND `skill` IN (43, 44, 54, 176);

INSERT INTO `playercreateinfo_skills` (`raceMask`, `classMask`, `skill`, `comment`) VALUES
-- Warrior: both races get both source races' sets.
  (1572864, 1, 43,  'Swords - Pandaren'),
  (1572864, 1, 44,  'Axes - Pandaren'),
  (1572864, 1, 54,  'Maces - Pandaren'),
  (1572864, 1, 176, 'Thrown - Pandaren'),
-- Hunter: only axes differed.
  (1572864, 4, 44,  'Axes - Pandaren');

-- Check. Both must give the same set, and neither may be empty:
--
--   SELECT GROUP_CONCAT(DISTINCT skill ORDER BY skill)
--     FROM playercreateinfo_skills
--    WHERE (raceMask = 0 OR raceMask & 524288) AND (classMask = 0 OR classMask & 1)
--      AND skill IN (43,44,45,46,54,55,136,160,162,172,173,176,226,228,229,413,414,415,433,473);
--   -- and the same with 1048576.
