#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_72.py
=========
Simulate the three-phase screensaver state machine of main.c **verbatim**
(macro-derived phase coordinates, W=72 from cat_frames.h) on a 10 ms
timebase for >= 2 full phase cycles and verify:

  1. Rhythm unchanged: exactly 1 px move every 20 ms (2 ticks), exactly
     1 dance frame every 50 ms (5 ticks); move+frame coincide every 100 ms.
  2. Phase order strictly A -> B -> C -> A -> ... (never skips/repeats).
  3. Entry/exit positions exactly per main.c (macro-derived, W=72):
       A: start (-CAT_SPRITE_W, 8) = (-72, 8),   exit when x > 127 (x = 128)
       B: start ((SCR_W-CAT_SPRITE_W)/2, -48) = (28, -48),
                                                  exit when y > 63  (y = 64)
       C: start (128, 64),                        exit when x < -CAT_SPRITE_W
                                                  (first x = -73)
  4. No out-of-bounds: every OLED_ShowImage write index stays inside
     DisplayBuf[8][128] (the driver clips negative/oversize coordinates;
     we replicate its guards and assert every index touched is in range).
"""
import sys

SCR_W, SCR_H = 128, 64
SPR_W, SPR_H = 72, 48          # from cat_frames.h (CAT_SPRITE_W/H)
FRAME_COUNT = 22
TICK_MS = 10
MOVE_INTERVAL_MS = 20
FRAME_INTERVAL_MS = 50

# main.c phase coordinates, macro-derived (mirror the current source)
A_START = (-SPR_W, 8)                          # x = -CAT_SPRITE_W
B_START = ((SCR_W - SPR_W) // 2, -SPR_H)       # x = (SCR_W-CAT_SPRITE_W)/2 = 28
C_START = (SCR_W, SCR_H)                       # x = SCR_W, y = SCR_H

EXP_ENTRY = {0: A_START, 1: B_START, 2: C_START}
# expected trigger positions (first coordinate value that fires the exit)
EXP_EXIT = {"A": (SCR_W, None), "B": (None, SCR_H), "C": (-SPR_W - 1, None)}


def offscreen(x, y):
    return (x + SPR_W <= 0) or (x >= SCR_W) or (y + SPR_H <= 0) or (y >= SCR_H)


def show_image_write_indices(x, y, w, h):
    """Yield (page, col) indices that OLED_ShowImage would write, applying
    exactly the same guards as OLED.c (negative coords skipped, etc.).
    Any yielded index outside DisplayBuf[8][128] is an OOB bug."""
    if w == 0 or h == 0 or x > SCR_W - 1 or y > SCR_H - 1:
        return
    writes = []
    # main 2-page loop (mirrors OLED_ShowImage)
    for j in range((h - 1) // 8 + 1):
        for i in range(w):
            cx = x + i
            cy = y + j * 8
            if cx < 0 or cx > SCR_W - 1 or cy < 0 or cy > SCR_H - 1:
                continue
            writes.append((cy // 8, cx))
            if cy + 8 <= SCR_H - 1:
                writes.append((cy // 8 + 1, cx))
    # Y < 0 extra pass (mirrors the tail of OLED_ShowImage)
    if y < 0:
        for i in range(w):
            cx = x + i
            if cx < 0 or cx > SCR_W - 1:
                continue
            writes.append((0, cx))
    return writes


def simulate(ticks):
    x, y = A_START
    dx, dy = 1, 0
    phase = 0                       # 0=A, 1=B, 2=C
    frame = 0
    tick = 0
    entries = [(0, x, y, 0)]        # (tick, x, y, phase)
    exits = []
    phase_seq = ["A"]
    move_events = []                # ticks where a move happened
    frame_events = []               # ticks where a frame change happened
    oob = []
    drawn = 0

    while tick < ticks:
        tick += 1
        moved = framed = 0

        if tick % (MOVE_INTERVAL_MS // TICK_MS) == 0:     # every 2 ticks
            x += dx
            y += dy
            moved = 1
            move_events.append(tick)
            if phase == 0 and x > 127:
                exits.append((tick, "A", x, y))
                phase, x, y, dx, dy = 1, *B_START, 0, 1
                entries.append((tick, x, y, phase))
                phase_seq.append("B")
            elif phase == 1 and y > 63:
                exits.append((tick, "B", x, y))
                phase, x, y, dx, dy = 2, *C_START, -1, -1
                entries.append((tick, x, y, phase))
                phase_seq.append("C")
            elif phase == 2 and x < -SPR_W:               # x < -CAT_SPRITE_W
                exits.append((tick, "C", x, y))
                phase, x, y, dx, dy = 0, *A_START, 1, 0
                entries.append((tick, x, y, phase))
                phase_seq.append("A")

        if tick % (FRAME_INTERVAL_MS // TICK_MS) == 0:    # every 5 ticks
            frame = (frame + 1) % FRAME_COUNT
            framed = 1
            frame_events.append(tick)

        if moved or framed:
            if not offscreen(x, y):
                drawn += 1
                ws = show_image_write_indices(x, y, SPR_W, SPR_H)
                for pg, col in ws:
                    if not (0 <= pg < 8 and 0 <= col < SCR_W):
                        oob.append((tick, phase, x, y, pg, col))

    return dict(x=x, y=y, phase=phase, frame=frame, tick=tick,
                phase_seq=phase_seq, entries=entries, exits=exits,
                move_events=move_events, frame_events=frame_events,
                oob=oob, drawn=drawn)


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 7000   # 70 s >= 6 cycles
    r = simulate(ticks)
    errs = []

    # ---- 1. rhythm ----
    if r["move_events"] != list(range(2, ticks + 1, 2)):
        errs.append("move event ticks differ from every-2-ticks (20 ms) grid")
    if r["frame_events"] != list(range(5, ticks + 1, 5)):
        errs.append("frame event ticks differ from every-5-ticks (50 ms) grid")

    # ---- 2. phase order A->B->C->A ----
    expected_seq = (["A", "B", "C"] * (len(r["phase_seq"]) // 3 + 2))
    if r["phase_seq"] != expected_seq[:len(r["phase_seq"])]:
        errs.append(f"phase order wrong: {r['phase_seq'][:12]}")

    # ---- 3. entries / exits exactly per macro-derived main.c ----
    for tk, ex, ey, ph in r["entries"]:
        if (ex, ey) != EXP_ENTRY[ph]:
            errs.append(f"entry tick {tk}: phase {ph} at ({ex},{ey}), "
                        f"expected {EXP_ENTRY[ph]}")
    for tk, ph, ex, ey in r["exits"]:
        exx, eyy = EXP_EXIT[ph]
        ok = (exx is not None and ex == exx) or (eyy is not None and ey == eyy)
        if not ok:
            errs.append(f"exit tick {tk}: {ph} at ({ex},{ey})")

    # ---- 4. no out-of-bounds writes ----
    if r["oob"]:
        errs.append(f"{len(r['oob'])} out-of-bounds framebuffer writes, "
                    f"e.g. {r['oob'][:3]}")

    # ---- summary ----
    print(f"simulated {ticks} ticks = {ticks * TICK_MS} ms "
          f"({len(r['exits'])} phase transitions, "
          f"{len([e for e in r['exits'] if e[1]=='A'])} full cycles, "
          f"{r['drawn']} draws)")
    print(f"final state: phase={r['phase']} x={r['x']} y={r['y']} "
          f"frame={r['frame']}")
    print(f"phase sequence: {''.join(r['phase_seq'][:12])}...")
    print("macro-derived phase coords (main.c now uses these, W=72):")
    print(f"  A entry x = -CAT_SPRITE_W = {A_START[0]}")
    print(f"  B entry x = (SCR_W-CAT_SPRITE_W)/2 = {B_START[0]}")
    print(f"  C exit  x < -CAT_SPRITE_W  => first x = {-SPR_W - 1}")

    if errs:
        print("FAILURES:")
        for e in errs[:20]:
            print("  -", e)
        sys.exit(1)
    print("ALL CHECKS PASSED (rhythm, phase order, macro coords, no OOB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
