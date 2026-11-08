"""On/off switch, outlet, and valve accessories."""

from __future__ import annotations

import logging
from typing import Any

from homekit_bridge.accessories.base import ISYAccessoryBase

LOGGER = logging.getLogger(__name__)


class ISYSwitchAccessory(ISYAccessoryBase):
    service_name = 'Switch'

    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service(self.service_name)
        serv.setter_callback = self._set_chars
        self._switch = serv
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'On' in char_values:
            self.apply_hap_on(bool(char_values['On']))

    def sync_from_isy(self, notify: bool = True) -> None:
        self._set_char(self._switch, 'On', self.isy_is_on(), notify=notify)


class ISYOutletAccessory(ISYSwitchAccessory):
    """HomeKit Outlet. Same on/off control as a switch; Apple Home shows a plug."""

    service_name = 'Outlet'


class ISYValveAccessory(ISYAccessoryBase):
    """HomeKit Valve. Moen Flo ST is 0 closed / 1 open, written with SET_VALVE."""

    def __init__(self, driver: Any, device, on_isy_change=None) -> None:
        super().__init__(driver, device, on_isy_change=on_isy_change)
        serv = self.add_preload_service('Valve')
        serv.setter_callback = self._set_chars
        self._valve = serv
        self._set_char(serv, 'ValveType', 0, notify=False)
        self.sync_from_isy(notify=False)

    def _set_chars(self, char_values: dict) -> None:
        if 'Active' not in char_values:
            return
        self._set_open(bool(int(char_values['Active'])))

    def _set_open(self, open_valve: bool) -> None:
        control = self._control()
        send = getattr(control, 'send_cmd', None)
        if not callable(send):
            LOGGER.warning('No send_cmd for %s; skipped SET_VALVE', self.exported.address)
            return
        try:
            send('SET_VALVE', 1 if open_valve else 0)
        except Exception:
            LOGGER.warning(
                'IoX SET_VALVE failed for %s',
                self.exported.address,
                exc_info=True,
            )

    def sync_from_isy(self, notify: bool = True) -> None:
        active = 1 if self.isy_is_on() else 0
        self._set_char(self._valve, 'Active', active, notify=notify)
        self._set_char(self._valve, 'InUse', active, notify=notify)
