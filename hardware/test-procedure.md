# Test procedure — staged, each step falsifies something specific

Convention as in the buck repo: every stage states what a wrong result
means. Log everything to `measurements/` as CSVs from `sdr_scan.py` with
the naming `NN_<stage>_<variant>.csv`.

## Step 0 — rig self-test (DUT absent)

1. Sweep the LISN impedance curve with a NanoVNA from the DUT port
   (measurement port terminated in 50 Ω). Expect the 50 µH ∥ 50 Ω curve:
   ~24 Ω at 150 kHz rising to ~48 Ω by 2 MHz. Off by ×2 → wrong turn
   count or a shorted turn on the toroid.
2. SDR + pad + LISN, supply on, **DUT disconnected**: record the ambient
   baseline (`00_ambient.csv`). AM broadcast lines will be visible in
   direct-sampling mode — that's normal; they must simply be logged so
   they're never attributed to the DUT.
3. H probe held over a running Arduino/oscillator (any known clock):
   its harmonics must appear and must *drop* when the probe is rotated
   90° (loop plane parallel to the current). No orientation null → the
   shield gap is missing or the tip weld shorted the gap.

## Step 1 — DUT on, conducted baseline

DUT at 12 V / 2 A resistive load, warmed 5 min (electrolytic ESR moves).

    python sdr_scan.py --direct --cal-db <cal> --out ../measurements/01_conducted_baseline.csv

* Expect a 100 kHz comb; predicted worst line ~88 dBµV near 300 kHz,
  ~33 dB over the Class B mask (`results/conducted_baseline.png`).
* Lines present with DUT off = ambient (compare `00_ambient.csv`).
* **Comb spacing ≠ 100 kHz** → read the actual fsw off pin 5 of the
  TL494 and update `parameters.py` before comparing anything to the
  model.

## Step 2 — receiver honesty check (every new DUT state)

Insert the second 10 dB pad. Every line must fall by 10 ± 1 dB.
A line that falls ~20 dB was an SDR intermod product — raise fixed
attenuation and redo the affected sweep. 30 seconds; not skippable.

## Step 3 — near-field map

H probe + SDR, tuner path. Grid-scan the board at ~1 cm height, 2 cm
pitch, max-hold per position; note the frequency and position of every
hotspot. Expected from the model: the hot loop lights up at f_ring
(~41 MHz predicted) and harmonics of 100 kHz; the output side should be
quiet (if the *output* leads light up, HF is escaping through L1's
inter-winding capacitance — a finding worth its own note).

## Step 4 — measure the real ring, redesign the snubber

1. Scope (or probe+SDR peak) on the SW node: record bare f_ring.
2. Solder a known C_add = 470 pF C0G across D1: record the new, lower
   f_ring′.
3. Two equations, two unknowns:
   C_node = C_add / ((f_ring/f_ring′)² − 1), L_loop = 1/((2π·f_ring)²·C_node).
4. Feed both into `parameters.py`, rerun `run_all.py` — the snubber R
   and C in the report are now *designed from measurement*. Fit them
   (short leads, directly across D1).
5. Record `04_conducted_snubbed.csv` and a near-field spectrum at the
   jig position. Expected: ring hump gone in near field and >30 MHz;
   **conducted band nearly unchanged** (the model says the snubber is
   not a conducted fix — this stage tests that claim).
6. Check the snubber R temperature by touch/IR after 10 min: warm is
   fine (22 mW predicted), hot means the ring was much bigger than
   modeled — measure κ and update.

## Step 5 — input filter

Fit the 22 µH / 47 µF / (220 µF + 1 Ω) filter between LISN and DUT input.

1. **Stability first, emissions second**: scope the 12 V rail at the DUT
   input, apply a 0.5 → 2 A load step. Ringing that grows or persists =
   the input rail is oscillating (Middlebrook margin gone — wrong
   damping parts?). A clean damped edge = proceed.
2. Verify Vout regulation and efficiency are unchanged (filter DCR
   costs ~0.24 W at 2 A — expect ~1 efficiency point, no more).
3. `05_conducted_filtered.csv`. Expected: whole comb down 40–55 dB,
   worst margin ≈ +19 dB (`results/conducted_mitigated.png`).

## Step 6 — harness ferrite + layout

1. Clip ferrite(s) on the input harness, 2 turns if possible:
   `06a_conducted_ferrite.csv` + near-field at jig. Expect: little
   change conducted (< a few dB), visible drop 60–150 MHz in near field
   (the CM resonance region).
2. If the hot-loop rebuild is undertaken (D1 across Q1, return
   underneath): re-do step 3's map. Expect the f_ring hotspot down
   ~12 dB (area) plus whatever the snubber already took.

## Step 7 — closing the loop on the model

For each variant, compute measured deltas (dB, per band) and tabulate
against the model's predicted deltas. Agreement to ±6 dB on *deltas* is
a pass for this class of model; systematic disagreement in a band is a
finding — chase it (κ? C_stray? harness geometry?) and update
`parameters.py`. The deliverable of the whole project is that table.
