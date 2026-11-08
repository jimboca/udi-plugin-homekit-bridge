"""Light, dimmer, and color-light accessories."""

from __future__ import annotations

import logging
from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase
from homekit_bridge.color import (
    aux_number,
    hap_sat_to_kasa,
    kasa_sat_to_hap,
    kelvin_to_mired,
    light_optional_chars,
    mired_to_kelvin,
)

LOGGER = logging.getLogger(__name__)


class ISYLightAccessory(ISYAccessoryBase):
    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        chars = light_optional_chars(device.traits)
        serv = self.add_preload_service('Lightbulb', chars=chars)
        serv.setter_callback = self._set_chars
        self._light = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'On' in char_values:
            self.apply_hap_on(bool(char_values['On']))
        if 'Brightness' in char_values:
            self.apply_hap_brightness(int(char_values['Brightness']))
        if 'Hue' in char_values:
            self._send_kasa('SET_HUE', int(round(float(char_values['Hue']))))
        if 'Saturation' in char_values:
            self._send_kasa('SET_SAT', hap_sat_to_kasa(char_values['Saturation']))
        if 'ColorTemperature' in char_values:
            kelvin = mired_to_kelvin(char_values['ColorTemperature'])
            if kelvin > 0:
                self._send_kasa('CLITEMP', kelvin)

    def _send_kasa(self, cmd: str, value: int) -> None:
        control = self._control()
        send = getattr(control, 'send_cmd', None)
        if not callable(send):
            LOGGER.warning('No send_cmd for %s; skipped %s', self.exported.address, cmd)
            return
        try:
            send(cmd, int(value))
        except Exception:
            LOGGER.warning(
                'IoX command %s=%s failed for %s',
                cmd,
                value,
                self.exported.address,
                exc_info=True,
            )

    def apply_hap_brightness(self, hap_value: int) -> None:
        if self.exported.traits.brightness_percent:
            level = max(0, min(100, int(hap_value)))
            if level <= 0:
                self._turn_off()
            else:
                self._turn_on(level)
            return
        super().apply_hap_brightness(hap_value)

    def _brightness_hap(self) -> int:
        if self.exported.traits.brightness_percent:
            return max(0, min(100, self._isy_status()))
        return self.isy_brightness_hap()

    def sync_from_isy(self, notify: bool = True) -> None:
        on = self.isy_is_on()
        self._set_char(self._light, 'On', on, notify=notify)
        traits = self.exported.traits
        if traits.dimmable or traits.color:
            self._set_char(self._light, 'Brightness', self._brightness_hap(), notify=notify)
        if traits.color:
            hue = aux_number(self.exported.node, 'GV3')
            sat = aux_number(self.exported.node, 'GV4')
            if hue is not None:
                self._set_char(self._light, 'Hue', max(0, min(360, int(round(hue)))), notify=notify)
            if sat is not None:
                self._set_char(self._light, 'Saturation', kasa_sat_to_hap(sat), notify=notify)
        if traits.color_temperature:
            kelvin = aux_number(self.exported.node, 'CLITEMP')
            if kelvin is not None and kelvin > 0:
                self._set_char(
                    self._light,
                    'ColorTemperature',
                    kelvin_to_mired(kelvin),
                    notify=notify,
                )
