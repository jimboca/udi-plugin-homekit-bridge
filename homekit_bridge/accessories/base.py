"""Base HomeKit accessory wired to an ISY exported device."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_OTHER
from pyisy import constants as pyisy_constants

from homekit_bridge.brightness import hap_to_isy_brightness, isy_to_hap_brightness

if TYPE_CHECKING:
    from homekit_bridge.isy_scanner import ExportedDevice

LOGGER = logging.getLogger(__name__)

CATEGORY_BY_HAP_TYPE = {
    'light': 5,
    'switch': 8,
    'fan': 7,
    'thermostat': 9,
    'contact': 10,
    'motion': 10,
    'lock': 6,
    'blind': 14,
    'temp_sensor': 10,
    'humidity_sensor': 10,
}


class ISYAccessoryBase(Accessory):
    """Common ISY ↔ HAP sync for exported devices."""

    def __init__(
        self,
        driver: Any,
        device: 'ExportedDevice',
        on_isy_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.exported = device
        self.on_isy_change = on_isy_change
        self.category = CATEGORY_BY_HAP_TYPE.get(device.hap_type, CATEGORY_OTHER)
        super().__init__(driver, device.display_name, aid=device.aid)
        self.set_info_service(
            manufacturer='Universal Devices',
            model='ISY',
            serial_number=device.address,
        )
        self._status_handler = None
        self._subscribe_isy()

    def _subscribe_isy(self) -> None:
        node = self.exported.node
        try:
            self._status_handler = self._handle_isy_status
            node.status_events.subscribe(self._status_handler)
        except Exception as exc:
            LOGGER.warning('Could not subscribe to %s: %s', self.exported.address, exc)

    def _handle_isy_status(self, _event: Any) -> None:
        if self.on_isy_change:
            self.on_isy_change(self.exported.address)
        else:
            self.sync_from_isy(notify=True)

    def _isy_status(self) -> int:
        status = getattr(self.exported.node, 'status', 0)
        if status == pyisy_constants.ISY_VALUE_UNKNOWN:
            return 0
        return int(status)

    def _control(self) -> Any:
        return self.exported.control_node

    def _turn_on(self, level: Optional[int] = None) -> None:
        control = self._control()
        scene = self.exported.scene_node
        if scene is not False and self.exported.traits.set_scene:
            scene.turn_on()
            return
        if level is not None and self.exported.traits.dimmable:
            control.turn_on(level)
        else:
            control.turn_on()

    def _turn_off(self) -> None:
        control = self._control()
        scene = self.exported.scene_node
        if scene is not False and self.exported.traits.set_scene:
            scene.turn_off()
            return
        control.turn_off()

    def sync_from_isy(self, notify: bool = True) -> None:
        """Override in subclasses."""

    def apply_hap_on(self, value: bool) -> None:
        if value:
            self._turn_on()
        else:
            self._turn_off()

    def apply_hap_brightness(self, hap_value: int) -> None:
        isy_value = hap_to_isy_brightness(hap_value)
        if isy_value <= 0:
            self._turn_off()
        elif self.exported.traits.dimmable and not self.exported.traits.set_scene:
            self._turn_on(isy_value)
        else:
            self._turn_on()

    def isy_brightness_hap(self) -> int:
        return isy_to_hap_brightness(self._isy_status())

    def isy_is_on(self) -> bool:
        return self._isy_status() > 0
