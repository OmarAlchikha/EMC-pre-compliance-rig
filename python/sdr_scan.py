"""SDR sweep tool: max-hold spectrum in dBuV from an RTL-SDR.

Usage:
    python sdr_scan.py --start 150e3 --stop 30e6 --out results/scan.csv
    python sdr_scan.py --synthetic baseline   # no hardware: model + receiver
                                              # effects, for pipeline testing

Measurement approach (why it looks like this -- details in
hardware/sdr-receiver.md):

* SWEEP of 2.4 MS/s captures: the RTL-SDR spans ~2 MHz per capture, so the
  band is covered by retuning in 1.8 MHz steps (overlap trims the filter
  skirts and the DC spike at the tuner center).
* MAX-HOLD of Welch periodograms per dwell: the DUT's lines are stationary
  but drift a little (TL494 RC oscillator, ~+-2 %); max-hold across a
  ~0.5 s dwell is the poor-man's peak detector. Peak >= quasi-peak, so a
  pass against the QP mask is conservative (see limits.py).
* RBW: FFT bin width is set near 9 kHz (CISPR band B) so NARROWBAND lines
  read the same as they would on a compliance receiver. For the 100 kHz
  harmonic comb this barely matters (isolated lines), but keeping the RBW
  honest costs nothing and removes a whole argument.
* CALIBRATION is a single scalar per band: cal_db = (known dBuV) - (raw
  dBFS reading) taken from a signal generator or the LISN's cal port at
  one amplitude. 8-bit SDR linearity is good over ~40 dB; beyond that,
  re-cal with the front-end attenuator switched in.

Requires pyrtlsdr only for real captures; --synthetic runs anywhere.
"""

import argparse
import csv
import os
import sys

import numpy as np


def welch_db(iq, nfft):
    """Averaged periodogram of one dwell, Hann window, 50 % overlap.
    Returns dBFS per bin, DC bin blanked (RTL-SDR center spike)."""
    win = np.hanning(nfft)
    scale = 1.0 / (win.sum())
    segs = []
    step = nfft // 2
    for i in range(0, len(iq) - nfft + 1, step):
        seg = np.fft.fftshift(np.fft.fft(iq[i:i + nfft] * win)) * scale
        segs.append(np.abs(seg) ** 2)
    psd = np.mean(segs, axis=0)
    mid = nfft // 2
    psd[mid - 2:mid + 3] = psd[mid - 5]      # blank the DC spike
    return 10 * np.log10(np.maximum(psd, 1e-20))


def scan_hardware(f_start, f_stop, fs, dwell_s, cal_db, direct):
    from rtlsdr import RtlSdr                 # import here: optional dep
    sdr = RtlSdr()
    sdr.sample_rate = fs
    if direct:
        sdr.set_direct_sampling(2)            # Q-branch: HF below 24 MHz
    sdr.gain = 0                              # start deaf; overload check below
    step = fs * 0.75
    nfft = int(round(fs / 9e3))               # bin width ~ CISPR band-B RBW
    freqs_all, dbuv_all = [], []
    fc = f_start + step / 2
    while fc - step / 2 < f_stop:
        sdr.center_freq = fc
        iq = sdr.read_samples(int(fs * dwell_s))
        if np.max(np.abs(iq)) > 0.95:
            print(f"  WARNING: ADC near clipping at {fc/1e6:.2f} MHz -- "
                  "add front-end attenuation and re-run", file=sys.stderr)
        db = welch_db(iq, nfft)
        f_axis = fc + np.fft.fftshift(np.fft.fftfreq(nfft, 1 / fs))
        keep = (np.abs(f_axis - fc) < step / 2) & (f_axis >= f_start) & \
               (f_axis <= f_stop)
        freqs_all.append(f_axis[keep])
        dbuv_all.append(db[keep] + cal_db)
        fc += step
    sdr.close()
    return np.concatenate(freqs_all), np.concatenate(dbuv_all)


def scan_synthetic(variant):
    """Model spectrum + receiver effects (noise floor, line jitter) so the
    full pipeline runs and plots without hardware."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from emissions_model import conducted_spectrum
    from limits import dbuv
    kw = dict(baseline={}, snubbed={"snubbed": True},
              filtered={"with_filter": True},
              all={"snubbed": True, "with_filter": True})[variant]
    f_n, v = conducted_spectrum(**kw)
    rng = np.random.default_rng(1)
    f_axis = np.arange(150e3, 30e6, 3e3)
    floor = 12.0 + rng.normal(0, 1.2, f_axis.size)      # ~12 dBuV noise floor
    spec = floor.copy()
    for fn, vn in zip(f_n, dbuv(v)):
        if fn < 150e3:
            continue
        i = int(round((fn * (1 + rng.normal(0, 2e-3)) - 150e3) / 3e3))
        if 0 <= i < spec.size:
            spec[i] = max(spec[i], vn)
    return f_axis, spec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", type=float, default=150e3)
    ap.add_argument("--stop", type=float, default=30e6)
    ap.add_argument("--fs", type=float, default=2.4e6)
    ap.add_argument("--dwell", type=float, default=0.5)
    ap.add_argument("--cal-db", type=float, default=0.0,
                    help="dBuV = dBFS + cal (single-tone substitution cal)")
    ap.add_argument("--direct", action="store_true",
                    help="RTL-SDR direct-sampling mode (required < 24 MHz)")
    ap.add_argument("--synthetic", choices=["baseline", "snubbed",
                                            "filtered", "all"],
                    help="no hardware: synthesize from the model")
    ap.add_argument("--out", default="results/scan.csv")
    args = ap.parse_args()

    if args.synthetic:
        f, db = scan_synthetic(args.synthetic)
    else:
        f, db = scan_hardware(args.start, args.stop, args.fs, args.dwell,
                              args.cal_db, args.direct)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["freq_hz", "level_dbuv"])
        w.writerows(zip(f, np.round(db, 2)))
    print(f"{len(f)} points -> {args.out}")


if __name__ == "__main__":
    main()
