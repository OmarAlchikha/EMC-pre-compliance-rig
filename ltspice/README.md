# ltspice/ — parasitic ring cross-check

`hot_loop_ring.cir` simulates the switching-edge ring of the buck's hot
loop (C2 → Q1 → D1) with the exact parasitic values from
`python/parameters.py`, bare and with the RC snubber designed in
`python/mitigations.py`.

Runs in LTspice as-is (the `.step` sweeps snubber-in/snubber-out in one
plot). It has also been verified with ngspice-42 (replace `.step` with two
runs, or use `alterparam` in a `.control` block); the measured numbers in
the netlist header come from that run.

## What it validates — and what it can't

| Quantity | Python model | Spice | Verdict |
|---|---|---|---|
| bare ring frequency | 41.1 MHz | 41.1 MHz | exact (same L·C, necessarily) |
| bare Q / decay | Q ≈ 13 | ±0.65 V still ringing at 150 ns | consistent |
| snubbed behavior | f→20 MHz, Q ≈ 0.7 | dead by 150 ns | consistent |
| overshoot amplitude | κ·12 V = 5.9 V (κ=0.5 assumed) | 2.2 V (20 ns edge) | **depends on κ — bench decides** |

The disagreement in the last row is deliberate and documented: overshoot
scales with how hard the commutation edge excites the tank (κ), the one
parameter no simulation can supply. Both tools agree on f₀ and Q — the
only quantities the snubber design actually uses.
