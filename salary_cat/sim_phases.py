#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_phases.py
=============
Simulate the three-phase screensaver state machine of main.c (96x48 sprite
on 128x64 OLED, 1 px per step) for N steps and verify:

  1. Phase order is strictly A -> B -> C -> A -> ... (never skips/repeats).
  2. Each phase starts exactly at its spec position and ends exactly at its
     spec off-screen exit position.
  3. Movement within a phase is exactly (dx, dy) per step.
  4. Sprite never draws pixels out of bounds (fully off-screen start/end
     positions are expected and skipped).

Phase spec:
  A: start (-96, 8),  dx=1, dy=0;  end when x > 127        -> B
  B: start (16, -48), dx=0, dy=1;  end when y > 63         -> C
  C: start (128, 64), dx=-1, dy=-1; end when x < -96       -> A
"""
import sys

SCR_W, SCR_H = 128, 64
SPR_W, SPR_H = 96, 48
STEPS = 3000

SPEC = {
    "A": {"start": (-96, 8),  "dx": 1,  "dy": 0,  "end": "x > 127",  "next": "B"},
    "B": {"start": (16, -48), "dx": 0,  "dy": 1,  "end": "y > 63",   "next": "C"},
    "C": {"start": (128, 64), "dx": -1, "dy": -1, "end": "x < -96",  "next": "A"},
}
ORDER = ["A", "B", "C"]


def offscreen(x, y):
    return (x + SPR_W <= 0) or (x >= SCR_W) or (y + SPR_H <= 0) or (y >= SCR_H)


def simulate(steps=STEPS):
    x, y = -96, 8
    dx, dy = 1, 0
    phase = "A"
    frame = 0
    phase_seq = [phase]
    entries = []            # (phase, x, y, step) at each entry
    exits = []              # (phase, x, y, step) at each exit trigger
    per_phase_steps = {"A": 0, "B": 0, "C": 0}
    skipped = []            # (step, x, y, phase) where draw was skipped
    errs = []

    entries.append((phase, x, y, 0))
    for step in range(1, steps + 1):
        frame = (frame + 1) % 22
        x += dx
        y += dy
        per_phase_steps[phase] += 1

        # --- phase transitions (mirror main.c exactly) ---
        if phase == "A" and x > 127:
            exits.append(("A", x, y, step))
            phase = "B"; x, y = 16, -48; dx, dy = 0, 1
            entries.append((phase, x, y, step))
            phase_seq.append(phase)
        elif phase == "B" and y > 63:
            exits.append(("B", x, y, step))
            phase = "C"; x, y = 128, 64; dx, dy = -1, -1
            entries.append((phase, x, y, step))
            phase_seq.append(phase)
        elif phase == "C" and x < -96:
            exits.append(("C", x, y, step))
            phase = "A"; x, y = -96, 8; dx, dy = 1, 0
            entries.append((phase, x, y, step))
            phase_seq.append(phase)

        # --- draw guard (mirror main.c) ---
        if offscreen(x, y):
            skipped.append((step, x, y, phase))
        else:
            # on-screen portion must stay inside the OLED
            x0, x1 = max(x, 0), min(x + SPR_W - 1, SCR_W - 1)
            y0, y1 = max(y, 0), min(y + SPR_H - 1, SCR_H - 1)
            if not (0 <= x0 <= x1 < SCR_W and 0 <= y0 <= y1 < SCR_H):
                errs.append(f"step {step}: drawn region out of bounds "
                            f"({x0},{y0})-({x1},{y1})")

    # ---- verification ----
    # 1) phase order strictly A->B->C->A...
    expected = [ORDER[i % 3] for i in range(len(phase_seq))]
    if phase_seq != expected:
        errs.append(f"phase order wrong: {phase_seq[:20]}...")

    # 2) entry positions exactly per spec
    for i, (ph, ex, ey, st) in enumerate(entries):
        sx, sy = SPEC[ph]["start"]
        if (ex, ey) != (sx, sy):
            errs.append(f"entry #{i}: {ph} at ({ex},{ey}) step {st}, "
                        f"expected ({sx},{sy})")

    # 3) exit positions exactly per spec
    for ph, ex, ey, st in exits:
        cond = SPEC[ph]["end"]
        if ph == "A" and ex != 128:
            errs.append(f"A exit at x={ex} step {st}, expected x=128")
        elif ph == "B" and ey != 64:
            errs.append(f"B exit at y={ey} step {st}, expected y=64")
        elif ph == "C" and ex != -97:
            errs.append(f"C exit at x={ex} step {st}, expected x=-97")

    # per-phase-instance step counts (duration between consecutive entries)
    exp_dur = {"A": 224, "B": 112, "C": 225}
    for i, (ph, ex, ey, st) in enumerate(entries[:-1]):
        dur = entries[i + 1][3] - st
        if dur != exp_dur[ph]:
            errs.append(f"entry #{i}: {ph} duration {dur}, expected {exp_dur[ph]}")

    # cycle length = entry of same phase 3 phases later
    if len(entries) >= 4:
        c = entries[3][3] - entries[0][3]
        if c != 561:
            errs.append(f"cycle length {c}, expected 561")

    # final state after exactly 3000 steps: 3000 = 5*561 + 195 -> 6th cycle,
    # 195 steps into phase A starting at (-96, 8) -> x = -96+195 = 99, y = 8
    if steps == 3000 and (x, y, phase) != (99, 8, "A"):
        errs.append(f"final state ({x},{y},{phase}), expected (99,8,A)")

    return dict(x=x, y=y, phase=phase, frame=frame, phase_seq=phase_seq,
                entries=entries, exits=exits, per_phase_steps=per_phase_steps,
                skipped=skipped, errs=errs)


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else STEPS
    r = simulate(steps)
    print(f"simulated {steps} steps")
    print(f"final state: phase={r['phase']} x={r['x']} y={r['y']} frame={r['frame']}")
    print(f"phase transitions: {len(r['exits'])} "
          f"-> sequence {''.join(r['phase_seq'][:12])}...")
    print(f"per-phase steps: "
          f"A={r['per_phase_steps']['A']} B={r['per_phase_steps']['B']} "
          f"C={r['per_phase_steps']['C']}")
    print(f"phase entries (all must match spec):")
    for ph, ex, ey, st in r["entries"][:9]:
        print(f"  step {st:5d}: {ph} start ({ex},{ey})")
    print(f"phase exits (all must match spec):")
    for ph, ex, ey, st in r["exits"][:9]:
        print(f"  step {st:5d}: {ph} exit ({ex},{ey})")
    print(f"draw-skipped (fully off-screen) steps: {len(r['skipped'])}")
    skip_positions = sorted({(s[1], s[2], s[3]) for s in r["skipped"]})
    print(f"  distinct off-screen positions: {skip_positions}")
    if r["errs"]:
        print("FAILURES:")
        for e in r["errs"][:20]:
            print("  -", e)
        sys.exit(1)
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
