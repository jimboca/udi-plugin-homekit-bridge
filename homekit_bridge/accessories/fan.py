"""Fan accessories."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase
from homekit_bridge.brightness import hap_to_isy_brightness, isy_to_hap_brightness


class ISYFanAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('Fan', chars=['RotationSpeed'])
        serv.configure_char('Name', value=device.display_name)
        serv.setter_callback = self._set_chars
        self._fan = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'On' in char_values:
            self.apply_hap_on(bool(char_values['On']))
        if 'RotationSpeed' in char_values:
            speed = int(char_values['RotationSpeed'])
            if speed <= 0:
                self._turn_off()
            else:
                self._turn_on(hap_to_isy_brightness(speed))

    def sync_from_isy(self, notify: bool = True) -> None:
        on = self.isy_is_on()
        self._fan.configure_char('On', value=on, notify=notify)
        self._fan.configure_char('RotationSpeed', value=self.isy_brightness_hap() if on else 0, notify=notify)
