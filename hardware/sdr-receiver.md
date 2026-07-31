# SDR as the measurement receiver — RTL-SDR v3, honestly characterized

## Why an SDR instead of a spectrum analyzer

A swept analyzer is the right tool; it also costs 100× more. The
$40 RTL-SDR covers 500 kHz–1.7 GHz (direct-sampling mode below 24 MHz),
digitizes 2.4 MHz at a time, and `python/sdr_scan.py` stitches sweeps
into a max-hold spectrum. For *pre*-compliance — find the peaks, rank
them, measure mitigation deltas — that is enough, **provided its three
real limitations are engineered around rather than ignored**:

## Limitation 1: 8-bit dynamic range (~48 dB)

The strongest conducted line (~88 dBµV predicted at 300 kHz baseline)
and the CISPR mask (56–66 dBµV) and a useful noise floor must all fit in
the ADC window, and a strong out-of-window line still causes
intermodulation even when the display looks fine.

* Keep tuner gain at 0 dB and add a **fixed 10 dB SMA attenuator** at
  the input as the default conducted setup; `sdr_scan.py` warns when the
  ADC exceeds 95 % of full scale — trust the warning, add attenuation,
  re-run. Attenuation is added to the calibration scalar, so nothing
  else changes.
* Overload check that catches what the clip detector can't: insert
  10 dB more attenuation — every real line must drop by exactly 10 dB.
  Anything that drops more (or less) was an intermod product born inside
  the SDR. This substitution test is run at every new DUT state
  (test-procedure.md step 2) because it costs 30 seconds and removes the
  main way an SDR lies.

## Limitation 2: it reads dBFS, not dBµV

Calibration is one scalar per band: feed a known level (signal
generator, or a crystal-oscillator comb whose lines you compute once on
a scope), read the SDR, `cal_db = known_dBµV − read_dBFS`. Pass it as
`--cal-db`. Linearity between cal point and reading is good to ~±2 dB
over the top 40 dB of the window, which is ample for margin-ranking. The
absolute uncertainty of the whole rig (LISN tolerance + cal + SDR
flatness) is honestly ±4–6 dB — that is why the model+measurement
combination targets *deltas* and *pass/fail with margin*, not
certificate numbers.

## Limitation 3: no quasi-peak detector

CISPR limits are quasi-peak (a charge/discharge-weighted detector that
punishes repetition rate). Implementing QP digitally is possible but
pointless here: **peak ≥ QP always**, and for this DUT's spectrum — a
stationary 100 kHz comb, pulse rate far above the QP corner frequencies
— peak exceeds QP by only a few dB. So `sdr_scan.py` records max-hold
peak and compares against the QP mask: a pass is a real pass with
bonus margin; a marginal fail (< ~5 dB) is a "measure properly" flag,
not a verdict.

## Direct sampling below 24 MHz

The conducted band (150 kHz–30 MHz) sits mostly below the R820T tuner's
range; the RTL-SDR v3 routes HF to the ADC directly (`--direct` flag →
Q-branch direct sampling). Two consequences:

* No tuner preselection: strong AM broadcast can alias in. The LISN's
  50 µH + the 10 dB pad help; verify suspicious lines by powering the
  DUT off — anything that stays is ambient, and `sdr_scan.py`'s
  DUT-off/DUT-on subtraction (test-procedure step 1) formalizes this.
* Sensitivity is lower in direct mode — irrelevant here, the DUT is
  loud and the pad is in anyway.

The 41 MHz ring and the radiated band use the normal tuner path.

## Chain summary

```
conducted:  LISN meas port ──10 dB pad── RTL-SDR v3 (direct sampling <24 MHz)
near-field: H probe ────────────────────  RTL-SDR v3 (tuner path)
            (pad only if the clip warning fires)
```

Both feed `python/sdr_scan.py → results/*.csv` and are compared against
model predictions from `run_all.py` in dB — same units end to end.
