"""Conducted-emissions model: switching-harmonic source -> LISN voltage.

The DUT's input current is the noise source. An asynchronous buck draws a
chopped trapezoid from its input node: 0 -> Iout for D*Tsw with the current
commutation set by the gate-drive edge, plus a damped ring at
f0 = 1/(2*pi*sqrt(L_loop*C_node)) excited at each switching edge.

Everything is computed as a LINE SPECTRUM at the harmonics n*fsw. That is
what a spectrum analyzer / SDR sees for a periodic source when RBW (9 kHz)
is far below the line spacing (100 kHz): isolated lines at harmonic
amplitudes, independent of RBW. This is why the model can be compared
directly to a measured max-hold trace without any RBW bookkeeping -- see
README "Why a line spectrum".

Signal path (conducted):

  I_noise --+-- Z_caps (C_bulk || C_hf, each with ESR + ESL)
            |
            +-- [optional input pi-filter] -- L_harness -- LISN(50u||50)
                                                             |
                                                          V_LISN -> dBuV

Solved as cascaded current dividers with full complex impedances; no
approximations beyond the lumped-element models themselves.
"""

import numpy as np

from parameters import DUT, PAR, CHAIN, MIT


# ---------------------------------------------------------------------------
# Source line spectra
# ---------------------------------------------------------------------------
def trapezoid_lines(n: np.ndarray, amp: float, D: float, T: float,
                    tr: float) -> np.ndarray:
    """Harmonic magnitudes of a periodic trapezoid (0 -> amp, duty D,
    equal rise/fall tr). Classic double-sinc envelope:

      |c_n| = 2*amp*D * |sinc(n*D)| * |sinc(n*tr/T)|

    with sinc(x) = sin(pi x)/(pi x). First corner at 1/(pi*D*T) rolls off
    20 dB/dec; second corner at 1/(pi*tr) adds another 20 dB/dec. The edge
    speed tr therefore sets everything above ~1/(pi*tr) = 3.2 MHz for the
    100 ns design edge -- the whole HF budget hangs on tr.
    """
    n = np.asarray(n, dtype=float)
    return (2.0 * amp * D
            * np.abs(np.sinc(n * D))
            * np.abs(np.sinc(n * tr / T)))


def ring_lines(n: np.ndarray, T: float, f0: float, Q: float,
               i_peak: float, second_edge_frac: float = 0.5) -> np.ndarray:
    """Harmonic magnitudes of a damped sinusoid repeating every period.

    One ring burst i(t) = Ip*exp(-a t)*sin(wd t) per edge, a = w0/(2Q).
    Its Fourier transform is X(w) = Ip*wd / ((a + jw)^2 + wd^2); a burst
    train at 1/T has lines |c_n| = (2/T)*|X(2*pi*f_n)|.

    Two edges ring per period (turn-on: diode capacitance; turn-off: FET
    Coss) with unknown relative phase, so they are combined as RSS rather
    than coherently -- a deliberate middle ground between the coherent
    worst case (+6 dB) and ignoring the second edge.
    """
    n = np.asarray(n, dtype=float)
    w = 2 * np.pi * n / T
    w0 = 2 * np.pi * f0
    a = w0 / (2.0 * Q)
    wd = w0 * np.sqrt(max(1.0 - 1.0 / (4 * Q * Q), 1e-9))

    def burst(ip):
        X = ip * wd / ((a + 1j * w) ** 2 + wd ** 2)
        return (2.0 / T) * np.abs(X)

    return np.sqrt(burst(i_peak) ** 2 + burst(i_peak * second_edge_frac) ** 2)


def ring_current_peak(vin: float, z0: float, kappa: float = 0.5) -> float:
    """Peak ring current: the tank is hit with ~Vin at commutation, so
    Ip ~ kappa * Vin / Z0. kappa (excitation efficiency, 0..1) is the
    LEAST-CERTAIN number in this model -- it depends on how hard the edge
    excites the tank relative to the ring period. kappa = 0.5 is a
    mid-range placeholder; the rig's first job is to replace it with a
    measured ring amplitude (test-procedure step 4). Note the SNUBBER
    DESIGN does not depend on kappa at all (only on f0 and Z0)."""
    return kappa * vin / z0


# ---------------------------------------------------------------------------
# Impedance elements (all vectorized over f)
# ---------------------------------------------------------------------------
def z_cap(f, C, esr=0.0, esl=0.0):
    w = 2 * np.pi * np.asarray(f, dtype=float)
    return esr + 1j * w * esl + 1.0 / (1j * w * C)


def z_ind(f, L, r=0.0):
    w = 2 * np.pi * np.asarray(f, dtype=float)
    return r + 1j * w * L


def z_par(*zs):
    y = sum(1.0 / z for z in zs)
    return 1.0 / y


def lisn_z(f):
    """CISPR 16-1-2 50 uH V-network seen from the DUT: 50 uH to the (RF-quiet)
    source in parallel with the 50 ohm receiver port. Below ~150 kHz the
    inductor dominates (|Z| falls); above ~1 MHz it is essentially 50 ohm."""
    return z_par(z_ind(f, CHAIN.LISN_L), np.full_like(np.asarray(f, float),
                                                      CHAIN.LISN_R, dtype=complex))


# ---------------------------------------------------------------------------
# Conducted solve
# ---------------------------------------------------------------------------
def input_cap_z(f):
    """DUT input capacitors with parasitics. The ESLs matter: above
    ~1.6 MHz the 470 uF bulk is an inductor (20 nH), above ~1.3 MHz so is
    the 1 uF HF cap -- which is exactly why raw perfboard converters leak
    in the single-digit-MHz decade."""
    zb = z_cap(f, DUT.C_BULK, DUT.C_BULK_ESR, PAR.ESL_BULK)
    zh = z_cap(f, DUT.C_HF, DUT.C_HF_ESR, PAR.ESL_HF)
    return z_par(zb, zh)


def pi_filter_shunt_z(f):
    """Line-side shunt of the input filter: 47 uF cap in parallel with the
    220 uF + 1 ohm damping leg (sized in mitigations.py)."""
    zc = z_cap(f, MIT.FILT_C, MIT.FILT_C_ESR, MIT.FILT_C_ESL)
    zd = z_cap(f, MIT.DAMP_C, MIT.DAMP_R, MIT.DAMP_C_ESL)
    return z_par(zc, zd)


def conducted_vlisn(f, i_lines, with_filter=False):
    """Transimpedance solve: harmonic current lines -> V_LISN magnitude.

    Divider 1 (at the DUT input node): I splits between the input caps
    and everything toward the line. Divider 2 (only with the filter): the
    line-bound current splits again at the filter's shunt node.
    """
    f = np.asarray(f, dtype=float)
    z_lisn = lisn_z(f)
    z_line = z_ind(f, PAR.L_HARNESS, PAR.R_HARNESS) + z_lisn
    z_caps = input_cap_z(f)

    if with_filter:
        z_shunt = pi_filter_shunt_z(f)
        z_toline = z_ind(f, MIT.FILT_L, MIT.FILT_L_DCR) + z_par(z_shunt, z_line)
        i1 = i_lines * np.abs(z_caps / (z_caps + z_toline))
        i2 = i1 * np.abs(z_shunt / (z_shunt + z_line))
    else:
        i2 = i_lines * np.abs(z_caps / (z_caps + z_line))

    return i2 * np.abs(z_lisn)


def conducted_spectrum(tr=None, ring=True, snubbed=False, with_filter=False,
                       n_max=300):
    """Full conducted line spectrum 100 kHz .. 30 MHz for one DUT variant.

    Returns (f_n, V_LISN) in Hz / volts. Variants:
      tr          -- edge time override (edge-slowing mitigation)
      snubbed     -- ring parameters replaced by post-snubber values
      with_filter -- input pi-filter installed
    """
    tr = DUT.TR if tr is None else tr
    T = 1.0 / DUT.FSW
    n = np.arange(1, n_max + 1)
    f_n = n * DUT.FSW

    i_lines = trapezoid_lines(n, DUT.IOUT, DUT.D, T, tr)

    if ring:
        if snubbed:
            from mitigations import snubber_design
            sn = snubber_design()
            i_lines = np.sqrt(i_lines ** 2 + ring_lines(
                n, T, sn["f_ring_snubbed"], sn["q_snubbed"],
                sn["i_peak_snubbed"]) ** 2)
        else:
            ip = ring_current_peak(DUT.VIN, PAR.z0_ring)
            i_lines = np.sqrt(i_lines ** 2 +
                              ring_lines(n, T, PAR.f_ring, PAR.q_ring, ip) ** 2)

    return f_n, conducted_vlisn(f_n, i_lines, with_filter=with_filter)
