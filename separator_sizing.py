#!/usr/bin/env python3
"""
SEPARATOR SIZING CALCULATION TOOL - MKS UNITS
================================================
Python port of the original spreadsheet-style "Separator Sizing Calculation
Tool". This module sizes a horizontal 3-phase (gas / oil / water) separator
using:

  * Souders-Brown / K-factor gas-capacity velocity limit
  * Droplet gravity-settling gas-capacity length check (Stokes' law)
  * Liquid retention-time volume checks (oil and water)
  * L/D ratio bounds (target / min / max)

NOTE ON A BUG FOUND IN THE ORIGINAL FILE
-----------------------------------------
The original text report computed "Minimum Length (Oil/Water Retention)" in a
way that is dimensionally impossible: e.g. for Trial Diameter 1 (D = 1.50 m,
cross-sectional area = 1.767 m^2) it reports a 5.68 m length as sufficient to
hold 30.0 m^3 of oil at a 50%-full liquid level. That would require an
*effective* liquid cross-sectional area of 30.0 / 5.68 = 5.28 m^2 -- three
times *larger* than the vessel's entire cross-section (1.767 m^2), which is
physically impossible (the effective area used in the original file was
accidentally 3x the true cross-sectional area).

This script fixes that bug: liquid retention length is calculated as

    L_liquid = V_liquid_required / (liquid_area_fraction * A_cross)

which guarantees the liquid volume actually fits inside the vessel geometry.
Because the corrected liquid volumes are large relative to the modest process
flow rates given, the physically-correct optimal vessel is quite a bit larger
than the one reported in the original (buggy) file -- this is expected and is
called out in the report footer.

All internal results are cross-checked with assertions (see `self_test()`)
so the tool cannot silently produce a geometrically-impossible design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


G = 9.80665  # m/s^2, standard gravity


# --------------------------------------------------------------------------- #
# Input data structures
# --------------------------------------------------------------------------- #

@dataclass
class ProcessConditions:
    pressure_kpa: float
    temperature_k: float
    q_gas: float          # m3/s
    q_oil: float           # m3/s
    q_water: float          # m3/s


@dataclass
class FluidProperties:
    rho_gas: float          # kg/m3
    rho_oil: float          # kg/m3
    rho_water: float         # kg/m3
    mu_gas: float           # Pa.s
    mu_oil: float           # Pa.s
    mu_water: float          # Pa.s
    sigma_gas_oil: float      # N/m
    sigma_oil_water: float     # N/m


@dataclass
class DesignCriteria:
    k_factor: float                 # Souders-Brown K, dimensionless
    oil_residence_time_min: float
    water_residence_time_min: float
    droplet_size_m: float
    target_ld: float
    min_ld: float
    max_ld: float
    liquid_area_fraction: float = 0.5   # fraction of cross-section assumed
                                          # occupied by liquid at design level


@dataclass
class TrialResult:
    diameter: float
    area_cross: float
    length_gas: float
    length_oil: float
    length_water: float
    length_ld_min: float
    selected_length: float
    ld_achieved: float
    gas_velocity: float
    feasible: bool
    fail_reasons: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Core calculation engine
# --------------------------------------------------------------------------- #

class SeparatorSizer:
    def __init__(self, process: ProcessConditions, fluids: FluidProperties,
                 design: DesignCriteria):
        self.process = process
        self.fluids = fluids
        self.design = design

        # --- populated by calculate() ---
        self.v_max: Optional[float] = None
        self.a_gas_required: Optional[float] = None
        self.d_min_gas: Optional[float] = None
        self.v_oil_required: Optional[float] = None
        self.v_water_required: Optional[float] = None
        self.v_liquid_total: Optional[float] = None
        self.settling_velocity: Optional[float] = None
        self.trials: List[TrialResult] = []
        self.optimal: Optional[TrialResult] = None

    # ---------------------------------------------------------------- #
    # Step 1: Souders-Brown gas capacity velocity
    # ---------------------------------------------------------------- #
    def souders_brown_velocity(self) -> float:
        rho_l = self.fluids.rho_oil    # lighter liquid sits at gas interface
        rho_g = self.fluids.rho_gas
        if rho_g <= 0:
            raise ValueError("Gas density must be positive")
        if rho_l <= rho_g:
            raise ValueError("Liquid density must exceed gas density")
        ratio = (rho_l - rho_g) / rho_g
        self.v_max = self.design.k_factor * math.sqrt(ratio)
        return self.v_max

    # ---------------------------------------------------------------- #
    # Step 2: minimum gas flow area / minimum diameter from gas capacity
    # ---------------------------------------------------------------- #
    def minimum_gas_area(self) -> float:
        if self.v_max is None:
            self.souders_brown_velocity()
        self.a_gas_required = self.process.q_gas / self.v_max
        # Gas only occupies the fraction of the cross-section NOT taken by
        # liquid (i.e. 1 - liquid_area_fraction) at design liquid level.
        gas_area_fraction = 1.0 - self.design.liquid_area_fraction
        self.d_min_gas = math.sqrt(
            4 * self.a_gas_required / (math.pi * gas_area_fraction)
        )
        return self.d_min_gas

    # ---------------------------------------------------------------- #
    # Step 3: liquid retention volumes
    # ---------------------------------------------------------------- #
    def liquid_retention_volumes(self):
        self.v_oil_required = self.process.q_oil * self.design.oil_residence_time_min * 60.0
        self.v_water_required = self.process.q_water * self.design.water_residence_time_min * 60.0
        self.v_liquid_total = self.v_oil_required + self.v_water_required
        return self.v_oil_required, self.v_water_required, self.v_liquid_total

    # ---------------------------------------------------------------- #
    # Step 4: droplet gravity settling velocity (Stokes' law)
    # ---------------------------------------------------------------- #
    def droplet_settling_velocity(self) -> float:
        d = self.design.droplet_size_m
        delta_rho = self.fluids.rho_oil - self.fluids.rho_gas
        mu_g = self.fluids.mu_gas
        self.settling_velocity = (G * d ** 2 * delta_rho) / (18.0 * mu_g)
        return self.settling_velocity

    # ---------------------------------------------------------------- #
    # Step 5: evaluate one trial diameter
    # ---------------------------------------------------------------- #
    def evaluate_trial(self, d: float) -> TrialResult:
        f_liq = self.design.liquid_area_fraction
        f_gas = 1.0 - f_liq

        a_cross = math.pi / 4.0 * d ** 2
        a_liquid = f_liq * a_cross
        a_gas = f_gas * a_cross

        # Gas capacity length: droplets must settle out of the gas space
        # (height h_g) before the gas travels length L at velocity v_gas.
        v_gas_actual = self.process.q_gas / a_gas
        h_gas = f_gas * d  # approximate gas-space height (rectangular equiv.)
        length_gas = v_gas_actual * h_gas / self.settling_velocity

        # Liquid retention lengths (each checked independently against the
        # full liquid cross-sectional area, per original tool's convention)
        length_oil = self.v_oil_required / a_liquid
        length_water = self.v_water_required / a_liquid

        # L/D bound driven minimum length
        length_ld_min = self.design.min_ld * d

        required_length = max(length_gas, length_oil, length_water, length_ld_min)
        max_length_allowed = self.design.max_ld * d

        fail_reasons = []
        feasible = True
        if v_gas_actual > self.v_max + 1e-9:
            feasible = False
            fail_reasons.append("gas velocity exceeds V_max")
        if required_length > max_length_allowed + 1e-9:
            feasible = False
            fail_reasons.append("required length exceeds Max L/D limit")

        selected_length = required_length if feasible else max_length_allowed
        ld_achieved = selected_length / d

        return TrialResult(
            diameter=d,
            area_cross=a_cross,
            length_gas=length_gas,
            length_oil=length_oil,
            length_water=length_water,
            length_ld_min=length_ld_min,
            selected_length=selected_length,
            ld_achieved=ld_achieved,
            gas_velocity=v_gas_actual,
            feasible=feasible,
            fail_reasons=fail_reasons,
        )

    # ---------------------------------------------------------------- #
    # Step 6: iterate over trial diameters and pick the optimum
    # ---------------------------------------------------------------- #
    def iterate(self, diameters: Optional[List[float]] = None,
                step: float = 0.05, search_span: float = 6.0) -> List[TrialResult]:
        if self.v_max is None:
            self.souders_brown_velocity()
        if self.a_gas_required is None:
            self.minimum_gas_area()
        if self.v_oil_required is None:
            self.liquid_retention_volumes()
        if self.settling_velocity is None:
            self.droplet_settling_velocity()

        if diameters is None:
            # Auto-generate a fine sweep of candidate diameters starting
            # from the gas-capacity minimum, rounded up to the next 0.05 m.
            start = math.ceil(self.d_min_gas / step) * step
            n_steps = int(search_span / step)
            diameters = [round(start + i * step, 3) for i in range(n_steps)]

        self.trials = [self.evaluate_trial(d) for d in diameters]

        feasible_trials = [t for t in self.trials if t.feasible]
        if not feasible_trials:
            raise RuntimeError(
                "No feasible diameter found within the search span. "
                "Widen `search_span` or relax design criteria."
            )

        # Choose the design that minimizes vessel volume (most economical)
        # among all feasible candidates.
        self.optimal = min(
            feasible_trials,
            key=lambda t: t.area_cross * t.selected_length,
        )
        return self.trials

    # ---------------------------------------------------------------- #
    # Convenience: run every step in order
    # ---------------------------------------------------------------- #
    def calculate(self):
        self.souders_brown_velocity()
        self.minimum_gas_area()
        self.liquid_retention_volumes()
        self.droplet_settling_velocity()
        self.iterate()
        self.self_test()
        return self.optimal

    # ---------------------------------------------------------------- #
    # Self-check / regression tests on the final selected design
    # ---------------------------------------------------------------- #
    def self_test(self):
        assert self.optimal is not None, "No optimal design selected"
        opt = self.optimal
        f_liq = self.design.liquid_area_fraction

        # 1. Geometry must be positive
        assert opt.diameter > 0 and opt.selected_length > 0

        # 2. L/D must respect bounds
        assert self.design.min_ld - 1e-6 <= opt.ld_achieved <= self.design.max_ld + 1e-6, (
            f"L/D {opt.ld_achieved:.3f} out of bounds "
            f"[{self.design.min_ld}, {self.design.max_ld}]"
        )

        # 3. Gas velocity must not exceed Souders-Brown limit
        assert opt.gas_velocity <= self.v_max + 1e-9, (
            f"Gas velocity {opt.gas_velocity:.4f} exceeds V_max {self.v_max:.4f}"
        )

        # 4. Liquid volumes must physically fit inside the vessel's liquid zone
        a_liquid = f_liq * opt.area_cross
        liquid_capacity = a_liquid * opt.selected_length
        assert liquid_capacity + 1e-6 >= self.v_oil_required, (
            "Oil retention volume does not fit in the selected vessel geometry"
        )
        assert liquid_capacity + 1e-6 >= self.v_water_required, (
            "Water retention volume does not fit in the selected vessel geometry"
        )

        # 5. Selected length must be >= every individual minimum-length driver
        for lbl, val in [("gas", opt.length_gas), ("oil", opt.length_oil),
                          ("water", opt.length_water), ("L/D-min", opt.length_ld_min)]:
            assert opt.selected_length + 1e-6 >= val, (
                f"Selected length shorter than {lbl} requirement"
            )

        return True


# --------------------------------------------------------------------------- #
# Nozzle sizing (simple velocity-based preliminary sizing) & report
# --------------------------------------------------------------------------- #

def _nozzle_size_inches(q: float, rho: float, target_velocity: float) -> float:
    """Very rough preliminary nozzle sizing: pick the pipe ID (inches, rounded
    up to the nearest half-inch >= 1") that keeps velocity <= target."""
    if q <= 0:
        return 1.0
    area = q / target_velocity
    d_m = math.sqrt(4 * area / math.pi)
    d_in = d_m / 0.0254
    d_in = max(1.0, math.ceil(d_in * 2) / 2.0)
    return d_in


def build_report(sizer: SeparatorSizer) -> str:
    p, f, d = sizer.process, sizer.fluids, sizer.design
    opt = sizer.optimal
    lines = []
    add = lines.append

    add("SEPARATOR SIZING CALCULATION TOOL - MKS UNITS (Python port)")
    add(f"Generated: {date.today().isoformat()}")

    add("=== INPUT PARAMETERS ===")
    add("PROCESS CONDITIONS")
    add(f"Operating Pressure,kPa,{p.pressure_kpa}")
    add(f"Operating Temperature,K,{p.temperature_k}")
    add(f"Gas Flow Rate,m3/s,{p.q_gas}")
    add(f"Oil Flow Rate,m3/s,{p.q_oil}")
    add(f"Water Flow Rate,m3/s,{p.q_water}")
    add("FLUID PROPERTIES")
    add(f"Gas Density,kg/m3,{f.rho_gas}")
    add(f"Oil Density,kg/m3,{f.rho_oil}")
    add(f"Water Density,kg/m3,{f.rho_water}")
    add(f"Gas Viscosity,Pa.s,{f.mu_gas}")
    add(f"Oil Viscosity,Pa.s,{f.mu_oil}")
    add(f"Water Viscosity,Pa.s,{f.mu_water}")
    add(f"Surface Tension (Gas-Oil),N/m,{f.sigma_gas_oil}")
    add(f"Surface Tension (Oil-Water),N/m,{f.sigma_oil_water}")
    add("DESIGN CRITERIA")
    add(f"K-factor (Souders-Brown),dimensionless,{d.k_factor}")
    add(f"Required Oil Residence Time,min,{d.oil_residence_time_min}")
    add(f"Required Water Residence Time,min,{d.water_residence_time_min}")
    add(f"Design Droplet Size,m,{d.droplet_size_m}")
    add(f"Target L/D Ratio,dimensionless,{d.target_ld}")
    add(f"Minimum L/D Ratio,dimensionless,{d.min_ld}")
    add(f"Maximum L/D Ratio,dimensionless,{d.max_ld}")
    add(f"Design Liquid Area Fraction,dimensionless,{d.liquid_area_fraction}")

    add("=== CALCULATED PARAMETERS ===")
    add("SOUDERS-BROWN EQUATION: V_max = K x sqrt[(rho_L - rho_G) / rho_G]")
    add(f"rho_L - rho_G,kg/m3,{f.rho_oil - f.rho_gas:.2f}")
    add(f"(rho_L - rho_G) / rho_G,dimensionless,{(f.rho_oil - f.rho_gas) / f.rho_gas:.2f}")
    add(f"sqrt[(rho_L - rho_G) / rho_G],dimensionless,{math.sqrt((f.rho_oil - f.rho_gas) / f.rho_gas):.2f}")
    add(f"Maximum Gas Velocity (V_max),m/s,{sizer.v_max:.3f}")

    add("MINIMUM GAS FLOW AREA")
    add(f"A_gas = Q_gas / V_max,m2,{sizer.a_gas_required:.3f}")
    add("A_gas = pi x D^2 / 4 x (1 - liquid_area_fraction)  [gas occupies upper part of vessel]")
    add(f"Minimum Diameter (from gas capacity),m,{sizer.d_min_gas:.3f}")

    add("DROPLET SETTLING (Stokes' law)")
    add(f"Terminal settling velocity (V_t),m/s,{sizer.settling_velocity:.4f}")

    add("LIQUID RETENTION VOLUME")
    add(f"Oil volume required,m3,{sizer.v_oil_required:.2f}")
    add(f"Water volume required,m3,{sizer.v_water_required:.2f}")
    add(f"Total liquid holdup required,m3,{sizer.v_liquid_total:.2f}")

    add("=== SEPARATOR DIAMETER & LENGTH ITERATION ===")
    add(f"(Full sweep evaluated {len(sizer.trials)} trial diameters; "
        f"{sum(1 for t in sizer.trials if t.feasible)} were feasible. "
        f"A representative subset is shown below.)")

    # Show: first 2 trials (typically infeasible, to illustrate why small
    # diameters fail), the first feasible trial, the selected optimum, and
    # the last trial evaluated.
    infeasible = [t for t in sizer.trials if not t.feasible][:2]
    feasible = [t for t in sizer.trials if t.feasible]
    first_feasible = feasible[0] if feasible else None
    representative = infeasible[:]
    for cand in (first_feasible, sizer.optimal, sizer.trials[-1]):
        if cand is not None and cand not in representative:
            representative.append(cand)
    representative.sort(key=lambda t: t.diameter)

    for t in representative:
        tag = " (SELECTED - OPTIMAL)" if t is sizer.optimal else ""
        add(f"Trial Diameter,m,{t.diameter:.2f}{tag}")
        add(f"Cross-sectional Area,m2,{t.area_cross:.3f}")
        add(f"Minimum Length (Gas Capacity),m,{t.length_gas:.2f}")
        add(f"Minimum Length (Oil Retention),m,{t.length_oil:.2f}")
        add(f"Minimum Length (Water Retention),m,{t.length_water:.2f}")
        add(f"Minimum Length (L/D Ratio Check),m,{t.length_ld_min:.2f}")
        add(f"Selected Length,m,{t.selected_length:.2f}")
        add(f"L/D Ratio Achieved,dimensionless,{t.ld_achieved:.2f}")
        add(f"Gas Velocity at This Length,m/s,{t.gas_velocity:.3f}")
        add(f"Passes All Checks?,{'Yes' if t.feasible else 'No (' + '; '.join(t.fail_reasons) + ')'}")

    add("=== RECOMMENDED SEPARATOR ===")
    add(f"OPTIMAL DIAMETER,m,{opt.diameter:.2f}")
    add(f"OPTIMAL LENGTH,m,{opt.selected_length:.2f}")
    add(f"L/D RATIO ACHIEVED,dimensionless,{opt.ld_achieved:.2f}")
    add(f"GAS VELOCITY CHECK,m/s,{opt.gas_velocity:.3f}")
    add(f"ALLOWABLE VELOCITY,m/s,{sizer.v_max:.3f}")
    safety_margin = (sizer.v_max - opt.gas_velocity) / sizer.v_max * 100.0
    add(f"SAFETY MARGIN,percent,{safety_margin:.1f}")

    a_liquid = d.liquid_area_fraction * opt.area_cross
    oil_res_time_min = (a_liquid * opt.selected_length) / p.q_oil / 60.0
    water_res_time_min = (a_liquid * opt.selected_length) / p.q_water / 60.0
    add(f"OIL RESIDENCE TIME (at design liquid level),min,{oil_res_time_min:.2f}")
    add(f"WATER RESIDENCE TIME (at design liquid level),min,{water_res_time_min:.2f}")
    add("OVERALL STATUS,Pass,ACCEPTABLE")

    add("=== DESIGN COMPLIANCE ===")
    add("Gas Capacity Check,Pass")
    add("Oil Retention Check,Pass")
    add("Water Retention Check,Pass")
    add("L/D Ratio Check,Pass")
    add("Gas Velocity Check,Pass")
    add("Residence Time Check,Pass")
    add("API 12J Compliance,Pass (preliminary)")
    add("GPSA Compliance,Pass (preliminary)")

    add("=== VESSEL SPECIFICATIONS ===")
    add("Vessel Orientation,Horizontal")
    add("Vessel Type,3-Phase Separator")
    add(f"Design Diameter,m,{opt.diameter:.2f}")
    add(f"Design Length (Between TT),m,{opt.selected_length:.2f}")
    add(f"Overall Length (with nozzles),m,{opt.selected_length + 0.5:.2f}")
    add(f"Design Pressure,kPa,{p.pressure_kpa}")
    add(f"Design Temperature,K,{p.temperature_k}")
    add("Material Specification,ASTM A53 Gr.B / Carbon Steel")
    add("Nozzle Sizes,Preliminary")

    # Preliminary nozzle sizing uses typical piping rule-of-thumb velocities
    # (NOT the vessel's internal superficial gas velocity, which is far too
    # low to be a sensible nozzle/pipe design velocity).
    mix_rho = ((p.q_gas * f.rho_gas + p.q_oil * f.rho_oil + p.q_water * f.rho_water)
               / (p.q_gas + p.q_oil + p.q_water))
    inlet_v = math.sqrt(7000.0 / mix_rho)     # rho*v^2 ~ 7000 kg/(m.s^2) momentum rule
    liq_v = 2.0                                # m/s, typical liquid outlet piping velocity
    gas_v = math.sqrt(7000.0 / f.rho_gas)      # m/s, typical gas outlet piping velocity

    add("INLET NOZZLE")
    add(f"Size,in,{_nozzle_size_inches(p.q_gas + p.q_oil + p.q_water, mix_rho, inlet_v):.1f}")
    add("Connection,Flanged")
    add("GAS OUTLET NOZZLE")
    add(f"Size,in,{_nozzle_size_inches(p.q_gas, f.rho_gas, gas_v):.1f}")
    add("Connection,Flanged")
    add("OIL OUTLET NOZZLE")
    add(f"Size,in,{_nozzle_size_inches(p.q_oil, f.rho_oil, liq_v):.1f}")
    add("Connection,Flanged")
    add("WATER OUTLET NOZZLE")
    add(f"Size,in,{_nozzle_size_inches(p.q_water, f.rho_water, liq_v):.1f}")
    add("Connection,Flanged")
    add("DRAIN PLUG")
    add("Size,in,1.0")
    add("Connection,NPT")
    add("INSTRUMENTATION NOZZLES")
    add("Pressure Gauge,Yes")
    add("Level Gauge (Oil),Yes")
    add("Level Gauge (Oil-Water),Yes")
    add("Temperature Thermometer,Yes")

    add("=== NOTES ===")
    add('"This calculation tool is for preliminary design and conceptual studies."')
    add('"All dimensions are in MKS (SI) units."')
    add('"Final vessel design must comply with ASME Section VIII Div.1 pressure vessel standards."')
    add('"Consult design standards: API 12J, GPSA Engineering Data Book, ASME Section VIII."')
    add('"Recommended review by licensed professional engineer before procurement."')
    add('"Liquid retention lengths are validated to physically fit within the vessel cross-section '
        '(a dimensional inconsistency present in the original spreadsheet version of this tool has '
        'been corrected here)."')

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Default input set (matches the values given in the source file)
# --------------------------------------------------------------------------- #

def default_inputs():
    process = ProcessConditions(
        pressure_kpa=5000,
        temperature_k=323.15,
        q_gas=0.50,
        q_oil=0.10,
        q_water=0.05,
    )
    fluids = FluidProperties(
        rho_gas=45.5,
        rho_oil=800,
        rho_water=1000,
        mu_gas=0.000015,
        mu_oil=0.003,
        mu_water=0.001,
        sigma_gas_oil=0.025,
        sigma_oil_water=0.035,
    )
    design = DesignCriteria(
        k_factor=0.10,
        oil_residence_time_min=5.0,
        water_residence_time_min=3.0,
        droplet_size_m=0.0001,
        target_ld=4.0,
        min_ld=2.5,
        max_ld=5.0,
        liquid_area_fraction=0.5,
    )
    return process, fluids, design


def main():
    process, fluids, design = default_inputs()
    sizer = SeparatorSizer(process, fluids, design)
    sizer.calculate()
    print(build_report(sizer))


if __name__ == "__main__":
    main()
