"""Mitigation designs and their predicted costs/benefits.

Four mitigations, one per emission mechanism:

  RC snubber        -> kills the 40 MHz hot-loop ring (radiated + >10 MHz)
  input pi-filter   -> kills conducted lines 150 kHz - a few MHz
  slower gate edge  -> lowers the 40 dB/dec corner (broad mid-band help)
  tighter hot loop  -> scales DM radiation with area (layout, free)

Each function returns both the design values and the numbers a reviewer
would ask for (loss, stability margin, efficiency cost).
"""

import numpy as np

from parameters import DUT, PAR, MIT
from emissions_model import z_cap, z_ind, z_par, ring_current_peak


# ---------------------------------------------------------------------------
# 1. RC snubber across D1 -- the ring-frequency method
# ---------------------------------------------------------------------------
def snubber_design():
    """Design an RC snubber from the ring parameters.

    Bench procedure this encodes (test-procedure.md step 4): measure the
    bare ring frequency f0; parallel a known capacitor C_add across D1
    until the frequency halves -- f0/2 means total C quadrupled, so
    C_node = C_add/3. Then L_loop = 1/((2*pi*f0)^2 * C_node). The model
    runs the same arithmetic on the estimated parasitics, so the code
    path is identical when real numbers arrive.

    R_snub = Z0 = sqrt(L/C): matches the tank's characteristic impedance,
    i.e. deposits maximum energy in R per cycle (critical-ish damping).
    C_snub ~ 3*C_node: big enough that R sees the ring, small enough to
    bound the C*V^2*f loss.
    """
    f0 = PAR.f_ring
    z0 = PAR.z0_ring
    c_node, l_loop = PAR.C_NODE, PAR.L_LOOP

    r_exact = z0                       # 7.75 -> E24 8.2 ohm (MIT.SNUB_R)
    c_exact = 3.0 * c_node             # 1.5 nF (MIT.SNUB_C)

    # Post-snubber tank: total C = C_node + C_snub, damped by R_snub.
    c_tot = c_node + MIT.SNUB_C
    f0_snub = 1.0 / (2 * np.pi * np.sqrt(l_loop * c_tot))
    z0_snub = float(np.sqrt(l_loop / c_tot))
    # Effective Q with the snubber: R_snub sits in series with C_snub, and
    # the capacitive divider transforms it into the ring path by
    # (C_snub/C_tot)^2 -- series approximation at the new resonance,
    # cross-checked in ltspice/hot_loop_ring.cir.
    r_eff = PAR.R_RING + MIT.SNUB_R * (MIT.SNUB_C / c_tot) ** 2
    q_snub = z0_snub / r_eff
    # Peak ring current also drops: same excitation into higher C, more R.
    ip_snub = ring_current_peak(DUT.VIN, z0_snub + MIT.SNUB_R)

    # Dissipation: the snubber C is charged/discharged through R twice per
    # cycle -> P = C * Vin^2 * fsw (all of it in R, rating matters).
    p_snub = MIT.SNUB_C * DUT.VIN ** 2 * DUT.FSW

    return {
        "f_ring_bare": f0, "q_bare": PAR.q_ring, "z0_bare": z0,
        "r_exact": r_exact, "r_std": MIT.SNUB_R,
        "c_exact": c_exact, "c_std": MIT.SNUB_C,
        "f_ring_snubbed": f0_snub, "z0_snubbed": z0_snub,
        "q_snubbed": q_snub,
        "i_peak_bare": ring_current_peak(DUT.VIN, z0),
        "i_peak_snubbed": ip_snub,
        "p_snubber_w": p_snub,
    }


# ---------------------------------------------------------------------------
# 2. Damped input pi-filter + Middlebrook stability check
# ---------------------------------------------------------------------------
def filter_output_z(f, damped=True, dcr=None, esr=None):
    """Filter output impedance seen by the converter (source side taken as
    a stiff voltage source -- worst case for the peak). dcr/esr overrides
    let the check be re-run for a hypothetical low-loss build."""
    dcr = MIT.FILT_L_DCR if dcr is None else dcr
    esr = MIT.FILT_C_ESR if esr is None else esr
    zl = z_ind(f, MIT.FILT_L, dcr)
    zc = z_cap(f, MIT.FILT_C, esr, MIT.FILT_C_ESL)
    if damped:
        zd = z_cap(f, MIT.DAMP_C, MIT.DAMP_R, MIT.DAMP_C_ESL)
        return z_par(zl, zc, zd)
    return z_par(zl, zc)


def middlebrook_check():
    """A regulated converter is a constant-power load: its incremental
    input resistance is NEGATIVE, |Zin| = Vin^2/Pin = 12.7 ohm below the
    control crossover. If the filter's output impedance peaks above that,
    the filter resonance sees a negative resistance bigger than its own
    damping and the input rail oscillates -- the classic way an EMC fix
    breaks a working converter.

    Design rule applied: |Zout,filter| < |Zin,conv| / 2 (6 dB margin) at
    all frequencies, BY DESIGN rather than by accident. The subtlety this
    check surfaces: with the chosen electrolytic (ESR 0.1 ohm) even the
    undamped filter happens to squeak by -- but that pass rests entirely
    on uncontrolled parasitic ESR (doubles when cold, halves batch to
    batch). Re-run with the low-loss parts a "better components" revision
    would use (ceramic line cap ESR ~5 mohm, low-DCR choke ~10 mohm) and
    the peak blows through |Zin|: the rail oscillates. The 220 uF + 1 ohm
    damping leg (C_d ~ 4-5x C_f, R_d ~ sqrt(L/C_f), Erickson's
    optimal-damping neighborhood) makes the margin independent of ESR.
    """
    f = np.logspace(1, 6, 800)
    z_in = DUT.z_in_neg
    zo_undamped = np.abs(filter_output_z(f, damped=False))
    zo_lowloss = np.abs(filter_output_z(f, damped=False, dcr=0.01, esr=0.005))
    zo_damped = np.abs(filter_output_z(f, damped=True))
    r_d_optimal = float(np.sqrt(MIT.FILT_L / MIT.FILT_C))
    return {
        "f": f,
        "z_in_conv": z_in,
        "zo_undamped": zo_undamped,
        "zo_lowloss": zo_lowloss,
        "zo_damped": zo_damped,
        "peak_undamped": float(zo_undamped.max()),
        "peak_lowloss": float(zo_lowloss.max()),
        "peak_damped": float(zo_damped.max()),
        "margin_db": 20 * np.log10(z_in / zo_damped.max()),
        "r_d_optimal": r_d_optimal,
        "f_corner": 1.0 / (2 * np.pi * np.sqrt(MIT.FILT_L * MIT.FILT_C)),
    }


# ---------------------------------------------------------------------------
# 3. Edge slowing -- efficiency cost
# ---------------------------------------------------------------------------
def edge_slowing():
    """Slow the gate so tr goes 100 -> 220 ns (bigger gate resistor).

    Benefit: the spectrum's 40 dB/dec corner moves 1/(pi*tr):
    3.18 MHz -> 1.45 MHz, buying ~6.9 dB at every frequency above it.
    Cost: overlap switching loss scales linearly with transition time.
    This mitigation is a genuine TRADE (unlike the snubber/layout/filter,
    which are nearly free) -- quantified so it can be rejected if the
    other three suffice.
    """
    p_sw_fast = 0.5 * DUT.VIN * DUT.IOUT * (2 * DUT.TR) * DUT.FSW
    p_sw_slow = 0.5 * DUT.VIN * DUT.IOUT * (2 * MIT.TR_SLOW) * DUT.FSW
    pout = DUT.VOUT * DUT.IOUT
    ploss_base = DUT.PIN - pout
    eff_fast = pout / (pout + ploss_base)
    eff_slow = pout / (pout + ploss_base + (p_sw_slow - p_sw_fast))
    return {
        "tr_fast": DUT.TR, "tr_slow": MIT.TR_SLOW,
        "f_corner_fast": 1 / (np.pi * DUT.TR),
        "f_corner_slow": 1 / (np.pi * MIT.TR_SLOW),
        "hf_gain_db": 20 * np.log10(MIT.TR_SLOW / DUT.TR),
        "p_sw_fast": p_sw_fast, "p_sw_slow": p_sw_slow,
        "eff_fast": eff_fast, "eff_slow": eff_slow,
    }


# ---------------------------------------------------------------------------
# 4. Layout: hot-loop area
# ---------------------------------------------------------------------------
def layout_change():
    """Rebuild the hot loop: D1 soldered lead-to-lead across Q1 drain and
    the C2 ground return routed directly beneath the loop (minimum
    enclosed area instead of merely minimum path length). DM radiation
    scales linearly with area -> 20*log10(2.0/0.5) = 12 dB, for free."""
    return {
        "a_before": PAR.A_LOOP, "a_after": MIT.A_LOOP_TIGHT,
        "gain_db": 20 * np.log10(PAR.A_LOOP / MIT.A_LOOP_TIGHT),
    }
