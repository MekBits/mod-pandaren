// mpqx -- list/extract from a chain of WoW MPQ archives.
//
// WoW loads Data/*.MPQ then Data/wow-update-base-<build>.MPQ in ascending build
// order, locale archives last; later wins. We mirror that: archives are given on
// the command line in ASCENDING priority and the LAST one holding a name wins.
//
// Retail MPQs from Cata onwards usually ship without a (listfile), so `find`
// only sees what the archive itself names. `has` takes exact paths instead and
// is the reliable path for known filenames.
#include <StormLib.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <sys/stat.h>

static void mkdirs(std::string p) {
    for (size_t i = 1; i < p.size(); ++i)
        if (p[i] == '/') { std::string d = p.substr(0, i); mkdir(d.c_str(), 0755); }
}

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr,
            "usage: mpqx list   <archive>...                  -- dump (listfile) of each\n"
            "       mpqx find   <pattern> <archive>...        -- search listfiles\n"
            "       mpqx has    <path> <archive>...           -- report which archives hold path\n"
            "       mpqx get    <outdir> <listfile-of-paths> <archive>...\n");
        return 2;
    }
    std::string mode = argv[1];

    auto openAll = [&](int first, std::vector<std::pair<std::string, HANDLE>>& out) {
        for (int i = first; i < argc; ++i) {
            HANDLE h = nullptr;
            if (SFileOpenArchive(argv[i], 0, MPQ_OPEN_READ_ONLY, &h))
                out.push_back({argv[i], h});
            else
                fprintf(stderr, "!! cannot open %s (err %u)\n", argv[i], SErrGetLastError());
        }
    };

    if (mode == "list" || mode == "find") {
        int first = (mode == "find") ? 3 : 2;
        const char* pat = (mode == "find") ? argv[2] : "*";
        std::vector<std::pair<std::string, HANDLE>> ar; openAll(first, ar);
        for (auto& [name, h] : ar) {
            SFILE_FIND_DATA fd; long n = 0;
            HANDLE f = SFileFindFirstFile(h, pat, &fd, nullptr);
            if (!f) { fprintf(stderr, "-- %s: no matches (err %u)\n", name.c_str(), SErrGetLastError()); continue; }
            do { printf("%s\t%s\t%u\n", name.c_str(), fd.cFileName, fd.dwFileSize); ++n; }
            while (SFileFindNextFile(f, &fd));
            SFileFindClose(f);
            fprintf(stderr, "-- %s: %ld\n", name.c_str(), n);
        }
        return 0;
    }

    if (mode == "has") {
        std::vector<std::pair<std::string, HANDLE>> ar; openAll(3, ar);
        for (auto& [name, h] : ar) {
            HANDLE f;
            if (SFileOpenFileEx(h, argv[2], 0, &f)) {
                DWORD hi = 0, sz = SFileGetFileSize(f, &hi);
                printf("%s\t%u\n", name.c_str(), sz);
                SFileCloseFile(f);
            }
        }
        return 0;
    }

    if (mode == "get") {
        std::string outdir = argv[2];
        FILE* lf = fopen(argv[3], "r");
        if (!lf) { perror(argv[3]); return 1; }
        std::vector<std::pair<std::string, HANDLE>> ar; openAll(4, ar);
        char line[4096]; int ok = 0, miss = 0;
        while (fgets(line, sizeof line, lf)) {
            std::string p(line);
            while (!p.empty() && (p.back() == '\n' || p.back() == '\r' || p.back() == ' ')) p.pop_back();
            if (p.empty() || p[0] == '#') continue;
            // last archive that has it wins -- that is WoW's own precedence
            HANDLE src = nullptr; std::string from;
            for (auto& [name, h] : ar) {
                HANDLE f;
                if (SFileOpenFileEx(h, p.c_str(), 0, &f)) { SFileCloseFile(f); src = h; from = name; }
            }
            if (!src) { printf("MISS\t%s\n", p.c_str()); ++miss; continue; }
            HANDLE f;
            if (!SFileOpenFileEx(src, p.c_str(), 0, &f)) { printf("MISS\t%s\n", p.c_str()); ++miss; continue; }
            DWORD hi = 0, sz = SFileGetFileSize(f, &hi);
            std::vector<char> buf(sz);
            DWORD got = 0;
            SFileReadFile(f, buf.data(), sz, &got, nullptr);
            SFileCloseFile(f);
            std::string rel = p;
            for (auto& c : rel) if (c == '\\') c = '/';
            std::string full = outdir + "/" + rel;
            mkdirs(full);
            FILE* o = fopen(full.c_str(), "wb");
            if (!o) { printf("ERR\t%s\n", full.c_str()); ++miss; continue; }
            fwrite(buf.data(), 1, got, o); fclose(o);
            const char* ptch = (got >= 4 && !memcmp(buf.data(), "PTCH", 4)) ? "\tPTCH!" : "";
            printf("OK\t%s\t%u\t%s%s\n", p.c_str(), got, from.c_str(), ptch);
            ++ok;
        }
        fprintf(stderr, "== %d extracted, %d missing\n", ok, miss);
        return miss ? 1 : 0;
    }
    fprintf(stderr, "unknown mode %s\n", mode.c_str());
    return 2;
}
