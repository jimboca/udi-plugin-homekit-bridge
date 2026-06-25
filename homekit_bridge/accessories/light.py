"""Light and dimmable light accessories."""

from __future__ import annotations

from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase


class ISYLightAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        chars = ['Brightness'] if device.traits.dimmable else None
        serv = self.add_preload_service('Lightbulb', chars=chars)
        serv.configure_char('Name', value=device.display_name)
        serv.setter_callback = self._set_chars
        self._light = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'On' in char_values:
            self.apply_hap_on(bool(char_values['On']))
        if 'Brightness' in char_values:
            self.apply_hap_brightness(int(char_values['Brightness']))

    def sync_from_isy(self, notify: bool = True) -> None:
        on = self.isy_is_on()
        self._light.configure_char('On', value=on, notify=notify)
        if self.exported.traits.dimmable:
            self._light.configure_char('Brightness', value=self.isy_brightness_hap(), notify=notify)
