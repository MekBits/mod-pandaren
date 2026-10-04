#!/usr/bin/env python3
"""Minimal WDBC reader/writer + CLI dumper.

WotLK DBC: header 'WDBC', record count, field count, record size, string block size.
Strings are offsets into the trailing string block, so a
byte-compare of two DBCs is meaningless because offsets differ for identical text.
"""
import struct, sys

HDR = struct.Struct('<4s4I')


class DBC:
    def __init__(self, path, data=None):
        d = open(path, 'rb').read() if data is None else data
        magic, rc, fc, rs, sbs = HDR.unpack_from(d, 0)
        if magic != b'WDBC':
            raise SystemExit(f'{path}: not WDBC')
        self.path, self.fields, self.recsize = path, fc, rs
        off = HDR.size
        self.rows = [d[off + i * rs:off + (i + 1) * rs] for i in range(rc)]
        self.strings = d[off + rc * rs:off + rc * rs + sbs]

    @classmethod
    def from_bytes(cls, data, name='<bytes>'):
        """A DBC already in memory, e.g. fetched from a container."""
        return cls(name, data)

    def ints(self, row):
        # Field count and record size disagree in DBCs that pack several small
        # values into one 4-byte field -- CharStartOutfit declares 77 fields in
        # a 296-byte record, because race/class/sex/outfit share one uint32.
        # Decode by record size, which is always the truth on disk.
        n = self.recsize // 4
        return struct.unpack('<%dI' % n, row[:n * 4])

    def s(self, off):
        if off == 0 or off >= len(self.strings):
            return ''
        e = self.strings.index(b'\0', off)
        return self.strings[off:e].decode('utf-8', 'replace')

    def write(self, path, rows=None, strings=None):
        rows = self.rows if rows is None else rows
        strings = self.strings if strings is None else strings
        with open(path, 'wb') as f:
            f.write(HDR.pack(b'WDBC', len(rows), self.fields, self.recsize, len(strings)))
            for r in rows:
                f.write(r)
            f.write(strings)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        raise SystemExit('usage: dbc.py <file.dbc> [--id N|--col C=V] [--fields a,b,c] [--str i,j]')
    d = DBC(a[0])
    print(f'# {a[0]}: {len(d.rows)} rows, {d.fields} fields, recsize {d.recsize} '
          f'(4*{d.fields}={4*d.fields}), stringblock {len(d.strings)}', file=sys.stderr)
    sel_id = None; sel_col = None; strcols = set(); limit = 50
    for i, x in enumerate(a[1:]):
        if x == '--id': sel_id = int(a[i + 2])
        elif x == '--col': c, v = a[i + 2].split('='); sel_col = (int(c), int(v))
        elif x == '--str': strcols = {int(y) for y in a[i + 2].split(',')}
        elif x == '--limit': limit = int(a[i + 2])
    n = 0
    for r in d.rows:
        v = d.ints(r)
        if sel_id is not None and v[0] != sel_id: continue
        if sel_col and v[sel_col[0]] != sel_col[1]: continue
        out = []
        for i, x in enumerate(v):
            out.append(f'{i}:{d.s(x)!r}' if i in strcols else f'{i}:{x}')
        print(' '.join(out))
        n += 1
        if n >= limit: break
