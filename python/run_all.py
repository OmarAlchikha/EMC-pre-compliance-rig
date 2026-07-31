"""Run every model, write all plots + emc_report.txt into results/.

    python run_all.py

Figure conventions (match the buck-converter repo): fixed color
assignment, never cycled -- baseline/before is always blue, the mitigated
variant always green, mechanism breakdowns orange/purple, limits and
references gray. One axis per figure.
"""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parameters import (DUT, PAR, CHAIN, MIT,
                        COL_PRIMARY, COL_SECONDARY, COL_TERTIARY,
                        COL_ACCENT, COL_GRAY)
import limits
from emissions_model import conducted_spectrum
from radiated_model import radiated_spectrum, probe_transfer, \
    probe_voltage_spectrum
from mitigations import snubber_design, middlebrook_check, edge_slowing, \
    layout_change

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "figure.figsize": (9, 5.2), "figure.dpi": 110,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10.5, "axes.titlesize": 11.5,
    "lines.linewidth": 1.8, "legend.frameon": False,
})

REPORT = []


def rep(txt=""):
    REPORT.append(txt)
    print(txt)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print(f"  wrote results/{name}")


def worst_margin(f, level_db, mask_db):
    """(freq, level, margin) at the worst point inside the mask's band.
    Positive margin = passing."""
    ok = ~np.isnan(mask_db)
    m = mask_db[ok] - level_db[ok]
    i = int(np.argmin(m))
    return f[ok][i], level_db[ok][i], m[i]


# ===========================================================================
# 1. Conducted emissions
# ===========================================================================
rep("=" * 74)
rep("CONDUCTED EMISSIONS -- LISN voltage vs CISPR 32 Class B (QP mask)")
rep("=" * 74)

variants = {
    "baseline": dict(),
    "+ snubber only": dict(snubbed=True),
    "+ pi-filter only": dict(with_filter=True),
    "filter + snubber": dict(snubbed=True, with_filter=True),
    "filter + snubber + slow edge": dict(snubbed=True, with_filter=True,
                                         tr=MIT.TR_SLOW),
}
cond = {}
for name, kw in variants.items():
    f_n, v = conducted_spectrum(**kw)
    lv = limits.dbuv(v)
    cond[name] = (f_n, lv)
    fw, lw, mg = worst_margin(f_n, lv, limits.conducted_qp_dbuv(f_n))
    rep(f"  {name:30s} worst margin {mg:+6.1f} dB at {fw/1e6:6.2f} MHz "
        f"(level {lw:5.1f} dBuV)")

f_n = cond["baseline"][0]
mask = limits.conducted_qp_dbuv(f_n)

fig, ax = plt.subplots()
ax.plot(f_n, cond["baseline"][1], color=COL_PRIMARY, label="baseline DUT")
ax.plot(f_n, mask, color=COL_GRAY, ls="--", lw=1.4)
ax.text(1.6e5, 45, "CISPR 32 Class B (QP)", color=COL_GRAY, fontsize=9)
fw, lw_, mg = worst_margin(f_n, cond["baseline"][1], mask)
ax.annotate(f"worst: {-mg:.0f} dB over\n@ {fw/1e6:.1f} MHz",
            xy=(fw, lw_), xytext=(fw * 2.2, lw_ + 9), fontsize=9,
            color="#333333", arrowprops=dict(arrowstyle="-", color=COL_GRAY))
ax.set_xscale("log")
ax.set_xlim(120e3, 30e6)
ax.set_ylim(-10, 100)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("LISN voltage [dBµV]")
ax.set_title("Conducted emissions, baseline 12 V→5 V buck "
             "(100 kHz lines, peak ≈ QP for isolated lines)")
ax.legend(loc="lower left")
save(fig, "conducted_baseline.png")

fig, ax = plt.subplots()
ax.plot(f_n, cond["baseline"][1], color=COL_PRIMARY, label="baseline")
ax.plot(f_n, cond["+ pi-filter only"][1], color=COL_SECONDARY,
        label="+ damped input π-filter")
ax.plot(f_n, cond["filter + snubber"][1], color=COL_TERTIARY,
        label="+ filter + snubber")
ax.plot(f_n, mask, color=COL_GRAY, ls="--", lw=1.4)
ax.text(1.6e5, 45, "CISPR 32 Class B (QP)", color=COL_GRAY, fontsize=9)
ax.set_xscale("log")
ax.set_xlim(120e3, 30e6)
ax.set_ylim(-40, 100)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("LISN voltage [dBµV]")
ax.set_title("Conducted emissions: mitigation stack")
ax.legend(loc="upper right")
save(fig, "conducted_mitigated.png")

# ===========================================================================
# 2. Radiated emissions
# ===========================================================================
rep()
rep("=" * 74)
rep("RADIATED EMISSIONS -- E at 3 m vs CISPR 32 Class B (scaled to 3 m)")
rep("=" * 74)

f_r, e_tot, e_dm_, e_cm_ = radiated_spectrum()
f_r2, e_mit, _, _ = radiated_spectrum(snubbed=True, ferrite=True,
                                      area=MIT.A_LOOP_TIGHT)
band = f_r >= 30e6
maskr = limits.radiated_qp_dbuv_m(f_r, 3.0)
for name, e in [("baseline", e_tot), ("mitigated (snub+ferrite+layout)",
                                      e_mit)]:
    lv = limits.dbuv(e)          # dBuV/m: same 20log10(x/1e-6)
    fw, lw_, mg = worst_margin(f_r, lv, maskr)
    rep(f"  {name:34s} worst margin {mg:+6.1f} dB at {fw/1e6:6.1f} MHz "
        f"(level {lw_:5.1f} dBuV/m)")

fig, ax = plt.subplots()
ax.plot(f_r[band], limits.dbuv(e_tot)[band], color=COL_PRIMARY,
        label="total (baseline)")
ax.plot(f_r[band], limits.dbuv(e_dm_)[band], color=COL_SECONDARY, lw=1.2,
        label="differential mode (hot loop)")
ax.plot(f_r[band], limits.dbuv(e_cm_)[band], color=COL_ACCENT, lw=1.2,
        label="common mode (harness)")
ax.plot(f_r[band], maskr[band], color=COL_GRAY, ls="--", lw=1.4)
ax.text(1.15e8, 42.6, "Class B @ 3 m", color=COL_GRAY, fontsize=9)
ax.annotate(f"hot-loop ring\n{PAR.f_ring/1e6:.0f} MHz",
            xy=(PAR.f_ring, limits.dbuv(e_tot)[np.argmin(np.abs(f_r - PAR.f_ring))]),
            xytext=(5.5e7, 62), fontsize=9, color="#333333",
            arrowprops=dict(arrowstyle="-", color=COL_GRAY))
ax.set_xscale("log")
ax.set_xlim(30e6, 300e6)
ax.set_ylim(-30, 80)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("E field at 3 m [dBµV/m]")
ax.set_title("Radiated estimate, baseline: common mode dominates "
             "(free-space model, see README caveats)")
ax.legend(loc="lower left")
save(fig, "radiated_baseline.png")

fig, ax = plt.subplots()
ax.plot(f_r[band], limits.dbuv(e_tot)[band], color=COL_PRIMARY,
        label="baseline")
ax.plot(f_r[band], limits.dbuv(e_mit)[band], color=COL_TERTIARY,
        label="snubber + harness ferrite + tight loop")
ax.plot(f_r[band], maskr[band], color=COL_GRAY, ls="--", lw=1.4)
ax.text(1.15e8, 42.6, "Class B @ 3 m", color=COL_GRAY, fontsize=9)
ax.set_xscale("log")
ax.set_xlim(30e6, 300e6)
ax.set_ylim(-30, 80)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("E field at 3 m [dBµV/m]")
ax.set_title("Radiated estimate: before / after mitigation")
ax.legend(loc="lower left")
save(fig, "radiated_mitigated.png")

# ===========================================================================
# 3. Snubber design + ring time domain
# ===========================================================================
rep()
rep("=" * 74)
rep("RC SNUBBER DESIGN (ring-frequency method, mitigations.py)")
rep("=" * 74)
sn = snubber_design()
rep(f"  bare ring: f0 = {sn['f_ring_bare']/1e6:.1f} MHz, "
    f"Z0 = {sn['z0_bare']:.1f} ohm, Q = {sn['q_bare']:.1f}, "
    f"Ipk ~ {sn['i_peak_bare']:.2f} A (kappa=0.5 assumed)")
rep(f"  design:   R = Z0 = {sn['r_exact']:.1f} -> {sn['r_std']:.1f} ohm "
    f"(E24), C = 3*Cnode = {sn['c_exact']*1e9:.2f} -> "
    f"{sn['c_std']*1e9:.1f} nF")
rep(f"  snubbed:  f0 = {sn['f_ring_snubbed']/1e6:.1f} MHz, "
    f"Q = {sn['q_snubbed']:.2f}, Ipk ~ {sn['i_peak_snubbed']:.2f} A")
rep(f"  snubber dissipation: C*Vin^2*fsw = {sn['p_snubber_w']*1e3:.0f} mW "
    f"(use a 1/4 W resistor; efficiency cost {sn['p_snubber_w']/10*100:.2f} "
    f"points)")

t = np.linspace(0, 400e-9, 2000)


def ring_wave(f0, q, v_pk):
    w0 = 2 * np.pi * f0
    a = w0 / (2 * q)
    wd = w0 * np.sqrt(max(1 - 1 / (4 * q * q), 1e-9))
    return DUT.VIN + v_pk * np.exp(-a * t) * np.sin(wd * t)


fig, ax = plt.subplots()
ax.plot(t * 1e9, ring_wave(sn["f_ring_bare"], sn["q_bare"],
                           sn["i_peak_bare"] * sn["z0_bare"]),
        color=COL_PRIMARY, label="bare SW node")
ax.plot(t * 1e9, ring_wave(sn["f_ring_snubbed"], sn["q_snubbed"],
                           sn["i_peak_snubbed"] * sn["z0_snubbed"]),
        color=COL_TERTIARY, label=f"with {sn['r_std']:.1f} Ω + "
        f"{sn['c_std']*1e9:.1f} nF snubber")
ax.axhline(DUT.VIN, color=COL_GRAY, ls=":", lw=1)
ax.text(360, DUT.VIN + 0.3, "12 V", color=COL_GRAY, fontsize=9)
ax.set_xlabel("time after turn-on edge [ns]")
ax.set_ylabel("SW node voltage [V]")
ax.set_title("Switch-node ring at turn-on, kappa=0.5 excitation "
             "(f\u2080 and Q verified in ltspice/hot_loop_ring.cir)")
ax.legend(loc="upper right")
save(fig, "snubber_ring.png")

# ===========================================================================
# 4. Input filter: Middlebrook stability
# ===========================================================================
rep()
rep("=" * 74)
rep("INPUT PI-FILTER + MIDDLEBROOK CHECK (mitigations.py)")
rep("=" * 74)
mb = middlebrook_check()
rep(f"  filter: L = {MIT.FILT_L*1e6:.0f} uH, C = {MIT.FILT_C*1e6:.0f} uF, "
    f"corner {mb['f_corner']:.0f} Hz")
rep(f"  damping leg: C_d = {MIT.DAMP_C*1e6:.0f} uF + R_d = "
    f"{MIT.DAMP_R:.1f} ohm (sqrt(L/C) = {mb['r_d_optimal']:.2f} ohm)")
rep(f"  converter |Zin| (neg.) = {mb['z_in_conv']:.1f} ohm")
rep(f"  |Zout,filter| peak: undamped {mb['peak_undamped']:.1f} ohm "
    f"(passes only thanks to electrolytic ESR),")
rep(f"    undamped w/ low-loss parts {mb['peak_lowloss']:.1f} ohm "
    f"(> |Zin|: RAIL OSCILLATES -- the trap a 'better caps' rev "
    f"walks into),")
rep(f"    damped {mb['peak_damped']:.2f} ohm -> margin "
    f"{mb['margin_db']:.1f} dB by design (still 0.99 ohm with "
    f"near-zero-ESR parts: the margin belongs to the damping leg)")

fig, ax = plt.subplots()
ax.plot(mb["f"], mb["zo_lowloss"], color=COL_ACCENT, lw=1.2,
        label="undamped, low-loss parts (ceramic cap): oscillates")
ax.plot(mb["f"], mb["zo_undamped"], color=COL_SECONDARY,
        label="undamped, chosen electrolytic (passes on ESR luck)")
ax.plot(mb["f"], mb["zo_damped"], color=COL_TERTIARY,
        label="filter Z_out, with 220 µF + 1 Ω damping leg")
ax.axhline(mb["z_in_conv"], color=COL_GRAY, ls="--", lw=1.4)
ax.text(15, mb["z_in_conv"] * 1.25,
        "|Z_in| of regulated converter = V²/P = 12.7 Ω (negative)",
        color=COL_GRAY, fontsize=9)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlim(10, 1e6)
ax.set_ylim(1e-2, 300)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("|Z| [Ω]")
ax.set_title("Middlebrook check: the EMC filter must not destabilize "
             "the converter it protects")
ax.legend(loc="upper left")
save(fig, "filter_middlebrook.png")

# ===========================================================================
# 5. Edge slowing + layout numbers
# ===========================================================================
rep()
rep("=" * 74)
rep("EDGE SLOWING AND LAYOUT (mitigations.py)")
rep("=" * 74)
es = edge_slowing()
rep(f"  tr {es['tr_fast']*1e9:.0f} -> {es['tr_slow']*1e9:.0f} ns: 40 dB/dec "
    f"corner {es['f_corner_fast']/1e6:.2f} -> {es['f_corner_slow']/1e6:.2f} "
    f"MHz, {es['hf_gain_db']:.1f} dB less at HF")
rep(f"  cost: P_sw {es['p_sw_fast']:.2f} -> {es['p_sw_slow']:.2f} W, "
    f"efficiency {es['eff_fast']*100:.1f} -> {es['eff_slow']*100:.1f} %")
lo = layout_change()
rep(f"  hot loop {lo['a_before']*1e4:.1f} -> {lo['a_after']*1e4:.1f} cm^2: "
    f"DM radiated -{lo['gain_db']:.1f} dB, zero cost")

# ===========================================================================
# 6. H-field probe
# ===========================================================================
rep()
rep("=" * 74)
rep("H-FIELD PROBE (hardware/h-field-probe.md)")
rep("=" * 74)
f_p = np.logspace(5, 9, 400)
pf = probe_transfer(f_p)
fc_probe = CHAIN.PROBE_R_TERM / (2 * np.pi * CHAIN.PROBE_L_SELF)
rep(f"  loop d = {CHAIN.PROBE_D*1000:.0f} mm, A = "
    f"{CHAIN.probe_area*1e6:.1f} mm^2, L_self ~ "
    f"{CHAIN.PROBE_L_SELF*1e9:.0f} nH -> L/R corner {fc_probe/1e6:.0f} MHz")
rep(f"  transfer at 40 MHz: {probe_transfer(np.array([40e6]))[0]*1e3:.2f} "
    f"mV per A/m")

f_v, v_probe = probe_voltage_spectrum()
f_v2, v_probe_sn = probe_voltage_spectrum(snubbed=True)
i0 = np.argmin(np.abs(f_v - PAR.f_ring))
rep(f"  predicted probe voltage over the hot loop at 1 cm, ring line: "
    f"{limits.dbuv(v_probe)[i0]:.0f} dBuV ({v_probe[i0]*1e6:.0f} uV) -- "
    f"~40 dB above the SDR noise floor: no preamp needed")

fig, ax = plt.subplots()
ax.plot(f_p, 20 * np.log10(pf), color=COL_PRIMARY)
ax.axvline(fc_probe, color=COL_GRAY, ls=":", lw=1)
ax.text(fc_probe * 1.15, -85, "L/R corner\n(self-L vs 50 Ω)",
        color=COL_GRAY, fontsize=9)
ax.set_xscale("log")
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("probe transfer [dB(V per A/m)]")
ax.set_title("Shielded-loop H probe: derivative response, +20 dB/dec "
             "to the L/R corner")
save(fig, "probe_transfer.png")

band_p = (f_v >= 1e6)
fig, ax = plt.subplots()
ax.plot(f_v[band_p], limits.dbuv(v_probe)[band_p], color=COL_PRIMARY,
        label="baseline")
ax.plot(f_v[band_p], limits.dbuv(v_probe_sn)[band_p], color=COL_TERTIARY,
        label="with snubber")
ax.axhline(12, color=COL_GRAY, ls="--", lw=1.2)
ax.text(1.3e6, 14, "≈ SDR noise floor (9 kHz RBW)", color=COL_GRAY,
        fontsize=9)
ax.set_xscale("log")
ax.set_xlim(1e6, 300e6)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("probe voltage into SDR [dBµV]")
ax.set_title("Predicted H-probe signal, loop at 1 cm over the hot loop "
             "(relative tool: watch the ring drop)")
ax.legend(loc="upper right")
save(fig, "probe_signal.png")

# ===========================================================================
# 7. Synthetic SDR scan (pipeline demo)
# ===========================================================================
import sdr_scan
fs_b, db_b = sdr_scan.scan_synthetic("baseline")
fs_a, db_a = sdr_scan.scan_synthetic("all")
fig, ax = plt.subplots()
ax.plot(fs_b, db_b, color=COL_PRIMARY, lw=0.8, label="baseline")
ax.plot(fs_a, db_a, color=COL_TERTIARY, lw=0.8,
        label="filter + snubber")
ax.plot(fs_b, limits.conducted_qp_dbuv(fs_b), color=COL_GRAY, ls="--",
        lw=1.4)
ax.text(1.6e5, 45, "CISPR 32 Class B (QP)", color=COL_GRAY, fontsize=9)
ax.set_xscale("log")
ax.set_xlim(150e3, 30e6)
ax.set_ylim(0, 100)
ax.set_xlabel("frequency [Hz]")
ax.set_ylabel("level [dBµV]")
ax.set_title("What the SDR sweep will look like (synthetic: model + "
             "receiver noise floor + oscillator jitter)")
ax.legend(loc="upper right")
save(fig, "sdr_synthetic_scan.png")

# ===========================================================================
with open(os.path.join(OUT, "emc_report.txt"), "w") as fh:
    fh.write("\n".join(REPORT) + "\n")
print("\nwrote results/emc_report.txt")
