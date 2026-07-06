# Near-field H probe — a shielded loop from RG-316 coax

## Why a *shielded* loop, and why H

A bare wire loop picks up both the magnetic field (by induction) and the
electric field (capacitively, as an antenna). Near a switch node slewing
12 V in 100 ns, the E-field pickup swamps everything and the "current
probe" becomes a dV/dt probe. The classic fix is the shielded
(Moebius/gap) loop: the coax shield encloses the center conductor
everywhere *except* a small gap, so capacitive pickup is intercepted and
shunted while the magnetic flux still links the loop through the gap.
Result: a probe that responds to dI/dt loops — which is exactly what the
hot loop, the thing we're hunting, produces.

An E probe (stub) is the complementary tool for finding dV/dt antennas
(the SW node itself); build both, they cost nothing. But H first: at
sub-centimeter distances over a power converter, the interesting sources
are current loops.

## Build (30 minutes, ~$5 of scrap)

1. Take ~15 cm of RG-316 (RG-174 works; semi-rigid UT-085 is nicer if
   you have it). SMA connector on one end.
2. Form the free end into a **10 mm diameter** loop and bring the tip
   back to the coax body.
3. At the tip: strip 2 mm, solder the **center conductor to the shield
   of the coax body** where it meets the loop base.
4. Cut a **1–2 mm gap in the shield only** (not the center conductor) at
   the top of the loop, diametrically opposite the base. This gap is the
   whole trick — no gap, no flux linkage (the shield would form a
   shorted turn).
5. Sleeve everything in heatshrink; the probe must never short board
   nodes it touches.

```
            shield gap (1–2 mm, center conductor intact)
                    ╭──╮╱
                  ╭─╯  ╰─╮
                  │ 10mm │   ← loop of RG-316
                  ╰─╮  ╭─╯
      tip: center ──╰──╯←── conductor soldered to shield here
      ══════════════╪══════════ coax body ══════ SMA → SDR (50 Ω)
```

## Why 10 mm diameter

Spatial resolution vs sensitivity. Transfer (from `python/radiated_model.py`):
V_out ≈ ω·µ₀·A·H below the L/R corner, so sensitivity scales with area —
but so does the blur: a probe averages the field over roughly its own
diameter, and the features we need to separate (hot loop vs gate loop vs
output cap) are 1–3 cm apart on the perfboard. 10 mm resolves them and
still delivers ~7 mV (77 dBµV) at the ring frequency 1 cm above the hot
loop — 40+ dB over the SDR noise floor (`results/probe_signal.png`).
No preamp needed; smaller would be sharper but might want one.

Self-inductance of a 10 mm loop of thin coax is ~25 nH, so the L/50 Ω
corner sits near 320 MHz — everything this rig measures is in the clean
+20 dB/dec "derivative" region below it (`results/probe_transfer.png`).

## Calibration — and why we mostly don't

The probe factor curve in `results/probe_transfer.png` is analytic and
good to a few dB. For **absolute** field numbers you'd calibrate by
substitution: drive a known RF current (signal generator + 50 Ω + series
resistor, compute I = V/R) through a straight wire, hold the probe at a
jig-fixed distance, and compare measured vs computed H = I/(2πr).

But the near field of a converter varies ~20 dB per cm of probe position,
so absolute near-field numbers are close to meaningless anyway. The probe
earns its keep as a **relative, differential instrument**:

* *Where* — scan the board, find which loop lights up at which frequency
  (source localization).
* *Before/after* — fix the probe position with a jig (a scrap of
  perfboard and hot glue is fine), apply one mitigation, measure the
  delta in dB. Position uncertainty cancels in the subtraction as long as
  nothing moves.

That's why `sdr_scan.py` reports deltas and the test procedure
(test-procedure.md) never asks for an absolute A/m value.
