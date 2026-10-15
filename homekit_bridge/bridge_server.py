"""HAP-python bridge server exposing IoX devices to Apple Home."""

from __future__ import annotations

import ipaddress
import logging
import random
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from homekit_bridge.accessories import build_accessory
from homekit_bridge.isy_scanner import ExportedDevice

LOGGER = logging.getLogger(__name__)

_HAP_START_TIMEOUT_SEC = 8.0


def _normalize_pin(pin: str) -> bytes:
    digits = re.sub(r'\D', '', pin or '')
    if len(digits) != 8:
        digits = ''.join(str(random.randint(0, 9)) for _ in range(8))
    return f'{digits[0:3]}-{digits[3:5]}-{digits[5:8]}'.encode('ascii')


def resolve_advertise_ip(value: Union[str, dict, None]) -> str:
    """Return a dotted IPv4 string, or '' if missing/invalid.

    `udi_interface.get_network_interface('default')` returns a dict with `addr`,
    not a string — passing that dict to HAP-python makes create_server fail with
    ``gaierror: Name does not resolve`` and the bridge never advertises.
    """
    if isinstance(value, dict):
        value = value.get('addr')
    ip = str(value or '').strip()
    if not ip or ip.lower() in ('false', 'none', '0.0.0.0'):
        return ''
    try:
        return str(ipaddress.IPv4Address(ip))
    except (ipaddress.AddressValueError, ValueError):
        LOGGER.warning('Ignoring invalid advertise_ip %r (need dotted IPv4)', ip)
        return ''


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
                LOGGER.exception('Failed syncing %s from IoX', address)

        self._driver.loop.call_soon_threadsafe(_sync)

    def start(self, devices: List[ExportedDevice]) -> None:
        with self._lock:
            if self._running:
                self.stop()
            bind_ip = resolve_advertise_ip(self.advertise_ip)
            self.advertise_ip = bind_ip
            pincode = _normalize_pin(self.hap_pin)
            driver_kwargs: Dict[str, Any] = {
                'port': int(self.hap_port),
                'persist_file': self.persist_file,
                'pincode': pincode,
            }
            # Bind + advertise on a real IPv4 only. Leaving address unset lets
            # HAP-python pick via util.get_local_address().
            # mDNS uses stock multicast AsyncZeroconf (UDP 5353). On this eISY
            # mDNSResponderPosix runs as polyglot: Zeroconf() as polyglot
            # succeeds, and as eisyui it raises OSError 48. The node server
            # must run as polyglot. Do not force unicast.
            if bind_ip:
                driver_kwargs['address'] = bind_ip
                driver_kwargs['listen_address'] = bind_ip
                driver_kwargs['advertised_address'] = bind_ip
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
            if not self._wait_until_ready(_HAP_START_TIMEOUT_SEC):
                err = (
                    f'HAP failed to listen/advertise on {bind_ip or "(auto)"}:{self.hap_port} '
                    f'within {_HAP_START_TIMEOUT_SEC:.0f}s '
                    f'(UDP 5353 — run NS as polyglot to share mDNS with the system responder)'
                )
                LOGGER.error(err)
                self.stop()
                raise RuntimeError(err)
            LOGGER.info(
                'HomeKit bridge listening on %s:%s (%d accessories, mDNS registered)',
                bind_ip or getattr(self._driver.state, 'address', 'auto'),
                self.hap_port,
                len(devices),
            )
            if self.on_paired_change:
                self.on_paired_change(self.is_paired())

    def _wait_until_ready(self, timeout: float) -> bool:
        """True once HAP TCP is bound and mDNS service info is registered."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            driver = self._driver
            thread = self._thread
            if thread is not None and not thread.is_alive() and not self._running:
                return False
            server = getattr(getattr(driver, 'http_server', None), 'server', None)
            mdns = getattr(driver, 'mdns_service_info', None)
            if server is not None and mdns is not None:
                return True
            time.sleep(0.05)
        return False

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
