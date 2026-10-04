// mod-pandaren is a pure data module: everything is in data/sql/db-world/.
//
// The loader exists only so the module is compiled in. The database updater
// (UpdateFetcher::ReceiveIncludedDirectories) scans data/sql/ only for the
// modules in AC_MODULES_LIST, and CMake (GetModuleSourceList) puts a module in
// that list only when it has a src/ directory. Without this file the SQL would
// never run, and nothing would say so.
//
// The name is not free: AzerothCore's module CMake generates a call to
// Add<directory name with _ instead of ->Scripts(). The directory is
// mod-pandaren, so Addmod_pandarenScripts().
void Addmod_pandarenScripts()
{
}
