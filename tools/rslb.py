"""Decompress an RSLB (.smf) container: a header, a block table, then one raw LZMA1 stream per block.

Layout (from the format description in yhzxcv/Z-Editor's RslbDecompressor comments;
this implementation is written independently):
  0x00 "RSLB" | 0x04 u32 version | 0x08 u64 total_uncompressed | 0x10 u64 packed_size
  0x18 u32 block_size | 0x1C u32 block_count | 0x20 block table, 36 bytes each:
    u64 cum_offset, u32 usize, u32 reserved, u64 data_offset, u32 csize (incl. 5-byte props),
    u8 lzma_props, u32 dict_size, 3 pad
  each block at data_offset: 5 bytes (props + dict) then raw LZMA1 data (no end marker).
"""
import lzma
import struct
import sys


def decompress(src_path, dst_path):
    with open(src_path, "rb") as f:
        data = f.read()
    magic, version, total, packed, block_size, count = struct.unpack_from("<4sIQQII", data, 0)
    if magic != b"RSLB":
        raise ValueError("not an RSLB file")
    produced = 0
    with open(dst_path, "wb") as out:
        for i in range(count):
            cum, usize, _res, doff, csize, props, dict_size = struct.unpack_from(
                "<QIIQIBI", data, 0x20 + i * 36)
            if cum != produced:
                raise ValueError(f"block {i}: offset gap")
            lc = props % 9
            lp = (props // 9) % 5
            pb = props // 45
            filters = [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}]
            stream = data[doff + 5: doff + csize]
            chunk = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters).decompress(
                stream, max_length=usize)
            if len(chunk) != usize:
                raise ValueError(f"block {i}: got {len(chunk)} bytes, expected {usize}")
            out.write(chunk)
            produced += usize
    if produced != total:
        raise ValueError(f"total {produced} != declared {total}")
    return produced


if __name__ == "__main__":
    print(decompress(sys.argv[1], sys.argv[2]), "bytes written")
