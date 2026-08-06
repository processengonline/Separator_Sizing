"""
Minimal calculation helpers for separator sizing.
Focused routines:
- Souders-Brown (allowable gas velocity)
- Cross-section area
- Simple diameter search for gas capacity
- Length required for liquid holdup
"""
import math
from typing import List, Optional, Dict

def souders_brown_velocity(K: float, rho_l: float, rho_g: float) -> float:
    """
    Souders-Brown allowable superficial gas velocity:
    v_allow = K * sqrt( (rho_l - rho_g) / rho_g )
    K: empirical factor in SI (m/s)
    rho_l, rho_g: kg/m3
    returns m/s
    """
    if rho_g <= 0:
        raise ValueError("rho_g must be positive")
    val = K * math.sqrt(max(rho_l - rho_g, 0.0) / rho_g)
    return val

# alias to keep names short in main script
souders_brown_velocity = souders_brown_velocity

def cross_section_area(diameter_m: float) -> float:
    """Full circular cross-sectional area (m2). For horizontal separators this is a simplification."""
    return math.pi * (diameter_m ** 2) / 4.0

def actual_gas_velocity(Qg_m3_s: float, area_m2: float) -> float:
    """Superficial gas velocity from volumetric gas flow and cross-sectional area."""
    if area_m2 <= 0:
        return float("inf")
    return Qg_m3_s / area_m2

def find_min_diameter_for_gas(Qg_m3_s: float, allowable_v_m_s: float, diameters_m: List[float]) -> Optional[Dict]:
    """Return the smallest diameter (from the list) whose area gives velocity <= allowable_v."""
    sorted_ds = sorted(diameters_m)
    for d in sorted_ds:
        a = cross_section_area(d)
        v = actual_gas_velocity(Qg_m3_s, a)
        if v <= allowable_v_m_s:
            return {"diameter_m": d, "area_m2": a, "gas_velocity_m_s": v}
    return None

def length_for_holdup(required_liquid_volume_m3: float, area_m2: float) -> float:
    """Compute length so that vessel volume = required liquid volume (simple full-volume approach)."""
    if area_m2 <= 0:
        raise ValueError("area must be positive")
    return required_liquid_volume_m3 / area_m2
