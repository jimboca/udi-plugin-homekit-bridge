"""Broad-mapping accessories: lock, blind, temperature/humidity sensors."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase


class ISYLockAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('LockMechanism')
        serv.configure_char('Name', value=device.display_name)
        serv.setter_callback = self._set_chars
        self._lock = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'LockTargetState' in char_values:
            locked = int(char_values['LockTargetState']) == 1
            if locked:
                self._turn_on()
            else:
                self._turn_off()

    def sync_from_isy(self, notify: bool = True) -> None:
        locked = self.isy_is_on()
        state = 1 if locked else 0
        self._lock.configure_char('LockCurrentState', value=state, notify=notify)
        self._lock.configure_char('LockTargetState', value=state, notify=notify)


class ISYBlindAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('WindowCovering')
        serv.configure_char('Name', value=device.display_name)
        serv.setter_callback = self._set_chars
        self._shade = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'TargetPosition' in char_values:
            pos = int(char_values['TargetPosition'])
            self._turn_on(pos)

    def sync_from_isy(self, notify: bool = True) -> None:
        pos = self.isy_brightness_hap()
        self._shade.configure_char('CurrentPosition', value=pos, notify=notify)
        self._shade.configure_char('TargetPosition', value=pos, notify=notify)
        self._shade.configure_char('PositionState', value=2, notify=notify)


class ISYTemperatureSensorAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('TemperatureSensor')
        serv.configure_char('Name', value=device.display_name)
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        value = float(self._isy_status())
        if value > 120:
            value = value / 2.0
        self._sensor.configure_char('CurrentTemperature', value=value, notify=notify)


class ISYHumiditySensorAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('HumiditySensor')
        serv.configure_char('Name', value=device.display_name)
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        value = min(100, max(0, self.isy_brightness_hap()))
        self._sensor.configure_char('CurrentRelativeHumidity', value=float(value), notify=notify)
