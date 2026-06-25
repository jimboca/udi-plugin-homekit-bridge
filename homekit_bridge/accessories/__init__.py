"""Accessory factory for exported ISY devices."""

from __future__ import annotations

from typing import Any, Callable, Optional, Type

from const import (
    HAP_TYPE_BLIND,
    HAP_TYPE_CONTACT,
    HAP_TYPE_FAN,
    HAP_TYPE_HUMIDITY_SENSOR,
    HAP_TYPE_LIGHT,
    HAP_TYPE_LOCK,
    HAP_TYPE_MOTION,
    HAP_TYPE_SWITCH,
    HAP_TYPE_TEMP_SENSOR,
    HAP_TYPE_THERMOSTAT,
)
from homekit_bridge.accessories.broad import (
    ISYBlindAccessory,
    ISYHumiditySensorAccessory,
    ISYLockAccessory,
    ISYTemperatureSensorAccessory,
)
from homekit_bridge.accessories.fan import ISYFanAccessory
from homekit_bridge.accessories.light import ISYLightAccessory
from homekit_bridge.accessories.sensor import ISYContactAccessory, ISYMotionAccessory
from homekit_bridge.accessories.switch import ISYSwitchAccessory
from homekit_bridge.accessories.thermostat import ISYThermostatAccessory
from homekit_bridge.isy_scanner import ExportedDevice

AccessoryFactory = Callable[[Any, ExportedDevice, Optional[Callable[[str], None]]], Any]

_REGISTRY: dict[str, Type] = {
    HAP_TYPE_LIGHT: ISYLightAccessory,
    HAP_TYPE_SWITCH: ISYSwitchAccessory,
    HAP_TYPE_FAN: ISYFanAccessory,
    HAP_TYPE_THERMOSTAT: ISYThermostatAccessory,
    HAP_TYPE_CONTACT: ISYContactAccessory,
    HAP_TYPE_MOTION: ISYMotionAccessory,
    HAP_TYPE_LOCK: ISYLockAccessory,
    HAP_TYPE_BLIND: ISYBlindAccessory,
    HAP_TYPE_TEMP_SENSOR: ISYTemperatureSensorAccessory,
    HAP_TYPE_HUMIDITY_SENSOR: ISYHumiditySensorAccessory,
}


def build_accessory(
    driver: Any,
    device: ExportedDevice,
    on_isy_change: Optional[Callable[[str], None]] = None,
):
    cls = _REGISTRY.get(device.hap_type, ISYSwitchAccessory)
    return cls(driver, device, on_isy_change=on_isy_change)
