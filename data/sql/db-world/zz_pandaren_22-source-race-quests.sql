-- Pandaren: the quests their source race gets.
--
-- 04 opens quests for all races and for a whole faction. Quests gated to a
-- group of races inside a faction are left, and the pandaren start zones are
-- full of them: Shadowglen's "Welcome!" is night elf only, the Durotar flight
-- chain orc, troll and goblin.
--
-- The source race decides, as in 03 and 11: night elf for race 20, troll for
-- race 21. Every quest without a class gate (AllowableClasses = 0) that the
-- source race may take and the pandaren may not:
--
--   race 20 (night elf, 8)
--     5842          Welcome! (Shadowglen)
--     6344 6341 6342 6343
--                   Nessa Shadowsong -> The Bounty of Teldrassil -> Flight to
--                   Auberdine -> Return to Nessa (Teldrassil's flight intro)
--     9369          Replenishing the Healing Crystals (Ammen Vale; the copy
--                   for every Alliance race but draenei)
--     14170         The Grateful Dead (Day of the Dead, night elf version)
--     12772 12773   A Desperate Alliance, Darnassus (3.0 Scourge invasion;
--                   no quest giver, opened so the rule has no exceptions)
--
--   race 21 (troll, 128)
--     5843          Welcome! (Valley of Trials)
--     6365 6384 6385 6386
--                   Meats to Orgrimmar -> Ride to Orgrimmar -> Doras the Wind
--                   Rider Master -> Return to the Crossroads
--     9329          The Forsaken (Ghostlands)          } the copies for
--     9811 9812 9813                                   } every Horde race
--                   Friend of the Sin'dorei -> Envoy   } but blood elf
--                   to the Horde -> Meeting the Warchief
--     9498          Falcon Watch (Hellfire Peninsula)  }
--     1049          Compendium of the Fallen (Scarlet Monastery; every Horde
--                   race but undead)
--     13914 13915 13916 13917
--                   Un'Goro Crater: the copies for undead, tauren
--                   and troll
--     14177         The Grateful Dead (troll version)
--     12783 12785   Desperate Research, Orgrimmar (as 12772/12773)
--
-- Not opened, because the pandaren takes the source race's copy instead:
--   13889 13903 13904 13905  Un'Goro, the orc, goblin and blood elf copies
--   14175                    The Grateful Dead, orc and goblin
--   13691 13736              A Valiant Of Orgrimmar, A Champion Rises
--                            (11 opens Sen'jin's)
--   12811 12812              the orc copies of 12783/12785
--
-- Class quests are not touched. mod-arac opens every class quest to every
-- race, and 04 adds pandaren to them. On a database without ARAC, the
-- class-gated night elf and troll quests include racial priest spells
-- (Elune's Grace, Hex of Weakness) that pandaren do not have.
--
-- `|` is idempotent.

UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 524288
  WHERE `AllowableRaces` > 0
    AND `ID` IN (5842, 6341, 6342, 6343, 6344, 9369, 12772, 12773, 14170);

UPDATE `quest_template` SET `AllowableRaces` = `AllowableRaces` | 1048576
  WHERE `AllowableRaces` > 0
    AND `ID` IN (1049, 5843, 6365, 6384, 6385, 6386, 9329, 9498, 9811, 9812, 9813,
                 12783, 12785, 13914, 13915, 13916, 13917, 14177);

-- --------------------------------------------------------------------------
-- Check. Must return 0 rows -- no quest without a class gate is open to the
-- source race and closed to its pandaren:
--
--   SELECT q.ID, q.AllowableRaces, q.LogTitle FROM quest_template q
--     LEFT JOIN quest_template_addon a ON a.ID = q.ID
--    WHERE q.AllowableRaces > 0 AND IFNULL(a.AllowableClasses, 0) = 0
--      AND (((q.AllowableRaces & 8) <> 0 AND (q.AllowableRaces & 524288) = 0)
--        OR ((q.AllowableRaces & 128) <> 0 AND (q.AllowableRaces & 1048576) = 0));
--
-- A row here is a new quest of the same kind, from a module or a core
-- update: decide whether the pandaren should have it and add it above.
--
-- In game: a new pandaren-A in Shadowglen and a pandaren-H in the Valley of
-- Trials are each offered "Welcome!".
