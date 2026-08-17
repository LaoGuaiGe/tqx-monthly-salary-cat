#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cat_frames.py
=================
Shrink the 22-frame 128x64 "Salary Cat" page-format frames down to 64x32
sprites (2x2 block downscale) and regenerate cat_frames.h.

Downscale algorithm (choose with --mode):
  majority : 2x2 block majority vote -- output pixel lit iff >=2 of the 4
             source pixels are lit (keeps thin lines, discards noise).
  dilate   : output pixel lit iff ANY of the 4 source pixels is lit
             (never drops a line, but thickens outlines).

Source layout (128x64, page format, LSB on top):
  frame[page * 128 + col], page = y/8, bit = (byte >> (y%8)) & 1
Target layout (64x32, page format, LSB on top):
  frame[page * 64 + col], page = y/8, bit = (byte >> (y%8)) & 1
"""
import argparse
import re
import sys

SRC_W, SRC_H = 128, 64
DST_W, DST_H = 64, 32
FRAME_COUNT = 22
SRC = "cat_frames.h"
DST = "cat_frames.h"
BYTES_PER_FRAME = 8 * 128          # 1024
DST_BYTES_PER_FRAME = 4 * 64       # 256


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


def downscale(frm, mode):
    """2x2 block downscale 128x64 -> 64x32. Returns 256-byte page-format frame."""
    out = bytearray(DST_BYTES_PER_FRAME)
    for oy in range(DST_H):
        for ox in range(DST_W):
            c = (src_pixel(frm, 2 * ox, 2 * oy) +
                 src_pixel(frm, 2 * ox + 1, 2 * oy) +
                 src_pixel(frm, 2 * ox, 2 * oy + 1) +
                 src_pixel(frm, 2 * ox + 1, 2 * oy + 1))
            lit = c >= 2 if mode == "majority" else c >= 1
            if lit:
                out[(oy // 8) * DST_W + ox] |= 1 << (oy % 8)
    return bytes(out)


def render_ascii(frm, w=DST_W, h=DST_H):
    """Render a page-format frame as ASCII art (64 cols x 32 rows)."""
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


def gen_header(frames, mode):
    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("/*")
    lines.append(" * Salary Cat: 22-frame dance, shrunk from the reference 22-frame")
    lines.append(" * 128x64 page-format animation down to 64x32 sprites (2x2 block")
    lines.append(f" * {'majority vote' if mode == 'majority' else 'dilation (any-of-4)'} "
                 f"downscale, width/height halved).")
    lines.append(" * Source: reference project YueXinMao[22][8][128] (OLED_Data.c),")
    lines.append(" * thin-outline line-art cat, pure black background.")
    lines.append(" * Layout: page format, LSB on top, 64 cols x 4 pages = 256 bytes/frame,")
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
    ap.add_argument("--mode", choices=("majority", "dilate"), default="majority")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--dst", default=DST)
    ap.add_argument("--show", action="store_true",
                    help="render ASCII of frames 0/7/14/21 for self-check")
    args = ap.parse_args()

    src_frames = parse_src_frames(args.src)
    new_frames = [downscale(f, args.mode) for f in src_frames]

    if args.show:
        for i in (0, 7, 14, 21):
            print(f"----- frame {i} (64x32, {args.mode}) bbox={bbox(new_frames[i])} -----")
            print(render_ascii(new_frames[i]))
            print()

    with open(args.dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(gen_header(new_frames, args.mode))
    print(f"wrote {args.dst}: {FRAME_COUNT} frames x {DST_BYTES_PER_FRAME} bytes "
          f"({DST_W}x{DST_H}), mode={args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
