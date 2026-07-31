# Bill of materials — everything, ~$85 total (assuming zero junk box)

## Measurement rig

| Item | Part / spec | Qty | ~CAD | Notes |
|---|---|---|---|---|
| SDR | RTL-SDR Blog v3 | 1 | $45 | must be v3 (direct sampling, TCXO) |
| Coax for probe | RG-316, 30 cm + SMA male | 1 | $6 | one probe + spare |
| Attenuator | 10 dB SMA, 2 W | 2 | $8 | overload control + substitution test |
| LISN inductor | T106-2 toroid + 1.5 m of 18 AWG | 1 | $4 | ~40 turns ≈ 50 µH; verify with NanoVNA/LCR |
| LISN caps | 0.1 µF film 100 V; 1 µF film | 1+1 | $2 | film, not ceramic (stable, low ESL) |
| LISN resistor | 1 kΩ 1/4 W | 1 | — | DC bleed |
| Enclosure | metal tin + 2 BNC/SMA bulkheads + binding posts | 1 | $8 | tin = ground reference |
| Adapters | SMA↔BNC as needed | — | $6 | |

## Mitigation parts (fitted to the buck DUT)

| Item | Part / spec | Qty | ~CAD | Design source |
|---|---|---|---|---|
| Snubber R | 8.2 Ω 1/4 W **carbon film/composition** | 2 | — | `mitigations.py`: R = Z₀ = √(L/C) ≈ 7.7 Ω. Carbon: a wirewound resistor is a coil — at 40 MHz its inductance defeats the snubber |
| Snubber C | 1.5 nF 100 V C0G/NP0 or film, short leads | 2 | $1 | 3×C_node; C0G because X7R loses C with bias and drifts the design |
| Filter choke | 22 µH ≥ 3 A power inductor (e.g. Bourns 2200 series) | 1 | $3 | conducted filter; must not saturate at 2 A + ripple |
| Filter cap | 47 µF 25 V electrolytic | 1 | $1 | line-side |
| Damping cap | 220 µF 25 V electrolytic | 1 | $1 | C_d ≈ 4–5 × C_f |
| Damping R | 1.0 Ω 1/4 W | 1 | — | ≈ √(L/C_f); Middlebrook margin in `results/filter_middlebrook.png` |
| Ferrite | clip-on / snap-on for ~5 mm cable, mix 31 or 43 | 2 | $4 | harness common-mode; 2 turns through if the clamp allows |
| Gate resistor | assorted 47–220 Ω | — | — | edge-slowing experiment (optional, costs efficiency) |

Quantities of 2 where a part will die or get lost. Everything is
through-hole and hand-solderable on purpose, matching the perfboard DUT.

## Already owned / assumed

Buck converter DUT (see the buck-converter repo BOM), 12 V bench supply,
electronic or resistive 2 A load, multimeter, any oscilloscope ≥ 100 MHz
for the ring-frequency measurement (a 20 MHz scope cannot see the 41 MHz
ring — this is the one real equipment constraint in the whole project;
if unavailable, the SDR itself locates f_ring, see test-procedure step 4).
