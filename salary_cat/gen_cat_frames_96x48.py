#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cat_frames_96x48.py
=======================
Regenerate cat_frames.h: 96x48 sprites (96 cols x 6 pages = 576 bytes/frame),
rescaled 0.75x from the reference 22-frame 128x64 page-format animation in
cat_frames_128x64_backup.h (128 cols x 8 pages = 1024 bytes/frame).

Scale mapping (box filter, source region per output pixel):
  src_cols = [floor(ox * 128 / 96) .. floor((ox+1) * 128 / 96) - 1]   (1 or 2 cols)
  src_rows = [floor(oy * 64 / 48) .. floor((oy+1) * 64 / 48) - 1]     (1 or 2 rows)
Threshold (--threshold):
  half : output pixel lit iff lit-source-pixels / region-area >= 0.5
         (thin 1px source lines survive: a 1x1 region needs 1/1 = 100%)
  third: output pixel lit iff lit-source-pixels / region-area >= 1/3
         (more forgiving, fills gaps but thickens)

Output layout: page format, LSB on top, 96 cols x 6 pages, directly
compatible with OLED_ShowImage().
"""
import argparse
import re
import sys

SRC_W, SRC_H = 128, 64
DST_W, DST_H = 96, 48
FRAME_COUNT = 22
SRC = "cat_frames_128x64_backup.h"
DST = "cat_frames.h"
BYTES_PER_FRAME = 8 * SRC_W            # 1024
DST_BYTES_PER_FRAME = 6 * DST_W        # 576

XSTEP = SRC_W / DST_W                  # 4/3
YSTEP = SRC_H / DST_H                  # 4/3


def parse_src_frames(path):
    """Return list of 22 frames, each a 1024-byte bytearray (page format)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    frames = []
    for m in re.finditer(
        r"static\s+const\s+unsigned\s+char\s+cat_frame(\d+)\[\s*1024\s*\]\s*=\s*\{(.*?)\};",
        text, re.S):
        idx = int(m.group(1))
        body = m.group(2)
        vals = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", body)]
        if len(vals) != BYTES_PER_FRAME:
            raise ValueError(f"frame {idx}: expected {BYTES_PER_FRAME} bytes, got {len(vals)}")
        frames.append((idx, bytes(vals)))
    frames.sort()
    if len(frames) != FRAME_COUNT:
        raise ValueError(f"expected {FRAME_COUNT} frames, parsed {len(frames)}")
    return [b for _, b in frames]


def src_pixel(frm, x, y):
    """Pixel at (x, y) in source frame. (x: 0..127, y: 0..63)"""
    return (frm[(y // 8) * SRC_W + x] >> (y % 8)) & 1


def region(coord, step, max_src):
    """Source interval [a..b] (inclusive) covered by output index 'coord'."""
    a = int(coord * step)
    b = int((coord + 1) * step) - 1
    if b >= max_src:
        b = max_src - 1
    return a, b


def downscale(frm, threshold):
    """0.75x box downscale 128x64 -> 96x48. Returns 576-byte page-format frame."""
    out = bytearray(DST_BYTES_PER_FRAME)
    for oy in range(DST_H):
        ya, yb = region(oy, YSTEP, SRC_H)
        for ox in range(DST_W):
            xa, xb = region(ox, XSTEP, SRC_W)
            lit = 0
            total = (xb - xa + 1) * (yb - ya + 1)
            for sy in range(ya, yb + 1):
                for sx in range(xa, xb + 1):
                    lit += src_pixel(frm, sx, sy)
            # lit / total >= threshold  <=>  lit * denom >= total * num
            ok = lit * 2 >= total if threshold == "half" else lit * 3 >= total
            if ok:
                out[(oy // 8) * DST_W + ox] |= 1 << (oy % 8)
    return bytes(out)


def render_ascii(frm, w=DST_W, h=DST_H):
    """Render a page-format frame as ASCII art (w cols x h rows)."""
    lines = []
    for y in range(h):
        row = []
        for x in range(w):
            row.append("#" if (frm[(y // 8) * w + x] >> (y % 8)) & 1 else " ")
        lines.append("".join(row).rstrip())
    return "\n".join(lines)


def bbox(frm, w=DST_W, h=DST_H):
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if (frm[(y // 8) * w + x] >> (y % 8)) & 1:
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    return (minx, miny, maxx, maxy) if maxx >= 0 else None


def stray_dots(frm, w=DST_W, h=DST_H):
    """Count isolated lit pixels (no lit 8-neighbour) as a noise metric."""
    lit = [[(frm[(y // 8) * w + x] >> (y % 8)) & 1 for x in range(w)] for y in range(h)]
    n = 0
    for y in range(h):
        for x in range(w):
            if not lit[y][x]:
                continue
            alone = True
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h and lit[yy][xx]:
                        alone = False
                        break
                if not alone:
                    break
            if alone:
                n += 1
    return n


def gen_header(frames, threshold):
    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("/*")
    lines.append(" * Salary Cat: 22-frame dance, rescaled 0.75x from the reference")
    lines.append(" * 22-frame 128x64 page-format animation")
    lines.append(" *   (cat_frames_128x64_backup.h, 128 cols x 8 pages).")
    lines.append(" * Scale: box-filter majority vote -- each 96x48 output pixel is")
    lines.append(" * lit iff >= 50% of its source region pixels (1x1/1x2/2x1/2x2")
    lines.append(" * regions, floor-mapped 128->96 cols, 64->48 rows) are lit,")
    lines.append(" * so thin 1px source lines survive.")
    lines.append(" * Layout: page format, LSB on top, 96 cols x 6 pages = 576 bytes/frame,")
    lines.append(" * directly compatible with OLED_ShowImage().")
    lines.append(" */")
    lines.append("")
    lines.append(f"#define CAT_SPRITE_W {DST_W}")
    lines.append(f"#define CAT_SPRITE_H {DST_H}")
    lines.append("")
    for i, frm in enumerate(frames):
        lines.append(f"static const unsigned char cat_frame{i}[{DST_BYTES_PER_FRAME}] = {{")
        for row in range(0, len(frm), 16):
            cols = ", ".join(f"0x{v:02X}" for v in frm[row:row + 16])
            lines.append("    " + cols + ",")
        lines.append("};")
        lines.append("")
    names = ", ".join(f"cat_frame{i}" for i in range(FRAME_COUNT))
    lines.append(f"static const unsigned char *const cat_frames[{FRAME_COUNT}] = {{")
    lines.append("    " + names)
    lines.append("};")
    lines.append("")
    lines.append(f"#define CAT_FRAME_COUNT {FRAME_COUNT}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", choices=("half", "third"), default="half")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--dst", default=DST)
    ap.add_argument("--show", action="store_true",
                    help="render ASCII of frames 0/7/14/21 for self-check")
    args = ap.parse_args()

    src_frames = parse_src_frames(args.src)
    new_frames = [downscale(f, args.threshold) for f in src_frames]

    if args.show:
        for i in (0, 7, 14, 21):
            print(f"----- frame {i} ({DST_W}x{DST_H}, {args.threshold}) "
                  f"bbox={bbox(new_frames[i])} stray={stray_dots(new_frames[i])} -----")
            print(render_ascii(new_frames[i]))
            print()

    with open(args.dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(gen_header(new_frames, args.threshold))
    print(f"wrote {args.dst}: {FRAME_COUNT} frames x {DST_BYTES_PER_FRAME} bytes "
          f"({DST_W}x{DST_H}), threshold={args.threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
