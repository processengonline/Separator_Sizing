#!/usr/bin/env python3
"""
Minimal separator sizing CLI (2-/3-phase baseline).
Usage:
  python separator_sizing.py inputs.yaml
The YAML format is simple and an example is shown in the README.
"""
import argparse
import yaml
from utils import calculations

def load_inputs(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def format_report(result):
    return f"""---------------------------------------
Separator Sizing Results
---------------------------------------
Recommended Diameter : {result['diameter_m']:.2f} m
Recommended Length   : {result['length_m']:.2f} m
Gas Velocity         : {result['gas_velocity_m_s']:.3f} m/s
Allowable Velocity   : {result['allowable_velocity_m_s']:.3f} m/s
Residence Time       : {result['residence_time_min']:.2f} min
L/D Ratio            : {result['l_to_d']:.2f}
Gas Capacity Check   : {'PASS' if result['gas_ok'] else 'FAIL'}
Residence Time Check : {'PASS' if result['residence_ok'] else 'FAIL'}
API Geometry Check   : {'PASS' if result['ld_ok'] else 'FAIL'}
Overall Status       : {'ACCEPTABLE' if result['gas_ok'] and result['residence_ok'] and result['ld_ok'] else 'REVISE'}
"""

def main():
    parser = argparse.ArgumentParser(description="Minimal Separator Sizing")
    parser.add_argument("input_yaml", help="YAML file with inputs")
    args = parser.parse_args()

    cfg = load_inputs(args.input_yaml)

    # Required inputs (simple names)
    Qg = float(cfg.get("gas_flow_m3_s", 0.0))          # gas vol flow m3/s
    Qo = float(cfg.get("oil_flow_m3_s", 0.0))          # oil vol flow m3/s
    Qw = float(cfg.get("water_flow_m3_s", 0.0))        # water vol flow m3/s
    rho_g = float(cfg.get("rho_g_kg_m3", 1.2))         # gas density
    rho_l = float(cfg.get("rho_l_kg_m3", 800.0))       # liquid density (use an average for oil/water mix)
    K = float(cfg.get("k_factor_m_s", 0.107))          # K-factor (m/s) typical range 0.02-0.25 depending on service; default 0.107 ~ 0.85 ft/s
    residence_time_min = float(cfg.get("residence_time_min", 5.0))
    min_L_over_D = float(cfg.get("min_L_over_D", 2.5))
    max_L_over_D = float(cfg.get("max_L_over_D", 5.0))

    # diameters to try (either list or generate)
    diameters = cfg.get("diameters_m")
    if diameters is None:
        d_min = float(cfg.get("diameter_min_m", 0.5))
        d_max = float(cfg.get("diameter_max_m", 3.0))
        d_step = float(cfg.get("diameter_step_m", 0.1))
        diameters = [round(d_min + i*d_step, 6) for i in range(int((d_max - d_min)/d_step) + 1)]

    # computations
    allowable_v = calculations.souders_brown_velocity(K, rho_l, rho_g)  # m/s
    chosen = calculations.find_min_diameter_for_gas(Qg, allowable_v, diameters)

    if chosen is None:
        print("No diameter in the provided range meets the gas capacity requirement.")
        return

    D = chosen["diameter_m"]
    gas_area = calculations.cross_section_area(D)
    # liquid holdup required (m3) = (Qo + Qw) * residence_time (s)
    res_time_s = residence_time_min * 60.0
    required_liquid_vol = (Qo + Qw) * res_time_s
    # Simple holdup: vessel internal volume = area * L
    L_for_holdup = calculations.length_for_holdup(required_liquid_vol, gas_area)
    # Ensure L satisfies L/D ratio limits
    L_min_geo = min_L_over_D * D
    L = max(L_for_holdup, L_min_geo)
    l_to_d = L / D

    result = {
        "diameter_m": D,
        "length_m": L,
        "gas_velocity_m_s": calculations.actual_gas_velocity(Qg, gas_area),
        "allowable_velocity_m_s": allowable_v,
        "residence_time_min": residence_time_min,
        "l_to_d": l_to_d,
        "gas_ok": calculations.actual_gas_velocity(Qg, gas_area) <= allowable_v,
        "residence_ok": L >= L_for_holdup - 1e-6,
        "ld_ok": (l_to_d >= min_L_over_D) and (l_to_d <= max_L_over_D)
    }

    print(format_report(result))

if __name__ == "__main__":
    main()
