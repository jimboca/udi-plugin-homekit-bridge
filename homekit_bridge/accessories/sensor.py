"""Contact and motion sensor accessories."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase


class ISYContactAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('ContactSensor')
        serv.configure_char('Name', value=device.display_name)
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        # HAP: 0 = detected/contact, 1 = not detected (normally open sensor semantics vary).
        open_contact = self._isy_status() <= 0
        self._sensor.configure_char('ContactSensorState', value=1 if open_contact else 0, notify=notify)


class ISYMotionAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('MotionSensor')
        serv.configure_char('Name', value=device.display_name)
        self._sensor = serv
        self.sync_from_isy(notify=False)

    def sync_from_isy(self, notify: bool = True) -> None:
        detected = self._isy_status() > 0
        self._sensor.configure_char('MotionDetected', value=detected, notify=notify)
