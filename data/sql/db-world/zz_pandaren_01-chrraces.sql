-- Pandaren: the two race rows. Race 20 = Alliance, 21 = Horde.
--
-- No core patch and no server-side DBC file: RaceMgr::LoadRaces() reads
-- sChrRacesStore, which LOAD_DBC fills from ChrRaces.dbc plus this override
-- table, and DBCDatabaseLoader::Load overrides per ID. IDs 20 and 21 exist in
-- the file as Northrend Skeleton and Ice Troll, both non-playable and not
-- used by any creature display; these rows replace them. IDs 13-19 are used
-- by NPCs through CreatureDisplayInfoExtra, and 22+ crash the 3.3.5 client
-- (character creation caches one object per race and sex in a fixed array
-- of 22 x 2, without a bounds check).
--
-- World.cpp loads the DBC overrides before RaceMgr counts the races and
-- before LoadPlayerInfo() sizes its table, so nothing else is needed.
--
-- TRAP: two fields carry the faction, and they count differently.
--   BaseLanguage  7 = Alliance, 1 = Horde   -> Player::TeamIdForRace()
--   Alliance      0 = Alliance, 1 = Horde   -> RaceMgr::LoadRaces()
-- If they disagree, the race sits in one faction's mask but plays as the
-- other, with no error. Always write both.

DELETE FROM `chrraces_dbc` WHERE `ID` IN (20, 21);

INSERT INTO `chrraces_dbc`
  (`ID`, `Flags`, `FactionID`, `ExplorationSoundID`, `MaleDisplayId`, `FemaleDisplayId`,
   `ClientPrefix`, `BaseLanguage`, `CreatureType`, `ResSicknessSpellID`, `SplashSoundID`,
   `ClientFilestring`, `CinematicSequenceID`, `Alliance`, `Name_Lang_enUS`, `Name_Lang_Mask`,
   `FacialHairCustomization_1`, `FacialHairCustomization_2`, `HairCustomization`,
   `Required_Expansion`)
VALUES
  -- Alliance. Faction and exploration sound from the night elf, whose start zone it uses.
  (20, 12,  4, 4145, 39500, 39501, 'Pa', 7, 7, 15007, 1096, 'Pandaren', 0, 0,
   'Pandaren', 16712190, 'NORMAL', 'EARRINGS', 'NORMAL', 0),
  -- Horde. Faction and exploration sound from the orc, whose start zone it uses.
  (21, 12,  2, 4141, 39500, 39501, 'Pa', 1, 7, 15007, 1096, 'Pandaren', 0, 1,
   'Pandaren', 16712190, 'NORMAL', 'EARRINGS', 'NORMAL', 0);

-- Flags 12 = CAN_MOUNT (4) + bit 8, as for human, orc, dwarf and blood elf.
--   BARE_FEET (2) is deliberately not set: pandaren have boot geosets, unlike
--   tauren, troll and draenei (14).
--
-- MaleDisplayId/FemaleDisplayId are 39500/39501 from 02. Both races share
--   them, as MoP's races 24-26 share 38551/38552.
--
-- CinematicSequenceID 0 = no intro. MoP's 259 does not exist in WotLK's
--   CinematicSequences.dbc, and borrowing the night elf or orc intro would
--   show a pandaren another race's story.
--
-- ClientFilestring 'Pandaren' is the path under Character\ in the MPQ, and
--   ClientPrefix 'Pa' the texture name prefix. Both must match the client
--   patch, or
--   the model renders untextured.
