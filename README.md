# pvz2-format-exploration

A small, readable Python decoder for a documented subset of PopCap's **RTON** format, plus the
scripts I used to inspect the container layers of one *Plants vs. Zombies 2* (Chinese version, Android) build:

```
APK -> .rsb.smf (RSLB, LZMA blocks) -> RSB -> RSGP -> RTON files (encrypted; decryption is out of scope)
```

Write-up (English / 中文):

- https://jelly-raytian.github.io/systems/pvz2-resource-analysis/
- https://jelly-raytian.github.io/zh/systems/pvz2-resource-analysis/
- DEV Community (English): https://dev.to/jellyraytian/inside-plants-vs-zombies-2-understanding-rsb-rton-and-rijndael-encryption-24oa
- 知乎 (中文): https://zhuanlan.zhihu.com/p/2100854901811196700

The same text is in [`article/`](article/).

## What is here

| Path | What it is |
|---|---|
| `src/mini_rton/` | The RTON decoder (`decode(bytes) -> dict`). Unknown tags raise `RtonError`; it never guesses. |
| `tests/` | 12 hand-built or encoder-built byte fixtures with expected values, plus error-handling tests. All synthetic. |
| `tools/rslb.py` | Unwraps the `.smf` (RSLB) container: a block table and one raw LZMA1 stream per block. |
| `tools/rsb_probe.py` | Reads an RSB header and its resource-group table. Read-only. |
| `tools/annotate_rton.py` | Prints a byte-by-byte walk-through of an unencrypted RTON. |
| `tools/inspect_build.py` | Container checks on a local APK: unwrap, header, group table, consistency checks. Decrypts and decodes nothing. |
| `docs/rton-scope.md` | Supported tags and how each was checked. |
| `article/` | The article drafts and diagrams. |

## Quick start

```bash
python3 -m unittest discover -s tests      # 14 tests

python3 - <<'PY'
import sys; sys.path.insert(0, "src")
from mini_rton import decode
print(decode(open("some.rton", "rb").read()))
PY
```

To inspect a build you are entitled to use:

```bash
python3 -I tools/inspect_build.py path/to/game.apk
```

## Status

- Synthetic fixtures: all pass.
- Real data: only the container layers of one build were inspected; no game data is decoded in this repository.
- Not implemented yet: floats, 64-bit integers, UTF-8 strings (`82`, `92`, `93`), RTID.
- Integer byte order (16/32-bit) is assumed little-endian and not yet confirmed on real data.

## Notes

- No game files, keys, decryption steps, accounts or captured traffic are included. You need your own copy of the game.
- The format knowledge comes from community research (RETON, Pvz2Tool, PVZ2 Format Lab and others, credited in the article). Nothing here is a new discovery.
- The decoder and scripts were written with the help of an AI coding assistant (Claude Code); I read and understand each function (article §4.1).
- Not affiliated with or endorsed by the game's publishers or operators.

## License

MIT for the code in this repository (see `LICENSE`). Third-party material is cited, not copied.
