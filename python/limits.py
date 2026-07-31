"""CISPR 32 / EN 55032 Class B limit masks.

Class B (residential) is the harder mask and the right pre-compliance
target for a hobby/portfolio converter. Values are the published
quasi-peak limits; peak-detector readings are always >= QP, so a PEAK
measurement below the QP mask is a conservative pass (see README for why
we measure peak with the SDR instead of implementing a QP detector).
"""

import numpy as np


def conducted_qp_dbuv(f: np.ndarray) -> np.ndarray:
    """CISPR 32 Class B conducted (mains port) QP limit, 150 kHz - 30 MHz.

    66 dBuV at 150 kHz falling log-linearly to 56 dBuV at 500 kHz,
    56 dBuV to 5 MHz, 60 dBuV to 30 MHz. NaN outside the band.
    """
    f = np.asarray(f, dtype=float)
    lim = np.full_like(f, np.nan)
    m1 = (f >= 150e3) & (f < 500e3)
    lim[m1] = 66.0 - 20.0 * (np.log10(f[m1] / 150e3) / np.log10(500e3 / 150e3))
    m2 = (f >= 500e3) & (f < 5e6)
    lim[m2] = 56.0
    m3 = (f >= 5e6) & (f <= 30e6)
    lim[m3] = 60.0
    return lim


def radiated_qp_dbuv_m(f: np.ndarray, dist_m: float = 3.0) -> np.ndarray:
    """CISPR 32 Class B radiated QP limit scaled to measurement distance.

    Published at 10 m: 30 dBuV/m (30-230 MHz), 37 dBuV/m (230-1000 MHz).
    Scaled with 20*log10(10/d) inverse-distance -- the standard (and
    imperfect, see README) extrapolation for a 3 m pre-compliance range.
    """
    f = np.asarray(f, dtype=float)
    scale = 20.0 * np.log10(10.0 / dist_m)
    lim = np.full_like(f, np.nan)
    lim[(f >= 30e6) & (f < 230e6)] = 30.0 + scale
    lim[(f >= 230e6) & (f <= 1000e6)] = 37.0 + scale
    return lim


def dbuv(v: np.ndarray) -> np.ndarray:
    """Volts -> dBuV, floored to avoid log(0)."""
    return 20.0 * np.log10(np.maximum(np.asarray(v, dtype=float), 1e-12) / 1e-6)
