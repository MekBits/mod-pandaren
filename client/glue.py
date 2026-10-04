"""Add pandaren to the character-creation glue UI.

Edits the four GlueXML files the client already has, so whatever another patch
did to them (worgen and goblin buttons, for instance) survives. Every edit is
idempotent and fails loudly when its anchor is missing.

Modified GlueXML is why the client needs a Wow.exe with the interface
signature check removed; without it the client reports "Your game/login
interface files are corrupt".

  CharacterCreate.lua  RACE_ICON_TCOORDS gets the two atlas rectangles (MoP's
                       own: column 0.750-0.875, which 3.3.5 leaves empty).
                       MAX_RACES grows by two, and the race buttons are laid
                       out at runtime from the client's faction data.
  CharacterCreate.xml  Two more race buttons. The lua indexes them by
                       enumeration number, so a missing one is a nil frame.
  GlueParent.lua       CharModelGlowInfo and GlueAmbienceTracks are indexed by
                       race name with no nil guard.
  GlueStrings.lua      RACE_INFO_* is the flavour text and ABILITY_INFO_*<n> the
                       racial list; CharacterCreate.lua walks the latter upward
                       until it hits nil, so the numbering is contiguous from 1.

The lookup key is ChrRaces' ClientFileString uppercased, 'PANDAREN', shared by
both races.
"""
import os
import re
import sys

ICONS = ('["PANDAREN_MALE"]   \t= {0.750, 0.875, 0, 0.25},',
         '["PANDAREN_FEMALE"] \t= {0.750, 0.875, 0.5, 0.75},')

# MAX_RACES is not a hint. CharacterCreateEnumerateRaces starts with
#
#     if ( CharacterCreate.numRaces > MAX_RACES ) then
#         message("Too many races!  Update MAX_RACES");
#         return;
#
# and that return leaves EVERY race button unconfigured, not just the new ones.
#
# Blizzard also anchored each race button statically in the XML, which fixes the
# column split at one number of races per faction. Rather than re-anchor for one
# more race, ask the client which faction each enumerated race belongs to.
# GetFactionForRace takes the same 1..numRaces index the buttons are numbered by
# and returns the untranslated faction token. At six per column the result is the
# stock layout; the gap only tightens when a column no longer fits above the
# gender label.
LAYOUT = '''-- Lay the race icons out from the client's own faction data instead of
-- from static anchors, which assume a fixed number of races per faction.
RACE_BUTTON_SIZE = 38;
RACE_BUTTON_TOP = -50;
RACE_BUTTON_GAP = 10;
RACE_BUTTON_COLUMN_HEIGHT = 310;

function CharacterCreate_LayoutRaceButtons()
\tlocal numRaces = CharacterCreate.numRaces;
\tif ( not numRaces ) then
\t\treturn;
\tend
\tlocal tallest = 0;
\tlocal counted = {};
\tfor i=1, numRaces, 1 do
\t\tlocal _, faction = GetFactionForRace(i);
\t\tlocal n = (counted[faction] or 0) + 1;
\t\tcounted[faction] = n;
\t\tif ( n > tallest ) then
\t\t\ttallest = n;
\t\tend
\tend
\tlocal gap = RACE_BUTTON_GAP;
\tif ( tallest > 1 ) then
\t\tlocal fits = (RACE_BUTTON_COLUMN_HEIGHT - tallest * RACE_BUTTON_SIZE) / (tallest - 1);
\t\tif ( fits < gap ) then
\t\t\tgap = fits;
\t\tend
\tend
\tlocal row = {};
\tfor i=1, numRaces, 1 do
\t\tlocal _, faction = GetFactionForRace(i);
\t\tlocal n = row[faction] or 0;
\t\trow[faction] = n + 1;
\t\tlocal x = 50;
\t\tif ( faction == "Alliance" ) then
\t\t\tx = -50;
\t\tend
\t\tlocal button = _G["CharacterCreateRaceButton"..i];
\t\tbutton:ClearAllPoints();
\t\tbutton:SetPoint("TOP", button:GetParent(), "TOP", x, RACE_BUTTON_TOP - n * (RACE_BUTTON_SIZE + gap));
\tend
end

'''
LAYOUT_CALL = '\tCharacterCreate_LayoutRaceButtons();\n'
HIDE_LOOP = re.compile(r'for i=CharacterCreate\.numRaces \+ 1, MAX_RACES, 1 do\s*\n'
                       r'\s*_G\["CharacterCreateRaceButton"\.\.i\]:Hide\(\);\s*\n\s*end\s*\n')

XML_BUTTON = ('{i}<CheckButton name="CharacterCreateRaceButton{id}" '
              'inherits="CharacterCreateRaceButtonTemplate" id="{id}">\n'
              '{i}\t<Anchors>\n'
              '{i}\t\t<Anchor point="TOPLEFT" relativeTo="CharacterCreateRaceButton{below}" '
              'relativePoint="BOTTOMLEFT" x="0" y="-10"/>\n'
              '{i}\t</Anchors>\n'
              '{i}</CheckButton>\n')

# MoP's own text names the neutral-faction choice and the Wandering Isle start.
# Here pandaren pick a side at creation and start in Shadowglen or the Valley of
# Trials, so the text says that.
RACE_INFO = (
    "The pandaren of the Wandering Isle have at last set foot on Azeroth's "
    "shores. Long students of patience, brewing and the martial arts, they "
    "arrive with old grudges left behind and choose their allegiance on "
    "landfall -- some to the Alliance, some to the Horde."
)

# The four racials the server delivers (zz_pandaren_08), not MoP's five:
# Epicurean is not implemented, and Inner Peace gives a kill-experience bonus
# instead of MoP's rested bonus. Order matches the spellbook.
ABILITIES = [
    "- May put enemies to sleep with a touch of their hand.",
    "- Inner peace grants increased experience from kills.",
    "- Cooking skill increased.",
    "- Bouncy and take less falling damage.",
]


class Text:
    """A file's text with its own line ending, edited in \\n form."""

    def __init__(self, path):
        self.path = path
        raw = open(path, 'rb').read().decode('utf-8', 'surrogateescape')
        self.crlf = '\r\n' in raw
        self.s = raw.replace('\r\n', '\n')

    def save(self):
        out = self.s.replace('\n', '\r\n') if self.crlf else self.s
        open(self.path, 'wb').write(out.encode('utf-8', 'surrogateescape'))


def die(path, what):
    sys.exit(f'{path}: {what}')


def patch_charactercreate(lua_path, xml_path, log):
    lua, xml = Text(lua_path), Text(xml_path)
    buttons = [int(n) for n in re.findall(r'<CheckButton name="CharacterCreateRaceButton(\d+)"', xml.s)]
    m = re.search(r'^MAX_RACES = (\d+);', lua.s, re.M)
    if not m or not buttons:
        die(lua_path, 'MAX_RACES or the race buttons not found')
    if 'PANDAREN_MALE' in lua.s:
        # Patched before. The two files have to agree, or the enumeration
        # reaches a button that does not exist.
        if int(m.group(1)) != max(buttons) or 'CharacterCreate_LayoutRaceButtons();' not in lua.s:
            die(lua_path, f'already has pandaren, but MAX_RACES = {m.group(1)} and the XML '
                          f'has {max(buttons)} race buttons')
        log('CharacterCreate.lua/.xml: already patched')
        return
    if int(m.group(1)) != max(buttons) or sorted(buttons) != list(range(1, max(buttons) + 1)):
        die(lua_path, f'MAX_RACES = {m.group(1)} but the XML has buttons {sorted(buttons)}')
    n = max(buttons)
    lua.s = lua.s[:m.start()] + f'MAX_RACES = {n + 2};' + lua.s[m.end():]

    # The icon rectangles go before the table's closing brace.
    t = lua.s.find('RACE_ICON_TCOORDS = {')
    if t < 0:
        die(lua_path, 'RACE_ICON_TCOORDS not found')
    close = re.compile(r'^\s*\}', re.M).search(lua.s, t)
    body = lua.s[t:close.start()].rstrip()
    if not body.endswith(','):
        die(lua_path, 'the last RACE_ICON_TCOORDS entry has no trailing comma')
    lua.s = (lua.s[:close.start()] + '\n' + ''.join(f'\t{e}\n' for e in ICONS) +
             lua.s[close.start():])

    f = lua.s.find('function CharacterCreateEnumerateRaces(')
    if f < 0:
        die(lua_path, 'CharacterCreateEnumerateRaces not found')
    lua.s = lua.s[:f] + LAYOUT + lua.s[f:]
    h = HIDE_LOOP.search(lua.s, f + len(LAYOUT))
    if not h:
        die(lua_path, 'the button hide loop in CharacterCreateEnumerateRaces not found')
    lua.s = lua.s[:h.end()] + LAYOUT_CALL + lua.s[h.end():]

    # The new buttons go after the last one defined, so every relativeTo names a
    # frame that already exists. The anchor is a fallback: the layout function
    # moves every visible button.
    last = list(re.finditer(r'<CheckButton name="CharacterCreateRaceButton(\d+)"', xml.s))[-1]
    indent = xml.s[xml.s.rindex('\n', 0, last.start()) + 1:last.start()]
    end = xml.s.index('</CheckButton>\n', last.start()) + len('</CheckButton>\n')
    below = last.group(1)
    added = (XML_BUTTON.format(i=indent, id=n + 1, below=below) +
             XML_BUTTON.format(i=indent, id=n + 2, below=n + 1))
    xml.s = xml.s[:end] + added + xml.s[end:]

    lua.save()
    xml.save()
    log(f'CharacterCreate.lua/.xml: MAX_RACES {n} -> {n + 2}, buttons {n + 1} and {n + 2}')


def append_after_last(path, table, line, log):
    t = Text(path)
    if line in t.s:
        log(f'{os.path.basename(path)}: {table} already patched')
        return
    hits = list(re.finditer(r'^%s\["[A-Z]+"\] = .*\n' % re.escape(table), t.s, re.M))
    if not hits:
        die(path, f'no {table}[...] assignments found')
    e = hits[-1].end()
    t.s = t.s[:e] + line + '\n' + t.s[e:]
    t.save()
    log(f'{os.path.basename(path)}: {table}["PANDAREN"]')


def patch_gluestrings(path, log):
    t = Text(path)
    if 'RACE_INFO_PANDAREN' in t.s:
        log('GlueStrings.lua: already patched')
        return
    lines = [f'RACE_INFO_PANDAREN = "{RACE_INFO}";',
             f'RACE_INFO_PANDAREN_FEMALE = "{RACE_INFO}";'] + \
            [f'ABILITY_INFO_PANDAREN{i + 1} = "{x}";' for i, x in enumerate(ABILITIES)]
    t.s = t.s.rstrip('\n') + '\n\n' + '\n'.join(lines) + '\n'
    t.save()
    log(f'GlueStrings.lua: flavour text and {len(ABILITIES)} racial lines')


def patch(gluexml_dir, log):
    def p(name):
        for fn in os.listdir(gluexml_dir):
            if fn.lower() == name.lower():
                return os.path.join(gluexml_dir, fn)
        sys.exit(f'{gluexml_dir}: {name} not found')
    patch_charactercreate(p('CharacterCreate.lua'), p('CharacterCreate.xml'), log)
    append_after_last(p('GlueParent.lua'), 'CharModelGlowInfo',
                      'CharModelGlowInfo["PANDAREN"] = 0.0;', log)
    append_after_last(p('GlueParent.lua'), 'GlueAmbienceTracks',
                      'GlueAmbienceTracks["PANDAREN"] = "GlueScreenHuman";', log)
    patch_gluestrings(p('GlueStrings.lua'), log)
