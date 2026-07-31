"""Single source of truth for the EMC pre-compliance rig.

Every model file reads from here, mirroring the convention of the
buck-converter repo (../../buck-converter/python-model/parameters.py).

Two kinds of numbers live in this file and they are NOT equally trustworthy:

1. DUT values copied verbatim from the buck-converter design package
   (Specs/Components there are the single source of truth; these are the
   *chosen, verified* design values).
2. EMC-specific PARASITICS that do not exist anywhere in the buck design
   because they are properties of the physical perfboard build: hot-loop
   inductance, device capacitances at the switch node, capacitor ESL,
   harness inductance, loop area. These are ESTIMATES from datasheet
   typicals and the 10 nH/cm perfboard rule, and each one is flagged with
   the measurement that replaces it (see hardware/test-procedure.md).
   The whole point of the rig is to replace section 2 with bench data.
"""

from dataclasses import dataclass
import numpy as np

MU0 = 4e-7 * np.pi          # vacuum permeability [H/m]
C0 = 299_792_458.0          # speed of light [m/s]
ETA0 = 376.73               # free-space impedance [ohm]


# ---------------------------------------------------------------------------
# 1. DUT: values copied from buck-converter/python-model/parameters.py
# ---------------------------------------------------------------------------
@dataclass
class BuckDUT:
    """12 V -> 5 V / 2 A asynchronous buck (IRF9540N + SB540, TL494 VM-PI)."""
    VIN: float = 12.0
    VOUT: float = 5.0
    IOUT: float = 2.0
    FSW: float = 100e3          # switching frequency [Hz]
    D: float = 0.4543           # duty with conduction drops (design_report.txt s1)
    TR: float = 100e-9          # voltage rise/fall time at SW node [s]
                                # (buck design: "slow ~100 ns edges", tr+tf=200 ns)
    DIL: float = 0.621          # inductor ripple current pk-pk [A]
    RDS_ON: float = 0.117       # IRF9540N on-resistance [ohm]
    PIN: float = 11.34          # input power at full load [W] (design_report s7)

    # Input capacitors as specified in design_report.txt s4:
    # 470 uF/25 V low-impedance electrolytic + 1 uF film/MLCC across the loop
    C_BULK: float = 470e-6
    C_BULK_ESR: float = 0.050
    C_HF: float = 1e-6
    C_HF_ESR: float = 0.020

    @property
    def z_in_neg(self) -> float:
        """Magnitude of the converter's negative incremental input resistance
        below crossover: |Zin| = Vin^2 / Pin. The regulated converter is a
        constant-power load, so dV*dI < 0 -- this is what an undamped input
        filter can oscillate against (Middlebrook)."""
        return self.VIN ** 2 / self.PIN   # = 12.7 ohm


# ---------------------------------------------------------------------------
# 2. EMC parasitics -- ESTIMATES, to be replaced by measurement
# ---------------------------------------------------------------------------
@dataclass
class Parasitics:
    """Physical-build parasitics. None of these exist in the buck design
    files; every one is an estimate with its replacement measurement noted.
    """
    # Hot loop (C2 -> Q1 -> D1 -> C2): the perfboard layout rule bounds the
    # loop path at < 3 cm; the 10 nH/cm rule-of-thumb gives ~30 nH.
    # MEASURE: ring frequency before/after a known added C (test-procedure s4).
    L_LOOP: float = 30e-9

    # Capacitance ringing with L_LOOP at the switch node: SB540 junction
    # capacitance (~450 pF datasheet typ. at low reverse bias) in parallel
    # with wiring C; IRF9540N Coss rings the complementary edge.
    # MEASURE: same added-C experiment resolves the true C.
    C_NODE: float = 500e-12

    # Resistance damping the bare ring: FET Rds(on) + trace + cap ESR.
    R_RING: float = 0.6

    # Capacitor ESL including ~1 cm of perfboard lead per leg.
    ESL_BULK: float = 20e-9     # radial electrolytic, typical
    ESL_HF: float = 15e-9       # film/MLCC + leads

    # DC harness from LISN to DUT input terminals (~50 cm pair).
    L_HARNESS: float = 500e-9
    R_HARNESS: float = 0.05

    # Radiating hot-loop area on the as-built perfboard. The <3 cm path
    # rule bounds it, but perfboard hole pitch makes ~2 cm^2 realistic.
    # MEASURE: geometry of the actual build (photo + ruler).
    A_LOOP: float = 2.0e-4      # [m^2] = 2 cm^2

    @property
    def f_ring(self) -> float:
        return 1.0 / (2 * np.pi * np.sqrt(self.L_LOOP * self.C_NODE))  # ~41 MHz

    @property
    def z0_ring(self) -> float:
        return float(np.sqrt(self.L_LOOP / self.C_NODE))               # ~7.7 ohm

    @property
    def q_ring(self) -> float:
        return self.z0_ring / self.R_RING                              # ~13


# ---------------------------------------------------------------------------
# 3. Measurement chain
# ---------------------------------------------------------------------------
@dataclass
class MeasurementChain:
    """LISN + SDR receiver + H-field probe parameters."""
    # LISN: CISPR 16-1-2 style 50 uH V-network (single line, budget build,
    # hardware/lisn.md). Model: 50 uH || 50 ohm receiver port; the 0.1 uF
    # coupling cap adds a 32 kHz high-pass -- negligible above 150 kHz.
    LISN_L: float = 50e-6
    LISN_R: float = 50.0

    # H-field probe: shielded loop of RG-316, hardware/h-field-probe.md.
    PROBE_D: float = 0.010          # loop diameter [m]
    PROBE_L_SELF: float = 25e-9     # loop self-inductance [H] (~1 cm loop)
    PROBE_R_TERM: float = 50.0      # SDR input termination

    # SDR: RTL-SDR Blog v3 (direct sampling < 24 MHz, quadrature above).
    SDR_NF_DB: float = 6.0          # front-end noise figure, quadrature mode
    SDR_RBW: float = 9e3            # CISPR band-B resolution bandwidth

    @property
    def probe_area(self) -> float:
        return np.pi * (self.PROBE_D / 2) ** 2


# ---------------------------------------------------------------------------
# 4. Mitigations under study (designed in mitigations.py)
# ---------------------------------------------------------------------------
@dataclass
class Mitigations:
    # RC snubber across D1, designed by the ring-frequency method
    # (mitigations.py derives these from L_LOOP/C_NODE; standard values).
    SNUB_R: float = 8.2             # [ohm]  ~ Z0 of the ring tank
    SNUB_C: float = 1.5e-9          # [F]    ~ 3x C_NODE

    # Input pi-filter: series L + line-side cap, with an R+C damping leg
    # sized against the converter's negative input impedance.
    FILT_L: float = 22e-6
    FILT_L_DCR: float = 0.06        # winding resistance of the filter choke
    FILT_C: float = 47e-6           # line-side electrolytic
    FILT_C_ESR: float = 0.10
    FILT_C_ESL: float = 20e-9
    DAMP_C: float = 220e-6          # damping leg: C_d ~ 4-5x FILT_C
    DAMP_R: float = 1.0             # sized in mitigations.py, Middlebrook plot
    DAMP_C_ESL: float = 20e-9

    # Slowed gate drive option: tr 100 ns -> 220 ns via gate resistor.
    TR_SLOW: float = 220e-9

    # Layout rebuild: D1 lead-to-lead across Q1, return directly underneath.
    A_LOOP_TIGHT: float = 0.5e-4    # [m^2] = 0.5 cm^2


DUT = BuckDUT()
PAR = Parasitics()
CHAIN = MeasurementChain()
MIT = Mitigations()


# Plot palette -- identical to the buck-converter repo (fixed assignment,
# never cycled; gray is reserved for limits/annotations, never a series).
COL_PRIMARY = "#2E6FB7"
COL_SECONDARY = "#D9782D"
COL_TERTIARY = "#3E8E5A"
COL_ACCENT = "#8A5CB8"
COL_GRAY = "#6E6E6E"
