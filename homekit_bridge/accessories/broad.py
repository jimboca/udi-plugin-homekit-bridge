"""Broad-mapping accessories: lock, blind, garage, temperature/humidity sensors."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase
from homekit_bridge.garage_door import (
    HAP_TARGET_CLOSED,
    HAP_TARGET_OPEN,
    aux_obstruction_detected,
    iox_to_hap_current,
    iox_to_hap_target,
)


class ISYLockAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('LockMechanism')
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
        self._set_char(self._lock, 'LockCurrentState', state, notify=notify)
        self._set_char(self._lock, 'LockTargetState', state, notify=notify)


class ISYBlindAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('WindowCovering')
        serv.setter_callback = self._set_chars
        self._shade = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'TargetPosition' in char_values:
            pos = int(char_values['TargetPosition'])
            self._turn_on(pos)

    def sync_from_isy(self, notify: bool = True) -> None:
        pos = self.isy_brightness_hap()
        self._set_char(self._shade, 'CurrentPosition', pos, notify=notify)
        self._set_char(self._shade, 'TargetPosition', pos, notify=notify)
        self._set_char(self._shade, 'PositionState', 2, notify=notify)


class ISYGarageDoorAccessory(ISYAccessoryBase):
    """GarageDoorOpener for Konnected GDO (nodeDef gdo) and hap_type=garage overrides.

    IoX: DON=open, DOF=close; ST is multi-state door index (not on/off).
    """

    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('GarageDoorOpener')
        serv.setter_callback = self._set_chars
        self._door = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'TargetDoorState' not in char_values:
            return
        target = int(char_values['TargetDoorState'])
        if target == HAP_TARGET_OPEN:
            self._turn_on()
        elif target == HAP_TARGET_CLOSED:
            self._turn_off()

    def sync_from_isy(self, notify: bool = True) -> None:
        iox = self._isy_status()
        self._set_char(self._door, 'CurrentDoorState', iox_to_hap_current(iox), notify=notify)
        self._set_char(self._door, 'TargetDoorState', iox_to_hap_target(iox), notify=notify)
        self._set_char(
            self._door,
            'ObstructionDetected',
            aux_obstruction_detected(self.exported.node),
            notify=notify,
        )


class ISYTemperatureSensorAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('TemperatureSensor')
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        value = float(self._isy_status())
        if value > 120:
            value = value / 2.0
        self._set_char(self._sensor, 'CurrentTemperature', value, notify=notify)


class ISYHumiditySensorAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('HumiditySensor')
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        value = min(100, max(0, self.isy_brightness_hap()))
        self._set_char(self._sensor, 'CurrentRelativeHumidity', float(value), notify=notify)
