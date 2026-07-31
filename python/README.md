# python/ — models, mitigation designs, and the SDR sweep tool

```
pip install -r requirements.txt
python run_all.py          # -> results/*.png + results/emc_report.txt
```

| File | Contents |
|---|---|
| `parameters.py` | single source of truth: DUT values copied from the buck-converter repo + EMC parasitics (estimates, each flagged with its replacement measurement) |
| `limits.py` | CISPR 32 Class B conducted/radiated masks, dBµV helpers |
| `emissions_model.py` | trapezoid + ring line spectra, LISN/cap/harness network, conducted solve |
| `radiated_model.py` | DM loop-dipole + CM harness-antenna estimates, H-probe transfer |
| `mitigations.py` | snubber (ring-frequency method), damped input filter + Middlebrook check, edge slowing, layout |
| `sdr_scan.py` | bench tool: RTL-SDR sweep → max-hold CSV in dBµV (`--synthetic` runs without hardware) |
| `run_all.py` | everything above → plots + report |

All spectra are line spectra at harmonics of fsw — see the docstring in
`emissions_model.py` for why that makes model and max-hold measurement
directly comparable with no RBW bookkeeping.
