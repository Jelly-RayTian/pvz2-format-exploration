"""Print an annotated hex walk-through of an (unencrypted) RTON using the same tag rules as mini_rton.
Prints facts only. Usage: python3 -I annotate_rton.py file.rton"""
import struct, sys

def uvarint(d, p):
    r = s = 0
    while True:
        b = d[p]; p += 1
        r |= (b & 0x7F) << s
        if b < 0x80: return r, p
        s += 7

def walk(d):
    rows = []; cache = []; p = 0
    def row(a, b, text, depth): rows.append((a, d[a:b], '  ' * depth + text))
    row(0, 4, 'magic "RTON"', 0); row(4, 8, 'version = 1 (uint32 LE)', 0); p = 8
    def val(p, depth):
        t = d[p]
        if t in (0, 1): row(p, p+1, 'false' if t == 0 else 'true', depth); return p+1
        if t in (0x08, 0x0A, 0x10, 0x12, 0x20):
            n = {0x08:1,0x0A:1,0x10:2,0x12:2,0x20:4}[t]; sg = t in (0x08,0x10,0x20)
            v = int.from_bytes(d[p+1:p+1+n], 'little', signed=sg)
            row(p, p+1+n, f'fixed int, value {v}', depth); return p+1+n
        if t == 0x21: row(p, p+1, 'int32 zero (no payload) = 0', depth); return p+1
        if t in (0x24, 0x25):
            n, q = uvarint(d, p+1); v = n if t == 0x24 else (n//2 if n % 2 == 0 else -(n+1)//2)
            row(p, q, ('unsigned' if t == 0x24 else 'signed') + f' varint = {v}', depth); return q
        if t == 0x81:
            n, q = uvarint(d, p+1); s = d[q:q+n].decode(); row(p, q+n, f'string "{s}"', depth); return q+n
        if t == 0x90:
            n, q = uvarint(d, p+1); s = d[q:q+n].decode(); cache.append(s)
            row(p, q+n, f'define cache[{len(cache)-1}] = "{s}"', depth); return q+n
        if t == 0x91:
            n, q = uvarint(d, p+1); row(p, q, f'recall cache[{n}] = "{cache[n]}"', depth); return q
        if t == 0x85: row(p, p+1, 'object start', depth); return obj(p+1, depth+1)
        if t == 0x86:
            assert d[p+1] == 0xFD; n, q = uvarint(d, p+2); row(p, q, f'array start, {n} item(s)', depth)
            for _ in range(n): q = val(q, depth+1)
            assert d[q] == 0xFE; row(q, q+1, 'array end', depth); return q+1
        raise ValueError(hex(t))
    def key(p, depth):
        t = d[p]
        if t == 0x81 or t == 0x90:
            n, q = uvarint(d, p+1); s = d[q:q+n].decode()
            if t == 0x90: cache.append(s)
            row(p, q+n, ('key, define cache[%d]' % (len(cache)-1) if t == 0x90 else 'key') + f' "{s}"', depth); return q+n
        n, q = uvarint(d, p+1); row(p, q, f'key, recall cache[{n}] = "{cache[n]}"', depth); return q
    def obj(p, depth):
        while d[p] != 0xFF:
            p = key(p, depth); p = val(p, depth)
        row(p, p+1, 'object end', depth-1); return p+1
    p = obj(p, 1)
    row(p, p+4, 'footer "DONE"', 0)
    assert p + 4 == len(d)
    return rows, cache

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    rows, cache = walk(d)
    def short(b):
        return b.hex(' ') if len(b) <= 8 else b[:8].hex(' ') + f' ..+{len(b) - 8}'
    for a, b, t in rows: print(f'{a:04X}  {short(b):<30} {t}')
    print('CACHE', cache)
