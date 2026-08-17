#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulate the DVD-style bounce of the 64x32 sprite on the 128x64 OLED for
N steps and verify: position always in bounds and every screen edge reached.
Mirrors the logic in main.c exactly (same order of checks).
"""
import sys

SCR_W, SCR_H = 128, 64
SPR_W, SPR_H = 64, 32
STEPS = 200
X_MAX, Y_MAX = SCR_W - SPR_W, SCR_H - SPR_H   # 64, 32


def simulate(steps=STEPS):
    x, y = 0, 0
    dx, dy = 1, 1
    hits = {"x0": False, "xmax": False, "y0": False, "ymax": False}
    visited = set()
    ok = True
    for step in range(1, steps + 1):
        x += dx
        y += dy
        if x <= 0:
            x = 0
            dx = 1
            hits["x0"] = True
        if x + SPR_W >= SCR_W:
            x = X_MAX
            dx = -1
            hits["xmax"] = True
        if y <= 0:
            y = 0
            dy = 1
            hits["y0"] = True
        if y + SPR_H >= SCR_H:
            y = Y_MAX
            dy = -1
            hits["ymax"] = True
        if not (0 <= x <= X_MAX and 0 <= y <= Y_MAX):
            print(f"[FAIL] step {step}: out of bounds x={x} y={y}")
            ok = False
        if not (0 <= x + SPR_W - 1 < SCR_W and 0 <= y + SPR_H - 1 < SCR_H):
            print(f"[FAIL] step {step}: sprite overflows x+W={x + SPR_W} y+H={y + SPR_H}")
            ok = False
        visited.add((x, y))
    return ok, hits, visited


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else STEPS
    ok, hits, visited = simulate(steps)
    print(f"steps simulated: {steps}")
    print(f"position always in bounds (0<=x<={X_MAX}, 0<=y<={Y_MAX}): {ok}")
    print("edge hits:", ", ".join(f"{k}={v}" for k, v in hits.items()))
    all_edges = all(hits.values())
    print(f"all four edges reached: {all_edges}")
    print(f"distinct positions visited: {len(visited)}")
    sys.exit(0 if (ok and all_edges) else 1)


if __name__ == "__main__":
    main()
