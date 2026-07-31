"""Radiated-emissions estimate + H-field probe response.

Two mechanisms, modeled separately and RSS-combined:

1. DIFFERENTIAL MODE -- the hot loop (C2 -> Q1 -> D1) is a small current
   loop, i.e. a magnetic dipole with moment m = I(f) * A_loop. Far-field:

     E [V/m] = eta0 * (2*pi*f/c)^2 * I * A / (4*pi*r)  ~ 1.32e-14 f^2 I A / r

   E grows as f^2 * I(f): even a tiny loop radiates once the ring puts
   current lines in the tens of MHz.

2. COMMON MODE -- the SW node's dV/dt drives displacement current through
   stray capacitance to the environment; that current returns via the DC
   harness, which then radiates as an electrically short wire antenna:

     E [V/m] = 60*pi * I_cm * L_wire * f / (c * r)

   CM is why "the loop is tiny, we're fine" fails in practice: a few tens
   of uA of CM current on half a meter of harness rivals a Class B limit.
   The CM path is modeled as a series RLC (C_stray - L_cm(harness) - R_loss)
   so it exhibits the real-world behavior: capacitive (weak) at low f, a
   nasty series resonance where the harness inductance tunes out C_stray,
   damped only by loss -- which is exactly where a clip-on ferrite earns
   its place.

CAVEATS (stated, not hidden): at 30 MHz a 3 m range is in the near/far
transition (lambda/2pi = 1.6 m), the dipole formulas assume free space
(no ground-plane reflection, up to +6 dB), and C_stray/kappa are order-of-
magnitude estimates. This model ranks mechanisms and predicts DELTAS from
mitigations; absolute margins come from the bench, relative levels from
here. That division of labor is the whole pre-compliance philosophy.
"""

import numpy as np

from parameters import DUT, PAR, CHAIN, MU0, C0, ETA0
from emissions_model import trapezoid_lines, ring_lines, ring_current_peak

# CM path estimates (flagged in parameters.py's spirit: replace by bench)
C_STRAY = 3e-12      # SW node + heatsink tab + D1 body to environment [F]
L_CM = 1.0e-6        # harness common-mode inductance (~0.5 m pair) [H]
R_CM = 60.0          # radiation + loss resistance of the CM loop [ohm]
L_WIRE = 0.5         # radiating harness length [m]


def _harmonics(n_max=3000):
    n = np.arange(1, n_max + 1)
    return n, n * DUT.FSW


def loop_current_lines(n, tr, ring_f0, ring_q, ring_ip):
    """Hot-loop current: chopped trapezoid + edge ring."""
    T = 1.0 / DUT.FSW
    trap = trapezoid_lines(n, DUT.IOUT, DUT.D, T, tr)
    rng = ring_lines(n, T, ring_f0, ring_q, ring_ip)
    return np.sqrt(trap ** 2 + rng ** 2)


def sw_voltage_lines(n, tr, ring_f0, ring_q, v_ring_peak):
    """SW-node voltage: 0->12 V trapezoid + ring overshoot voltage."""
    T = 1.0 / DUT.FSW
    trap = trapezoid_lines(n, DUT.VIN, DUT.D, T, tr)
    rng = ring_lines(n, T, ring_f0, ring_q, v_ring_peak)
    return np.sqrt(trap ** 2 + rng ** 2)


def e_dm(f, i_lines, area, r):
    """Magnetic-dipole far field of the hot loop [V/m]."""
    f = np.asarray(f, dtype=float)
    return ETA0 * (2 * np.pi * f / C0) ** 2 * i_lines * area / (4 * np.pi * r)


def cm_path_z(f, z_ferrite=None):
    """Series RLC common-mode path; optional ferrite impedance in series."""
    w = 2 * np.pi * np.asarray(f, dtype=float)
    z = R_CM + 1j * w * L_CM + 1.0 / (1j * w * C_STRAY)
    if z_ferrite is not None:
        z = z + z_ferrite
    return z


def ferrite_z(f, r_at_ref=200.0, f_ref=40e6):
    """Clip-on ferrite (2 turns), lossy above ~10 MHz. Modeled as a lossy
    inductor whose impedance is mostly RESISTIVE in the VHF range -- that
    resistance is the damping element for the CM series resonance. Simple
    fit: |Z| ramps 20 dB/dec below f_ref, flat (resistive) above."""
    f = np.asarray(f, dtype=float)
    mag = r_at_ref * np.minimum(f / f_ref, 1.0)
    # 30 deg inductive below f_ref, near-resistive above
    phase = np.where(f < f_ref, np.pi / 3, np.pi / 12)
    return mag * np.exp(1j * phase)


def e_cm(f, v_sw_lines, r, z_ferrite=None):
    """CM emission: SW-node voltage -> CM current -> short-wire E field."""
    f = np.asarray(f, dtype=float)
    i_cm = v_sw_lines / np.abs(cm_path_z(f, z_ferrite))
    return 60 * np.pi * i_cm * L_WIRE * f / (C0 * r)


def radiated_spectrum(tr=None, snubbed=False, area=None, ferrite=False,
                      r=3.0, n_max=3000):
    """Total radiated estimate at distance r for one DUT variant.

    Returns (f, E_total, E_dm, E_cm) in Hz / V/m.
    """
    tr = DUT.TR if tr is None else tr
    area = PAR.A_LOOP if area is None else area
    n, f = _harmonics(n_max)

    if snubbed:
        from mitigations import snubber_design
        sn = snubber_design()
        f0, q, ip = sn["f_ring_snubbed"], sn["q_snubbed"], sn["i_peak_snubbed"]
        vr = ip * sn["z0_snubbed"]
    else:
        f0, q = PAR.f_ring, PAR.q_ring
        ip = ring_current_peak(DUT.VIN, PAR.z0_ring)
        vr = ip * PAR.z0_ring

    i_lines = loop_current_lines(n, tr, f0, q, ip)
    v_lines = sw_voltage_lines(n, tr, f0, q, vr)

    edm = e_dm(f, i_lines, area, r)
    ecm = e_cm(f, v_lines, r, ferrite_z(f) if ferrite else None)
    return f, np.sqrt(edm ** 2 + ecm ** 2), edm, ecm


# ---------------------------------------------------------------------------
# H-field probe response (what the SDR actually sees on the bench)
# ---------------------------------------------------------------------------
def probe_transfer(f):
    """Shielded-loop transfer: V_out(50 ohm) per unit H [V per A/m].

    Faraday: V_oc = j*w*mu0*A_probe*H. The loop's self-inductance and the
    50 ohm termination form an L/R divider with corner fc = R/(2*pi*L)
    ~ 320 MHz -- below fc the response rises 20 dB/dec (a derivative
    probe), above it flattens. Everything this rig cares about is below
    fc, so: small probe = low sensitivity but flat-in-derivative,
    predictable response. Absolute cal still comes from the substitution
    method in hardware/h-field-probe.md."""
    w = 2 * np.pi * np.asarray(f, dtype=float)
    v_oc = w * MU0 * CHAIN.probe_area
    div = CHAIN.PROBE_R_TERM / np.abs(
        CHAIN.PROBE_R_TERM + 1j * w * CHAIN.PROBE_L_SELF)
    return v_oc * div


def near_h_from_loop(i_lines, r_probe=0.01):
    """On-axis near-field H of the hot loop at probe distance r [A/m].
    Magnetic-dipole near term H = m/(2*pi*r^3); at r ~ loop size this is
    order-of-magnitude only, which is fine -- near-field probing is a
    RELATIVE (before/after, where-is-it-coming-from) tool, never absolute."""
    m = i_lines * PAR.A_LOOP
    return m / (2 * np.pi * r_probe ** 3)


def probe_voltage_spectrum(tr=None, snubbed=False, r_probe=0.01, n_max=3000):
    """Predicted probe voltage into the SDR, hot loop at r_probe."""
    tr = DUT.TR if tr is None else tr
    n, f = _harmonics(n_max)
    if snubbed:
        from mitigations import snubber_design
        sn = snubber_design()
        i_lines = loop_current_lines(n, tr, sn["f_ring_snubbed"],
                                     sn["q_snubbed"], sn["i_peak_snubbed"])
    else:
        ip = ring_current_peak(DUT.VIN, PAR.z0_ring)
        i_lines = loop_current_lines(n, tr, PAR.f_ring, PAR.q_ring, ip)
    return f, probe_transfer(f) * near_h_from_loop(i_lines, r_probe)
