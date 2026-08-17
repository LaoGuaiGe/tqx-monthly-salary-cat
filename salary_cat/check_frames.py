#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-check renderer for the generated 64x32 cat_frames.h (256 B/frame)."""
import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "cat_frames.h"
W, H = 64, 32


def parse(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    frames = {}
    for m in re.finditer(
        r"static\s+const\s+unsigned\s+char\s+cat_frame(\d+)\[\s*256\s*\]\s*=\s*\{(.*?)\};",
        text, re.S):
        body = m.group(2)
        vals = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", body)]
        if len(vals) != 256:
            raise SystemExit(f"frame {m.group(1)}: expected 256 bytes, got {len(vals)}")
        frames[int(m.group(1))] = vals
    return frames


def bbox(frm):
    minx = miny = 10 ** 9
    maxx = maxy = -1
    for y in range(H):
        for x in range(W):
            if (frm[(y // 8) * W + x] >> (y % 8)) & 1:
                minx, maxx = min(minx, x), max(maxx, x)
                miny, maxy = min(miny, y), max(maxy, y)
    return (minx, miny, maxx, maxy)


frames = parse(PATH)
assert len(frames) == 22, f"expected 22 frames, got {len(frames)}"
for i in (0, 7, 14, 21):
    frm = frames[i]
    print(f"----- frame {i} bbox={bbox(frm)} -----")
    for y in range(H):
        row = "".join("#" if (frm[(y // 8) * W + x] >> (y % 8)) & 1 else " "
                      for x in range(W))
        print(row.rstrip())
    print()
print(f"OK: {len(frames)} frames, {W}x{H}")
