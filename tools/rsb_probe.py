"""Read an RSB header and its resource-group (RSGP) table.

Field order follows the layout described by Pvz2Tool's RsbHeadInfo / RsbRsgpInfo
(MIT). Written independently; read-only, extracts nothing.
"""
import struct
import sys

HEADER_FIELDS = [
    "magic", "version", "zero0", "headLength", "fileList_Length", "fileList_BeginOffset",
    "zero1", "zero2", "rsgpList_Length", "rsgpList_BeginOffset", "rsgp_Number",
    "rsgpInfo_BeginOffset", "rsgpInfo_EachLength", "composite_Number", "compositeInfo_BeginOffset",
    "compositeInfo_EachLength", "compositeList_Length", "compositeList_BeginOffset",
    "autopool_Number", "autopoolInfo_BeginOffset", "autopoolInfo_EachLength", "ptx_Number",
    "ptxInfo_BeginOffset", "ptxInfo_EachLength", "xmlPart1", "xmlPart2", "xmlPart3",
]

GROUP_FIELDS = ["offset", "size", "pool_index", "flags", "fileOffset", "p0_offset", "p0_zsize",
                "p0_size", "p0_size2", "p1_offset", "p1_zsize", "p1_size"]


def read_header(data):
    vals = struct.unpack_from("<" + "I" * len(HEADER_FIELDS), data, 0)
    h = dict(zip(HEADER_FIELDS, vals))
    if data[:4] != b"1bsr":
        raise ValueError("bad RSB magic")
    return h


def read_groups(data, h):
    groups = []
    base, each = h["rsgpInfo_BeginOffset"], h["rsgpInfo_EachLength"]
    for i in range(h["rsgp_Number"]):
        rec = data[base + i * each: base + (i + 1) * each]
        name = rec[:0x80].split(b"\0", 1)[0].decode("ascii", "replace")
        nums = struct.unpack_from("<" + "I" * len(GROUP_FIELDS), rec, 0x80)
        groups.append({"name": name, **dict(zip(GROUP_FIELDS, nums))})
    return groups


if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read()
    h = read_header(data)
    for k in ("version", "headLength", "rsgp_Number", "rsgpInfo_BeginOffset", "rsgpInfo_EachLength",
              "ptxInfo_EachLength"):
        print(f"{k} = {h[k]} (0x{h[k]:X})")
    print("zero fields ok:", h["zero0"] == h["zero1"] == h["zero2"] == 0)
    for g in read_groups(data, h)[:12]:
        print(g["name"], "off", g["offset"], "size", g["size"], "p0", g["p0_zsize"], "->", g["p0_size"],
              "p1", g["p1_zsize"], "->", g["p1_size"], "flags", g["flags"])
