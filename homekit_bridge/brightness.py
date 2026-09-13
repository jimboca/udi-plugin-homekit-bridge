"""Brightness conversion between IoX (0-255) and HomeKit (0-100)."""

from __future__ import annotations


def isy_to_hap_brightness(isy_value: int) -> int:
    value = max(0, min(255, int(isy_value)))
    return round(value * 100 / 255)


def hap_to_isy_brightness(hap_value: int) -> int:
    value = max(0, min(100, int(hap_value)))
    return round(value * 255 / 100)
