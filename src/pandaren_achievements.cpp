/*
 * mod-pandaren: the criteria script for achievements that list races one by
 * one.
 */

#include "AchievementCriteriaScript.h"
#include "Player.h"

// Pandaren are one race with two race ids, 20 on the Alliance and 21 on the
// Horde. An achievement that lists races one by one (Check Your Head, Shake Your
// Bunny-Maker) checks the target with a T_PLAYER_CLASS_RACE data row, which takes
// a single race; its "Pandaren" criterion uses this script instead
// (zz_pandaren_13-achievements.sql). The other data rows of the criterion, such
// as gender and level, still apply: all of them must pass.
class achievement_pandaren_target : public AchievementCriteriaScript
{
public:
    achievement_pandaren_target() : AchievementCriteriaScript("achievement_pandaren_target") { }

    bool OnCheck(Player* /*source*/, Unit* target, uint32 /*criteria_id*/) override
    {
        Player* player = target ? target->ToPlayer() : nullptr;
        if (!player)
            return false;

        // getRace(), as AzerothCore's own T_PLAYER_CLASS_RACE check uses.
        uint8 race = player->getRace();
        return race == 20 || race == 21;
    }
};

void AddPandarenAchievementScripts()
{
    new achievement_pandaren_target();
}
