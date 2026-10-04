// mpqpack -- build a WoW-readable MPQ from a directory tree.
//
//   mpqpack <out.mpq> <root-dir>
//
// Every file under <root-dir> is added under its relative path with backslash
// separators, which is how the client names things internally. A (listfile) is
// written too: retail archives often omit it, but it is the only way tooling
// can enumerate what an archive contains.
//
// Archive format is v1 on purpose. The 3.3.5 client predates v2/v3/v4 handling
// in places, and nothing here is near the 4 GB v1 ceiling.
#include <StormLib.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>
#include <dirent.h>
#include <sys/stat.h>

static void walk(const std::string& root, const std::string& rel,
                 std::vector<std::pair<std::string, std::string>>& out) {
    std::string dir = rel.empty() ? root : root + "/" + rel;
    DIR* d = opendir(dir.c_str());
    if (!d) return;
    std::vector<std::string> names;
    while (struct dirent* e = readdir(d)) {
        std::string n = e->d_name;
        if (n == "." || n == "..") continue;
        names.push_back(n);
    }
    closedir(d);
    std::sort(names.begin(), names.end());          // deterministic archive order
    for (auto& n : names) {
        std::string r = rel.empty() ? n : rel + "/" + n;
        struct stat st;
        if (stat((root + "/" + r).c_str(), &st)) continue;
        if (S_ISDIR(st.st_mode)) walk(root, r, out);
        else out.push_back({root + "/" + r, r});
    }
}

int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: mpqpack <out.mpq> <root-dir>\n"); return 2; }
    const char* out = argv[1];
    std::string root = argv[2];

    std::vector<std::pair<std::string, std::string>> files;
    walk(root, "", files);
    if (files.empty()) { fprintf(stderr, "no files under %s\n", root.c_str()); return 1; }

    // Hash table must be a power of two and comfortably larger than the file
    // count, or adding files starts failing once it fills up.
    DWORD cap = 16;
    while (cap < files.size() * 2) cap <<= 1;

    remove(out);
    HANDLE h = nullptr;
    if (!SFileCreateArchive(out, MPQ_CREATE_ARCHIVE_V1 | MPQ_CREATE_LISTFILE, cap, &h)) {
        fprintf(stderr, "SFileCreateArchive failed (%u)\n", SErrGetLastError());
        return 1;
    }

    size_t ok = 0;
    for (auto& [disk, rel] : files) {
        std::string name = rel;
        for (auto& c : name) if (c == '/') c = '\\';
        if (SFileAddFileEx(h, disk.c_str(), name.c_str(),
                           MPQ_FILE_COMPRESS | MPQ_FILE_REPLACEEXISTING,
                           MPQ_COMPRESSION_ZLIB, MPQ_COMPRESSION_ZLIB)) {
            ++ok;
        } else {
            fprintf(stderr, "!! add failed (%u): %s\n", SErrGetLastError(), name.c_str());
        }
    }
    SFileCloseArchive(h);

    struct stat st{};
    stat(out, &st);
    printf("%s: %zu/%zu files, hash table %u, %.1f MB\n",
           out, ok, files.size(), cap, st.st_size / 1048576.0);
    return ok == files.size() ? 0 : 1;
}
