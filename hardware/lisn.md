# LISN — 50 µH line impedance stabilization network (DC-rail, single line)

## Why conducted measurements need this at all

A conducted-emissions number is meaningless without a defined source
impedance: the noise current the DUT pushes into its supply develops a
voltage across *whatever the supply's impedance happens to be* — a bench
supply might be 0.01 Ω at 150 kHz or 30 Ω at 10 MHz depending on its
output filter and the lead dressing. The LISN pins that impedance to the
standard 50 µH ∥ 50 Ω curve (CISPR 16-1-2), isolates the DUT from
whatever garbage rides on the bench supply, and hands the noise voltage
to the receiver across a defined 50 Ω. Repeatability is the entire point:
the same board must read the same on my bench and on the test house's.

## Circuit (one line; duplicate for a full V-network later)

```
 supply + ────●───L1 50 µH───●──────────── DUT +
              │              │
          C2 1 µF        C1 0.1 µF
              │              │
 supply − ────●              ●───R1 1 kΩ──── GND
 (= GND)                     │
                             ●───── BNC to SDR (50 Ω input = the
                                    detector impedance; R1 bleeds DC
                                    when nothing is connected)
```

* **L1 50 µH**: iron-powder toroid (T106-2 or similar), ~40 turns of
  18 AWG — must carry the DUT's 2 A DC without saturating and without
  cooking. Air-core (wound on a pill bottle) also works and *cannot*
  saturate; it's just bulkier.
* **C1 0.1 µF** couples the RF to the measurement port and blocks the
  12 V DC from the SDR. With the 50 Ω receiver it forms a 32 kHz
  high-pass — invisible at 150 kHz where the band starts.
* **C2 1 µF** shorts bench-supply noise to ground on the supply side.
* Build it in a tin (cookie/Altoids); the box is the ground reference
  and the bulkhead BNC/SMA mounts on it.

**The 50 Ω termination is part of the network.** If the SDR is not
connected, connect a 50 Ω load, or the measurement-port impedance (and
the reading) is undefined.

## Why 50 µH / why not a certified LISN

50 µH corresponds to the CISPR 16 mains network used by CISPR 32 — the
mask this project tests against (automotive CISPR 25 uses 5 µH; swapping
one inductor converts the rig). A calibrated commercial LISN is a few
thousand dollars; this one is ~$15 and its impedance curve can be swept
with a NanoVNA and compared against the CISPR tolerance mask (±20 %).
That sweep — not faith in the schematic — is what makes the numbers
citable as *pre*-compliance. Log it in `measurements/` when built.

## Safety / practical notes

* 12 V DC rig, so no mains-safety issue — but note for the record: a
  mains LISN is a different, genuinely dangerous build (lethal voltages
  on exposed terminals, earth-leakage trips) and is out of scope here.
  This is the DC-rail variant on purpose.
* Keep DUT-side leads to the board short and fixed with the same
  routing every run; harness geometry is part of the measurement
  (`L_HARNESS` in the model at 500 nH — measure yours and update).
* The SDR sees the full 12 V step if the DUT input is hot-plugged with
  the coupling cap charged — hot-plug the supply side, not the DUT side,
  or keep 10 dB of attenuation inline (see sdr-receiver.md, which wants
  it anyway).
