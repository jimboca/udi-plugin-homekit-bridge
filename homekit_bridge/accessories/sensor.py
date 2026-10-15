"""Contact and motion sensor accessories."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase


class ISYContactAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('ContactSensor')
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        # HAP: 0 = detected/contact, 1 = not detected (normally open sensor semantics vary).
        open_contact = self._isy_status() <= 0
        self._set_char(self._sensor, 'ContactSensorState', 1 if open_contact else 0, notify=notify)


class ISYMotionAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('MotionSensor')
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        detected = self._isy_status() > 0
        self._set_char(self._sensor, 'MotionDetected', detected, notify=notify)
