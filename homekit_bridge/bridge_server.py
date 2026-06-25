"""HAP-python bridge server exposing ISY devices to Apple Home."""

from __future__ import annotations

import logging
import random
import re
import threading
from typing import Any, Callable, Dict, List, Optional

from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from homekit_bridge.accessories import build_accessory
from homekit_bridge.isy_scanner import ExportedDevice

LOGGER = logging.getLogger(__name__)


def _normalize_pin(pin: str) -> bytes:
    digits = re.sub(r'\D', '', pin or '')
    if len(digits) != 8:
        digits = ''.join(str(random.randint(0, 9)) for _ in range(8))
    return f'{digits[0:3]}-{digits[3:5]}-{digits[5:8]}'.encode('ascii')


class IsyHomeKitBridge:
    """Runs a HAP bridge in a background thread."""

    def __init__(
        self,
        *,
        bridge_name: str,
        hap_port: int,
        hap_pin: str,
        advertise_ip: str,
        persist_file: str,
        on_paired_change: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self.bridge_name = bridge_name
        self.hap_port = hap_port
        self.hap_pin = hap_pin
        self.advertise_ip = advertise_ip
        self.persist_file = persist_file
        self.on_paired_change = on_paired_change
        self._driver: Optional[AccessoryDriver] = None
        self._thread: Optional[threading.Thread] = None
        self._accessories: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def driver(self) -> Optional[AccessoryDriver]:
        return self._driver

    def setup_message(self) -> None:
        bridge = self._driver.accessory if self._driver else None
        if bridge is not None and hasattr(bridge, 'setup_message'):
            bridge.setup_message()

    def is_paired(self) -> bool:
        if self._driver is None:
            return False
        clients = getattr(self._driver.state, 'paired_clients', {})
        return bool(clients)

    def _on_isy_change(self, address: str) -> None:
        accessory = self._accessories.get(address)
        if accessory is None or self._driver is None:
            return

        def _sync() -> None:
            try:
                accessory.sync_from_isy(notify=True)
            except Exception:
                LOGGER.exception('Failed syncing %s from ISY', address)

        self._driver.loop.call_soon_threadsafe(_sync)

    def start(self, devices: List[ExportedDevice]) -> None:
        with self._lock:
            if self._running:
                self.stop()
            pincode = _normalize_pin(self.hap_pin)
            driver_kwargs: Dict[str, Any] = {
                'port': int(self.hap_port),
                'persist_file': self.persist_file,
                'pincode': pincode,
            }
            if self.advertise_ip:
                driver_kwargs['address'] = self.advertise_ip
                driver_kwargs['advertised_address'] = self.advertise_ip
            self._driver = AccessoryDriver(**driver_kwargs)
            bridge = Bridge(self._driver, self.bridge_name)
            self._accessories = {}
            for device in devices:
                acc = build_accessory(self._driver, device, on_isy_change=self._on_isy_change)
                bridge.add_accessory(acc)
                self._accessories[device.address] = acc
            self._driver.add_accessory(accessory=bridge)

            def _run() -> None:
                try:
                    self._running = True
                    self._driver.start()
                except Exception:
                    LOGGER.exception('HAP bridge thread exited with error')
                finally:
                    self._running = False

            self._thread = threading.Thread(target=_run, name='homekit-bridge-hap', daemon=True)
            self._thread.start()
            LOGGER.info(
                'HomeKit bridge started on port %s (%d accessories)',
                self.hap_port,
                len(devices),
            )
            if self.on_paired_change:
                self.on_paired_change(self.is_paired())

    def stop(self) -> None:
        with self._lock:
            driver = self._driver
            thread = self._thread
            self._driver = None
            self._thread = None
            self._accessories = {}
            if driver is not None:
                try:
                    driver.stop()
                except Exception:
                    LOGGER.exception('Error stopping HAP driver')
            if thread is not None and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=10)
            self._running = False

    def sync_all(self) -> None:
        for accessory in self._accessories.values():
            try:
                accessory.sync_from_isy(notify=True)
            except Exception:
                LOGGER.exception('sync_all failed for %s', getattr(accessory.exported, 'address', '?'))
