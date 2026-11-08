"""HomeKit color conversions for Kasa hue / saturation / color temperature."""

from __future__ import annotations

from typing import Any, Optional

# HAP ColorTemperature is mired (micro-reciprocal degrees), typically 140–500.
HAP_MIRED_MIN = 140
HAP_MIRED_MAX = 500
# Kasa saturation driver is 0–254. HomeKit saturation is percent.
KASA_SAT_MAX = 254


def aux_number(node: Any, control: str) -> Optional[float]:
    """Read one IoX aux driver (GV3, CLITEMP, ALARM, …) from a PyISY node."""
    props = getattr(node, 'aux_properties', None) or {}
    prop = props.get(control)
    if prop is None:
        return None
    value = getattr(prop, 'value', None)
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def kasa_sat_to_hap(sat: float) -> int:
    value = max(0.0, min(float(KASA_SAT_MAX), float(sat)))
    return int(round(value * 100 / KASA_SAT_MAX))


def hap_sat_to_kasa(sat: float) -> int:
    value = max(0.0, min(100.0, float(sat)))
    return int(round(value * KASA_SAT_MAX / 100))


def kelvin_to_mired(kelvin: float) -> int:
    if kelvin <= 0:
        return HAP_MIRED_MAX
    mired = int(round(1_000_000 / float(kelvin)))
    return max(HAP_MIRED_MIN, min(HAP_MIRED_MAX, mired))


def mired_to_kelvin(mired: float) -> int:
    if mired <= 0:
        return 0
    return int(round(1_000_000 / float(mired)))


def light_optional_chars(traits: Any) -> Optional[list]:
    """HAP-python Lightbulb optional characteristics, or None for On only."""
    chars: list = []
    if getattr(traits, 'dimmable', False) or getattr(traits, 'color', False):
        chars.append('Brightness')
    if getattr(traits, 'color', False):
        chars.extend(['Hue', 'Saturation'])
    if getattr(traits, 'color_temperature', False):
        chars.append('ColorTemperature')
    return chars or None
