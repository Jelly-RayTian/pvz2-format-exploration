"""Hand-built RTON byte strings, each with its expected decoded value.

Every byte is annotated so you can check it against docs/rton-scope.md.
These are synthetic: they contain no game data.
"""

HEADER = bytes.fromhex("52544F4E" "01000000")  # "RTON" + version 1 (uint32 LE)
FOOTER = bytes.fromhex("444F4E45")              # "DONE"

# name -> (bytes, expected decoded Python value)
FIXTURES = {
    # {}   -- just the end-of-object marker FF
    "empty": (HEADER + bytes.fromhex("FF") + FOOTER, {}),

    # {"a": true, "b": false}
    #   81 01 61   string, 1 byte: "a"      01  true
    #   81 01 62   string, 1 byte: "b"      00  false
    "bools": (
        HEADER + bytes.fromhex("81 01 61 01  81 01 62 00  FF") + FOOTER,
        {"a": True, "b": False},
    ),

    # {"name": "Zombie"}
    #   81 04 6E616D65         "name"
    #   81 06 5A6F6D626965     "Zombie"
    "string": (
        HEADER + bytes.fromhex("81 04 6E616D65  81 06 5A6F6D626965  FF") + FOOTER,
        {"name": "Zombie"},
    ),

    # {"n": -2, "u": 200}
    #   08 FE   int8 0xFE = -2 (two's complement)
    #   0A C8   uint8 0xC8 = 200
    "small_ints": (
        HEADER + bytes.fromhex("81 01 6E 08 FE  81 01 75 0A C8  FF") + FOOTER,
        {"n": -2, "u": 200},
    ),

    # {"a": {"a": 1}}  -- cache define (90) then recall (91 00) inside a nested object
    #   90 01 61  define "a" (index 0)   85  object start
    #   91 00     recall index 0 ("a")   08 01  int8 1
    #   FF FF     inner end, outer end
    "nested_cache_recall": (
        HEADER + bytes.fromhex("90 01 61  85  91 00  08 01  FF  FF") + FOOTER,
        {"a": {"a": 1}},
    ),

    # {"a": [1, 2]}  -- 86 FD <count=2> 08 01 08 02 FE
    "array": (
        HEADER + bytes.fromhex("81 01 61  86 FD 02  08 01  08 02  FE  FF") + FOOTER,
        {"a": [1, 2]},
    ),

    # {"w": -300, "i": 70000}
    #   10 D4 FE  int16 LE: 0xFED4 = -300
    #   20 70 11 01 00  int32 LE: 0x00011170 = 70000
    "wide_ints": (
        HEADER + bytes.fromhex("81 01 77 10 D4 FE  81 01 69 20 70 11 01 00  FF") + FOOTER,
        {"w": -300, "i": 70000},
    ),

    # {"mX": 0, "mY": -150}  -- 21 = int32 zero (no payload);
    # 25 AB 02 -> varint 0x2B + (2 << 7) = 299 (odd) -> -(299+1)/2 = -150
    "int32_zero_and_signed": (
        HEADER + bytes.fromhex("81 02 6D 58 21  81 02 6D 59 25 AB 02  FF") + FOOTER,
        {"mX": 0, "mY": -150},
    ),

    # A made-up sample with the same *shape* as a typical object file: a version, then an array of
    # objects (uid / objclass / objdata). The second object reuses keys and values through the string
    # cache (91). Built with a small encoder; annotated byte by byte in the article (section 3.6).
    "showcase": (
        bytes.fromhex(
            "52 54 4f 4e 01 00 00 00 90 07 76 65 72 73 69 6f 6e 24 01 90 07 6f 62 6a 65 63 74 73 86 fd 02 85"
            "90 03 75 69 64 90 05 31 2e 30 2e 31 90 08 6f 62 6a 63 6c 61 73 73 90 08 44 65 6d 6f 44 61 74 61"
            "90 07 6f 62 6a 64 61 74 61 85 90 04 6e 61 6d 65 90 04 64 65 6d 6f 90 05 69 74 65 6d 73 86 fd 00"
            "fe 90 04 66 6c 61 67 01 90 05 63 6f 75 6e 74 24 f4 03 90 06 6f 72 69 67 69 6e 25 95 01 90 04 7a"
            "65 72 6f 21 90 03 62 6f 78 85 90 01 78 21 90 01 79 25 95 01 90 01 77 21 90 01 68 24 c8 01 ff ff"
            "ff 85 91 02 90 05 31 2e 30 2e 32 91 04 91 05 91 06 85 91 07 90 05 64 65 6d 6f 32 91 09 86 fd 02"
            "24 01 24 02 fe 91 0a 00 91 0b 24 07 91 0c 21 91 0d 21 91 0e 85 91 0f 24 05 91 10 25 01 91 11 21"
            "91 12 24 09 ff ff ff fe ff 44 4f 4e 45"
        ),
        {'version': 1, 'objects': [{'uid': '1.0.1', 'objclass': 'DemoData', 'objdata': {'name': 'demo', 'items': [], 'flag': True, 'count': 500, 'origin': -75, 'zero': 0, 'box': {'x': 0, 'y': -75, 'w': 0, 'h': 200}}}, {'uid': '1.0.2', 'objclass': 'DemoData', 'objdata': {'name': 'demo2', 'items': [1, 2], 'flag': False, 'count': 7, 'origin': 0, 'zero': 0, 'box': {'x': 5, 'y': -1, 'w': 0, 'h': 9}}}]},
    ),

    # --- varint fixtures ---
    # {"Value": 61}: key via cache-define 90, value unsigned varint 24 3D (0x3D = 61)
    "varint_cached_key": (
        HEADER + bytes.fromhex("90 05 56616C7565  24 3D  FF") + FOOTER,
        {"Value": 61},
    ),
    # {"n": -2}: signed varint 25 03 -> n=3 is odd -> -(3+1)/2 = -2
    "signed_varint": (
        HEADER + bytes.fromhex("81 01 6E  25 03  FF") + FOOTER,
        {"n": -2},
    ),
    # {"x": 254}: varint FE 01 -> 0x7E + (1 << 7) = 254
    "varint_two_bytes": (
        HEADER + bytes.fromhex("81 01 78  24 FE 01  FF") + FOOTER,
        {"x": 254},
    ),
}
