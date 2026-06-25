"""On/off switch accessories."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase


class ISYSwitchAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('Switch')
        serv.configure_char('Name', value=device.display_name)
        serv.setter_callback = self._set_chars
        self._switch = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'On' in char_values:
            self.apply_hap_on(bool(char_values['On']))

    def sync_from_isy(self, notify: bool = True) -> None:
        self._switch.configure_char('On', value=self.isy_is_on(), notify=notify)
