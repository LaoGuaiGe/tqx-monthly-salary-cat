#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_decoupled.py
================
Simulate the DECOUPLED main.c logic on a common 10 ms timebase:

  - Movement: exactly 1 px every 20 ms  (tick % 2 == 0)
  - Dance:    exactly 1 frame every 50 ms (tick % 5 == 0)
  - Redraw once whenever move and/or frame fired (a simultaneous 100 ms
    tick fires both but draws exactly once).

Verifies:
  1. total moves  == ticks // 2,  total frame advances == ticks // 5
  2. phase order strictly A->B->C->A, entry/exit coordinates unchanged
  3. per-phase durations (in moves) unchanged: A=224, B=112, C=225
  4. simultaneous ticks (tick % 10 == 0) run both actions, draw exactly once
  5. no out-of-bounds draw (SPRITE_OFFSCREEN guard semantics preserved)
"""
import sys

MOVE_INTERVAL_MS = 20
FRAME_INTERVAL_MS = 50
TICK_MS = 10
SCR_W, SCR_H = 128, 64
SPR_W, SPR_H = 96, 48
CAT_FRAME_COUNT = 22

SPEC = {
    0: {"start": (-96, 8),  "dx": 1,  "dy": 0,  "exit_x": 128,  "exit_y": None, "dur": 224, "name": "A"},
    1: {"start": (16, -48), "dx": 0,  "dy": 1,  "exit_x": None, "exit_y": 64,  "dur": 112, "name": "B"},
    2: {"start": (128, 64), "dx": -1, "dy": -1, "exit_x": -97,  "exit_y": None, "dur": 225, "name": "C"},
}


def offscreen(x, y):
    return (x + SPR_W <= 0) or (x >= SCR_W) or (y + SPR_H <= 0) or (y >= SCR_H)


def simulate(ticks):
    x, y = -96, 8
    dx, dy = 1, 0
    frame = 0
    phase = 0
    moves = frames = draws = simultaneous = 0
    phase_seq = [0]
    entries = [(0, x, y, 0)]
    exits = []
    skip_draws = 0
    errs = []

    for tick in range(1, ticks + 1):
        moved = framed = False

        # --- movement: 1 px / 20 ms, then phase state machine (mirror main.c) ---
        if tick % (MOVE_INTERVAL_MS // TICK_MS) == 0:
            x += dx
            y += dy
            moves += 1
            moved = True

            if phase == 0 and x > 127:
                exits.append((0, x, y, tick))
                phase = 1; x, y = 16, -48; dx, dy = 0, 1
                entries.append((1, x, y, tick)); phase_seq.append(1)
            elif phase == 1 and y > 63:
                exits.append((1, x, y, tick))
                phase = 2; x, y = 128, 64; dx, dy = -1, -1
                entries.append((2, x, y, tick)); phase_seq.append(2)
            elif phase == 2 and x < -96:
                exits.append((2, x, y, tick))
                phase = 0; x, y = -96, 8; dx, dy = 1, 0
                entries.append((0, x, y, tick)); phase_seq.append(0)

        # --- dance: 1 frame / 50 ms ---
        if tick % (FRAME_INTERVAL_MS // TICK_MS) == 0:
            frame = (frame + 1) % CAT_FRAME_COUNT
            frames += 1
            framed = True

        if moved and framed:
            simultaneous += 1

        # --- redraw once when something changed ---
        if moved or framed:
            draws += 1
            if offscreen(x, y):
                skip_draws += 1
            else:
                x0, x1 = max(x, 0), min(x + SPR_W - 1, SCR_W - 1)
                y0, y1 = max(y, 0), min(y + SPR_H - 1, SCR_H - 1)
                if not (0 <= x0 <= x1 < SCR_W and 0 <= y0 <= y1 < SCR_H):
                    errs.append(f"tick {tick}: drawn region out of bounds "
                                f"({x0},{y0})-({x1},{y1})")

    # ---------------- verification ----------------
    if moves != ticks // 2:
        errs.append(f"moves {moves} != ticks//2 ({ticks // 2})")
    if frames != ticks // 5:
        errs.append(f"frames {frames} != ticks//5 ({ticks // 5})")
    if simultaneous != ticks // 10:
        errs.append(f"simultaneous ticks {simultaneous} != ticks//10 ({ticks // 10})")
    if draws != moves + frames - simultaneous:
        errs.append(f"draws {draws} != moves+frames-simultaneous "
                    f"({moves + frames - simultaneous})")

    # phase order strictly 0->1->2->0...
    expected = [i % 3 for i in range(len(phase_seq))]
    if phase_seq != expected:
        errs.append(f"phase order wrong: {phase_seq[:20]}...")

    # entry coordinates per spec
    for i, (ph, ex, ey, st) in enumerate(entries):
        sx, sy = SPEC[ph]["start"]
        if (ex, ey) != (sx, sy):
            errs.append(f"entry #{i}: {SPEC[ph]['name']} at ({ex},{ey}) tick {st}, "
                        f"expected ({sx},{sy})")

    # exit coordinates per spec
    for ph, ex, ey, st in exits:
        if SPEC[ph]["exit_x"] is not None and ex != SPEC[ph]["exit_x"]:
            errs.append(f"{SPEC[ph]['name']} exit at x={ex} tick {st}, "
                        f"expected {SPEC[ph]['exit_x']}")
        if SPEC[ph]["exit_y"] is not None and ey != SPEC[ph]["exit_y"]:
            errs.append(f"{SPEC[ph]['name']} exit at y={ey} tick {st}, "
                        f"expected {SPEC[ph]['exit_y']}")

    # per-phase-instance durations in MOVES unchanged
    for i, (ph, ex, ey, st) in enumerate(entries[:-1]):
        dur = entries[i + 1][3] - st            # ticks
        dur_moves = dur // 2                     # moves within the phase
        if dur_moves != SPEC[ph]["dur"]:
            errs.append(f"entry #{i}: {SPEC[ph]['name']} duration {dur_moves} moves, "
                        f"expected {SPEC[ph]['dur']}")
    if len(entries) >= 4:
        cyc = entries[3][3] - entries[0][3]     # ticks per full cycle
        if cyc != 2 * (224 + 112 + 225):
            errs.append(f"cycle length {cyc} ticks, "
                        f"expected {2 * (224 + 112 + 225)}")

    return dict(x=x, y=y, phase=phase, frame=frame, moves=moves, frames=frames,
                draws=draws, simultaneous=simultaneous, skip_draws=skip_draws,
                phase_seq=phase_seq, entries=entries, exits=exits, errs=errs)


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 5610
    r = simulate(ticks)
    print(f"simulated {ticks} x 10ms ticks = {ticks * 10} ms")
    print(f"moves={r['moves']} (expected {ticks // 2}), "
          f"frame advances={r['frames']} (expected {ticks // 5})")
    print(f"simultaneous 100ms ticks={r['simultaneous']} (expected {ticks // 10}), "
          f"draws={r['draws']} (expected {r['moves'] + r['frames'] - r['simultaneous']})")
    print(f"draws skipped while fully off-screen: {r['skip_draws']}")
    print(f"final state: phase={r['phase']} x={r['x']} y={r['y']} frame={r['frame']}")
    print(f"phase transitions: {len(r['exits'])} -> "
          f"sequence {''.join(SPEC[p]['name'] for p in r['phase_seq'][:12])}...")
    print("phase entries (all must match spec):")
    for ph, ex, ey, st in r["entries"][:9]:
        print(f"  tick {st:5d}: {SPEC[ph]['name']} start ({ex},{ey})")
    print("phase exits (all must match spec):")
    for ph, ex, ey, st in r["exits"][:9]:
        print(f"  tick {st:5d}: {SPEC[ph]['name']} exit ({ex},{ey})")
    if r["errs"]:
        print("FAILURES:")
        for e in r["errs"][:20]:
            print("  -", e)
        sys.exit(1)
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
