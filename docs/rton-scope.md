# Supported RTON tags and how each was checked

Format source: community notes (h3x4n1um/RETON); see the article's references.
All tests use synthetic samples built for this project; no game data is used.

| Tag | Meaning | Synthetic test |
|---|---|---|
| `00` / `01` | false / true | yes |
| `08` / `0A` | int8 / uint8 | yes |
| `10` / `12` | int16 / uint16 (little-endian assumed) | yes |
| `20` | int32 (little-endian assumed) | yes |
| `21` | int32 zero, no payload (the notes mark it as unconfirmed; supported provisionally) | yes |
| `24` | unsigned varint | yes |
| `25` | signed varint (zigzag-style) | yes |
| `81` | length-prefixed string | yes |
| `85` ... `FF` | object | yes |
| `86 FD` n ... `FE` | array | yes |
| `90` / `91` | string cache define / recall | yes |

Not implemented: floats, 64-bit integers, `82` / `92` / `93` UTF-8 strings, RTID (`83`), and the other
"zero" variants (`09`, `0B`, `11`, `13`, `23`, `27`, ...) that the notes mark as uncertain.
Integer byte order is assumed little-endian and has not been confirmed against real data.
