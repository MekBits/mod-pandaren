// Most of mod-pandaren is data: everything in data/sql/db-world/ is applied by
// the database updater, which scans data/sql/ only for the modules in
// AC_MODULES_LIST. CMake (GetModuleSourceList) puts a module in that list only
// when it has a src/ directory.
//
// The name is not free: AzerothCore's module CMake generates a call to
// Add<directory name with _ instead of ->Scripts(). The directory is
// mod-pandaren, so Addmod_pandarenScripts().
void AddPandarenAchievementScripts();

void Addmod_pandarenScripts()
{
    AddPandarenAchievementScripts();
}
