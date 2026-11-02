"""Container-level inspection of a locally owned APK: unwrap assets/dynamic.rsb.smf, read the RSB header
and group table, and run consistency checks. It does not decrypt or decode any game data and writes
nothing outside a temporary folder.

APK -> assets/dynamic.rsb.smf -> (RSLB / LZMA blocks) -> RSB -> resource groups

Usage:  python3 -I tools/inspect_build.py path/to/game.apk
"""
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rslb  # noqa: E402
from rsb_probe import read_groups, read_header  # noqa: E402


def main(apk):
    with tempfile.TemporaryDirectory() as tmp:
        smf_path, rsb_path = os.path.join(tmp, "x.smf"), os.path.join(tmp, "x.rsb")
        with zipfile.ZipFile(apk) as z:
            open(smf_path, "wb").write(z.read("assets/dynamic.rsb.smf"))
        print("SMF magic:", open(smf_path, "rb").read(4))
        size = rslb.decompress(smf_path, rsb_path)
        data = open(rsb_path, "rb").read()
    h = read_header(data)
    groups = read_groups(data, h)
    print("RSB bytes:", size, "magic:", data[:4], "version:", h["version"], "groups:", h["rsgp_Number"])
    print("first group starts at headLength:", groups[0]["offset"] == h["headLength"])
    print("groups are contiguous:", all(groups[i]["offset"] + groups[i]["size"] == groups[i + 1]["offset"]
                                        for i in range(len(groups) - 1)))
    print("last group ends at end of file:", groups[-1]["offset"] + groups[-1]["size"] == len(data))
    print("all offsets/sizes multiples of 4096:", all(g["offset"] % 4096 == 0 and g["size"] % 4096 == 0 for g in groups))
    print("every group stored uncompressed (ZSize == Size):",
          all(g["p0_zsize"] == g["p0_size"] and g["p1_zsize"] == g["p1_size"] for g in groups))
    for g in groups:
        print(f"  {g['name']:36s} offset={g['offset']:>11,} size={g['size']:>11,}")


if __name__ == "__main__":
    main(sys.argv[1])
