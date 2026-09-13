"""Thermostat accessory (basic heat/cool setpoints from IoX status)."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase


class ISYThermostatAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('Thermostat')
        serv.configure_char('Name', value=device.display_name)
        serv.setter_callback = self._set_chars
        self._thermostat = serv
        self.sync_from_isy(notify=False)

    def _node_value(self, attr: str, default: float) -> float:
        node = self.exported.node
        value = getattr(node, attr, None)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _set_chars(self, char_values: dict) -> None:
        if 'TargetTemperature' in char_values:
            target = float(char_values['TargetTemperature'])
            control = self._control()
            if hasattr(control, 'set_heat_cool'):
                control.set_heat_cool(target)
            elif hasattr(control, 'turn_on'):
                control.turn_on(int(target))

    def sync_from_isy(self, notify: bool = True) -> None:
        current = self._node_value('status', 70.0)
        if current > 120:
            current = current / 2.0
        target = self._node_value('status', current)
        if target > 120:
            target = target / 2.0
        self._thermostat.configure_char('CurrentTemperature', value=current, notify=notify)
        self._thermostat.configure_char('TargetTemperature', value=target, notify=notify)
        self._thermostat.configure_char('CurrentHeatingCoolingState', value=1 if current < target else 0, notify=notify)
        self._thermostat.configure_char('TargetHeatingCoolingState', value=1, notify=notify)
        self._thermostat.configure_char('TemperatureDisplayUnits', value=0, notify=notify)
