#!/usr/bin/env python3
"""Build the pandaren client patch on top of a WoW 3.3.5a client.

The released patch-Z.MPQ is built with this script against an unmodified
client. A client that already has other patches touching the same files (other
races, HD models, UI mods) needs its own build: a later patch letter replaces
whole files, so a DBC from the released patch would throw away every row the
other patches added. This script reads the files the client actually loads and
adds pandaren to them.

    build_patch.py --client "<WoW dir>" --assets patch-Z.MPQ --out patch-Z.MPQ

  --client    the WoW directory (the one with Wow.exe and Data/)
  --assets    the released patch-Z.MPQ, or a directory it was extracted to;
              models, textures and the character-select scene are taken from it
  --out       the MPQ to write, or a directory when it does not end in .mpq
  --letter    the patch letter you will install it as (default Z). Archives
              with that letter are ignored when reading the client, so an older
              build of this patch is not built upon.

Needs the two small StormLib tools in tools/ (mpqx to read, mpqpack to write);
see the README for building them.

What is generated from the client's own files:

  DBFilesClient\\*.dbc     14 DBCs: the client's rows plus pandaren's
  Interface\\GlueXML\\*     race buttons, icons, flavour text, racials
  UI-CharacterCreate-Races.blp   the two pandaren icons spliced in

Everything else is copied from --assets unchanged.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import dbcrows  # noqa: E402
import glue     # noqa: E402
from dbc import DBC  # noqa: E402

GLUE_FILES = ['Interface\\GlueXML\\CharacterCreate.lua',
              'Interface\\GlueXML\\CharacterCreate.xml',
              'Interface\\GlueXML\\GlueParent.lua',
              'Interface\\GlueXML\\GlueStrings.lua']
ATLAS = 'Interface\\Glues\\CharacterCreate\\UI-CharacterCreate-Races.blp'

# Files taken from --assets as they are. Anything else in the assets archive
# (DBCs, glue files, the atlas) is generated instead.
ASSET_PREFIXES = ('character\\pandaren\\',
                  'interface\\glues\\models\\ui_pandaren\\',
                  'world\\expansion04\\',
                  'world\\kalimdor\\hyjal\\lavaeffects\\')

BASE_ARCHIVES = ['common.MPQ', 'common-2.MPQ', 'expansion.MPQ', 'lichking.MPQ']
LOCALE_BASE = ['locale-{l}.MPQ', 'expansion-locale-{l}.MPQ', 'lichking-locale-{l}.MPQ']
LETTER = re.compile(r'^patch-([A-Za-z0-9])\.mpq$', re.I)
LOCALE_LETTER = re.compile(r'^patch-[a-zA-Z]{4}-([A-Za-z0-9])\.mpq$', re.I)


def archive_chain(client, letter):
    """The client's archives, lowest priority first (later wins, as in mpqx).

    Base archives, then the locale base, then the numbered patches, then the
    lettered ones, root before locale at each step. A patch with our own letter
    is left out: the base is what the client loads without this patch.
    """
    data = os.path.join(client, 'Data')
    if not os.path.isdir(data):
        sys.exit(f'{client}: no Data directory')
    locales = [d for d in os.listdir(data)
               if len(d) == 4 and os.path.isfile(os.path.join(data, d, f'locale-{d}.MPQ'))]
    if len(locales) != 1:
        sys.exit(f'{data}: expected one locale directory, found {locales}')
    loc = locales[0]
    ldir = os.path.join(data, loc)

    def ci(d, name):
        for fn in os.listdir(d):
            if fn.lower() == name.lower():
                return os.path.join(d, fn)
        return None

    chain = [ci(data, n) for n in BASE_ARCHIVES]
    chain += [ci(ldir, n.format(l=loc)) for n in LOCALE_BASE]
    for n in ('', '-2', '-3'):
        chain += [ci(data, f'patch{n}.MPQ'), ci(ldir, f'patch-{loc}{n}.MPQ')]
    lettered = []
    for d, rx in ((data, LETTER), (ldir, LOCALE_LETTER)):
        for fn in os.listdir(d):
            m = rx.match(fn)
            if m and m.group(1).upper() not in '23':
                if m.group(1).upper() == letter.upper():
                    print(f'  ignoring {fn}: same letter as the patch being built')
                    continue
                lettered.append((m.group(1).upper(), d != data, os.path.join(d, fn)))
    chain += [p for _, _, p in sorted(lettered)]
    return [p for p in chain if p]


def mpqx(tools, *args):
    exe = os.path.join(tools, 'mpqx')
    if not os.path.exists(exe):
        sys.exit(f'{exe} not found -- build it first (see the README)')
    r = subprocess.run([exe, *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'mpqx {args[0]} failed:\n{r.stderr}')
    return r.stdout


def resolve(root, name):
    """A path under root for an MPQ name, matching case-insensitively."""
    d = root
    for part in name.split('\\'):
        hit = next((x for x in os.listdir(d) if x.lower() == part.lower()), None) \
            if os.path.isdir(d) else None
        if hit is None:
            return None
        d = os.path.join(d, hit)
    return d if os.path.exists(d) else None


def extract(tools, names, archives, outdir):
    """Extract `names` with the last archive winning. Returns {name: path}."""
    lst = os.path.join(outdir, 'names.txt')
    with open(lst, 'w') as f:
        f.write('\n'.join(names) + '\n')
    mpqx(tools, 'get', outdir, lst, *archives)
    found = {}
    for n in names:
        p = resolve(outdir, n)              # mpqx writes the case the archive uses
        if p:
            found[n] = p
    return found


def splice_icons(src_path, dst_path):
    """Copy the two pandaren icons (column 6 of the 8x4 grid) between atlases.

    Both are 512x256 DXT3 with 16-byte blocks, and a 64x64 icon is block
    aligned at every mip level down to 4x4, so the compressed blocks are copied
    as they are.
    """
    import struct
    src, dst = open(src_path, 'rb').read(), bytearray(open(dst_path, 'rb').read())

    def info(d):
        comp, adepth, aenc, mips = struct.unpack_from('<4B', d, 8)
        w, h = struct.unpack_from('<2I', d, 12)
        return comp, aenc, w, h, struct.unpack_from('<16I', d, 20), struct.unpack_from('<16I', d, 84)
    s, t = info(src), info(dst)
    if s[:4] != t[:4] or s[:4] != (2, 1, 512, 256):
        sys.exit(f'race icon atlas: expected 512x256 DXT3 in both, got {s[:4]} and {t[:4]}')
    for lvl in range(16):
        if s[5][lvl] == 0 or t[5][lvl] == 0:
            break
        lw, lh = 512 >> lvl, 256 >> lvl
        iw, ih = lw // 8, lh // 4
        if iw < 4 or ih < 4:
            break
        bw = lw // 4
        for row in (0, 2):                       # male, female
            bx0, by0 = 6 * iw // 4, row * ih // 4
            for by in range(by0, by0 + ih // 4):
                for bx in range(bx0, bx0 + iw // 4):
                    so = s[4][lvl] + (by * bw + bx) * 16
                    do = t[4][lvl] + (by * bw + bx) * 16
                    dst[do:do + 16] = src[so:so + 16]
    open(dst_path, 'wb').write(dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--client', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--letter', default='Z')
    ap.add_argument('--tools', default=os.path.join(HERE, '..', 'tools'))
    a = ap.parse_args()

    chain = archive_chain(a.client, a.letter)
    print(f'reading {len(chain)} archives from {a.client}')
    work = tempfile.mkdtemp(prefix='pandaren-')
    try:
        tree = os.path.join(work, 'tree')
        base = os.path.join(work, 'base')
        os.makedirs(tree)
        os.makedirs(base)

        # --- assets ---------------------------------------------------------
        if os.path.isdir(a.assets):
            asset_root = a.assets
        else:
            asset_root = os.path.join(work, 'assets')
            os.makedirs(asset_root)
            listing = mpqx(a.tools, 'list', a.assets)
            names = [ln.split('\t')[1] for ln in listing.splitlines()
                     if '\t' in ln and ln.split('\t')[1] != '(listfile)']
            extract(a.tools, names, [a.assets], asset_root)
        copied = 0
        for root, _, files in os.walk(asset_root):
            for fn in files:
                rel = os.path.relpath(os.path.join(root, fn), asset_root)
                key = rel.replace('/', '\\').replace(os.sep, '\\').lower()
                if key.startswith(ASSET_PREFIXES):
                    dst = os.path.join(tree, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(os.path.join(root, fn), dst)
                    copied += 1
        if copied < 100:
            sys.exit(f'{a.assets}: only {copied} asset files found -- is this the pandaren patch?')
        icon_src = resolve(asset_root, ATLAS)
        if not icon_src:
            sys.exit(f'{a.assets}: no {ATLAS} to take the pandaren icons from')
        print(f'  {copied} asset files')

        # --- DBCs -----------------------------------------------------------
        names = [f'DBFilesClient\\{n}.dbc' for n in dbcrows.ALL]
        got = extract(a.tools, names + GLUE_FILES + [ATLAS], chain, base)
        missing = [n for n in names + GLUE_FILES + [ATLAS] if n not in got]
        if missing:
            sys.exit(f'not found in the client: {missing}')
        dbcdir = os.path.join(tree, 'DBFilesClient')
        os.makedirs(dbcdir)

        print(f'  {"DBC":<28} {"base":>7} {"replaced":>9} {"result":>7}')

        def log(name, before, dropped, after, note=''):
            print(f'  {name:<28} {before:>7} {dropped:>9} {after:>7}  {note}')
        for n in dbcrows.SCHEMAS:
            dbcrows.apply_rows(n, got[f'DBFilesClient\\{n}.dbc'],
                               os.path.join(HERE, 'rows'), os.path.join(dbcdir, n + '.dbc'), log)
        for n, fn in dbcrows.COMPUTE.items():
            fn(got[f'DBFilesClient\\{n}.dbc'], os.path.join(dbcdir, n + '.dbc'), log)

        # --- glue -----------------------------------------------------------
        gdir = os.path.join(tree, 'Interface', 'GlueXML')
        os.makedirs(gdir)
        for n in GLUE_FILES:
            shutil.copy2(got[n], os.path.join(gdir, n.split('\\')[-1]))
        glue.patch(gdir, lambda m: print('  ' + m))

        adir = os.path.join(tree, 'Interface', 'Glues', 'CharacterCreate')
        os.makedirs(adir, exist_ok=True)
        atlas = os.path.join(adir, 'UI-CharacterCreate-Races.blp')
        shutil.copy2(got[ATLAS], atlas)
        splice_icons(icon_src, atlas)
        print('  race icons spliced into UI-CharacterCreate-Races.blp')

        # --- out ------------------------------------------------------------
        if a.out.lower().endswith('.mpq'):
            exe = os.path.join(a.tools, 'mpqpack')
            if not os.path.exists(exe):
                sys.exit(f'{exe} not found -- build it first, or give --out a directory')
            r = subprocess.run([exe, a.out, tree], capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit(f'mpqpack failed:\n{r.stderr}')
            print(f'wrote {a.out} ({os.path.getsize(a.out) / 1e6:.1f} MB)')
        else:
            if os.path.exists(a.out):
                sys.exit(f'{a.out} exists; give a new directory')
            shutil.copytree(tree, a.out)
            print(f'wrote {a.out}/')
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
