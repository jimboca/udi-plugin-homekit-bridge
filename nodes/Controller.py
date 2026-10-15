#!/usr/bin/env python3
"""Plugins controller for the IoX → HomeKit bridge."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import markdown2
from udi_interface import Custom, ISY, LOGGER, LOG_HANDLER, Node, get_network_interface

from const import (
    BRIDGE_RESTART_KEYS,
    DEFAULT_ADVERTISE_TIMEOUT_MINUTES,
    DEFAULT_BRIDGE_PARAMS,
    ERR_BRIDGE_START,
    ERR_BRIDGE_STOP,
    ERR_ISY_CONNECT,
    ERR_ISY_UNAUTHORIZED,
    ERR_OK,
    ERR_SCAN,
    ERR_TOO_MANY_DEVICES,
    EXPORT_MODES,
    MAPPING_MODES,
    TYPED_EXPORT_DEVICES_KEY,
)
from homekit_bridge import BridgeStateStore, IsyHomeKitBridge, scan_export_devices
from homekit_bridge.bridge_server import resolve_advertise_ip
from homekit_bridge.config_doc import build_custom_params_doc_html, exported_devices_signature
from homekit_bridge.mdns_diag import (
    MDNS_DEBOUNCE_SEC,
    MDNS_WATCHDOG_SEC,
    format_debug_report,
    normalize_services,
    summarize,
)
from homekit_bridge.pyisy_eisy import apply_pyisy_eisy_patches
from homekit_bridge.setup_notice import (
    build_setup_details,
    format_setup_log_message,
    format_setup_notice_html,
)

_CONFIG_DIR = Path('config')
_BRIDGE_STATE_FILE = _CONFIG_DIR / 'bridge_state.json'
_ACCESSORY_STATE_FILE = _CONFIG_DIR / 'accessory.state'


class Controller(Node):
    """Single IoX node that runs the HomeKit bridge."""

    def __init__(self, plugin, primary, address, name):
        super().__init__(plugin, primary, address, name)
        self.hb = 0
        self.isy: Optional[ISY] = None
        self.pyisy = None
        self.bridge: Optional[IsyHomeKitBridge] = None
        self.state_store = BridgeStateStore(str(_BRIDGE_STATE_FILE))
        self.exported_devices = []
        self.handler_params_st = False
        self.handler_config_st = False
        self._config_snap: Dict[str, str] = {}
        self._advertise_until = 0.0
        self._mdns_lock = threading.Lock()
        self._mdns_inflight = False
        self._mdns_services: List[Any] = []
        self._mdns_generation = 0
        self._mdns_expect_name = ''
        self._mdns_expect_port = 0
        self._mdns_payload_keys: List[str] = []
        self._mdns_debounce: Optional[threading.Timer] = None
        self._mdns_watchdog: Optional[threading.Timer] = None
        self._config_doc_table_sig = None
        self._config_md_path = Path(__file__).resolve().parent.parent / 'CONFIG.md'
        self.Notices = Custom(plugin, 'notices')
        self.Params = Custom(plugin, 'customparams')
        self.TypedParams = Custom(plugin, 'customtypedparams')
        self.TypedData = Custom(plugin, 'customtypeddata')
        plugin.subscribe(plugin.START, self.handler_start, address)
        plugin.subscribe(plugin.POLL, self.handler_poll)
        plugin.subscribe(plugin.CUSTOMPARAMS, self.handler_custom_params)
        plugin.subscribe(plugin.CUSTOMTYPEDPARAMS, self.handler_typed_params)
        plugin.subscribe(plugin.CUSTOMTYPEDDATA, self.handler_typed_data)
        plugin.subscribe(plugin.LOGLEVEL, self.handler_log_level)
        plugin.subscribe(plugin.CONFIGDONE, self.handler_config_done)
        plugin.subscribe(plugin.STOP, self.handler_stop)
        plugin.subscribe(plugin.DISCOVER, self.handler_discover)
        plugin.subscribe(plugin.BONJOUR, self.handler_bonjour)
        self.commands = {
            'QUERY': self.query,
            'REFRESH': self.cmd_refresh,
            'SHOW_SETUP': self.cmd_show_setup,
            'SET_ADVERTISE': self.cmd_set_advertise,
        }
        self.init_typed_params()
        self.Notices.clear()
        plugin.ready()
        plugin.addNode(self, conn_status='ST')

    def init_typed_params(self) -> None:
        self.TypedParams.load(
            [
                {
                    'name': TYPED_EXPORT_DEVICES_KEY,
                    'title': 'Exported devices',
                    'desc': 'Optional per-node include/exclude/rename overrides (hybrid/all modes).',
                    'isList': True,
                    'params': [
                        {
                            'name': 'node_address',
                            'title': 'Node address or name',
                            'isRequired': True,
                        },
                        {
                            'name': 'action',
                            'title': 'Action (include, exclude, rename)',
                            'isRequired': False,
                        },
                        {
                            'name': 'homekit_name',
                            'title': 'HomeKit display name override',
                            'isRequired': False,
                        },
                        {
                            'name': 'hap_type',
                            'title': 'Forced HAP type (light, switch, fan, thermostat, contact, motion, lock, blind, garage)',
                            'isRequired': False,
                        },
                    ],
                }
            ],
            True,
        )

    def handler_start(self) -> None:
        LOGGER.info('Started IoX HomeKit bridge %s', self.poly.serverdata.get('version'))
        self._update_config_doc(force=True)
        self.setDriver('ST', 0)
        self.setDriver('GV0', 0)
        self.setDriver('GV1', 0)
        self.setDriver('GV2', 0)
        self.set_err(ERR_OK)
        self.heartbeat(0)

    def handler_log_level(self, level) -> None:
        if level['level'] < 10:
            LOG_HANDLER.set_basic_config(True, logging.DEBUG)
        else:
            LOG_HANDLER.set_basic_config(True, logging.WARNING)

    def handler_custom_params(self, data) -> None:
        defaults = dict(DEFAULT_BRIDGE_PARAMS)
        if data is None:
            data = {}
        self.Params.load(data)
        # Seed one missing key then return — Custom.__setitem__ publishes and
        # PG3 echoes CUSTOMPARAMS; writing without return floods set/.
        for key, value in defaults.items():
            if key not in data:
                self.Params[key] = value
                return
        export_mode = str(self.Params.get('export_mode', defaults['export_mode'])).strip().lower()
        if export_mode not in EXPORT_MODES:
            self.Params['export_mode'] = defaults['export_mode']
            return
        mapping_mode = str(self.Params.get('mapping_mode', defaults['mapping_mode'])).strip().lower()
        if mapping_mode not in MAPPING_MODES:
            self.Params['mapping_mode'] = defaults['mapping_mode']
            return
        try:
            timeout = int(str(self.Params.get('advertise_timeout', defaults['advertise_timeout'])).strip())
            if timeout < 1:
                raise ValueError('timeout must be >= 1')
        except (TypeError, ValueError):
            self.Params['advertise_timeout'] = defaults['advertise_timeout']
            return
        self.handler_params_st = True
        # Apply export_mode / mapping / HAP settings without requiring a restart.
        if self.handler_config_st:
            self._maybe_restart_on_config_change()

    def handler_typed_params(self, params) -> None:
        # Schema is published once from __init__ via init_typed_params(save=True).
        # On echo, load without save — load(..., True) here loops forever.
        if params is not None and len(params) > 0:
            self.TypedParams.load(params)

    def handler_typed_data(self, data) -> None:
        if data is not None:
            self.TypedData.load(data)
        # hybrid/all typed include/exclude/rename — rescan when already running.
        if self.handler_config_st and self.handler_params_st:
            LOGGER.info('Typed export data changed; refreshing devices')
            self.refresh_bridge(force=True)

    def handler_config_done(self) -> None:
        self.poly.addLogLevel('DEBUG_MODULES', 9, 'Debug + Modules')
        self._config_snap = self._params_snapshot()
        self.state_store.load()
        # Scan devices; only start HAP when already paired or Advertise is on.
        if self.refresh_bridge(force=True):
            self.handler_config_st = True

    def handler_poll(self, polltype) -> None:
        if not self.handler_config_st:
            return
        if polltype == 'longPoll':
            self.heartbeat()
            self._maybe_restart_on_config_change()
            if self.pyisy is not None and not self.pyisy.connected:
                self.setDriver('GV1', 0)
                self.init_isy()
        elif polltype == 'shortPoll':
            self._check_advertise_timeout()
            if self._should_run_hap() and (self.bridge is None or not self.bridge.running):
                self.refresh_bridge(force=False)

    def handler_stop(self) -> None:
        self.stop_bridge()
        self.isy_stop()

    def handler_discover(self, _data=None) -> None:
        """Plugins UI Discover button → open the timed HomeKit Advertise window."""
        LOGGER.info('Discover requested — enabling HomeKit Advertise')
        self.set_advertise(1)

    def _update_config_doc(self, force: bool = False) -> None:
        """Publish CONFIG.md help plus a read-only exported-devices table."""
        if not self._config_md_path.is_file():
            return
        sig = exported_devices_signature(self.exported_devices)
        if not force and sig == self._config_doc_table_sig:
            return
        try:
            html_doc = build_custom_params_doc_html(
                self._config_md_path,
                self.exported_devices,
                markdown_path_fn=markdown2.markdown_path,
            )
            self.poly.setCustomParamsDoc(html_doc)
            self._config_doc_table_sig = sig
        except Exception:
            LOGGER.exception('Failed to update Configuration help document')

    def _params_snapshot(self) -> Dict[str, str]:
        snap = {}
        for key in DEFAULT_BRIDGE_PARAMS:
            snap[key] = str(self.Params.get(key, DEFAULT_BRIDGE_PARAMS[key]))
        return snap

    def _maybe_restart_on_config_change(self) -> None:
        current = self._params_snapshot()
        if any(current.get(k) != self._config_snap.get(k) for k in BRIDGE_RESTART_KEYS):
            changed = [k for k in BRIDGE_RESTART_KEYS if current.get(k) != self._config_snap.get(k)]
            LOGGER.info('Bridge config changed (%s); refreshing', ', '.join(changed))
            self._config_snap = current
            self.refresh_bridge(force=True)

    def _typed_export_rows(self) -> List[Dict[str, Any]]:
        try:
            rows = self.TypedData.get(TYPED_EXPORT_DEVICES_KEY)
        except Exception:
            return []
        return rows if isinstance(rows, list) else []

    def _bridge_params(self) -> Dict[str, Any]:
        advertise_ip = resolve_advertise_ip(self.Params.get('advertise_ip', ''))
        if not advertise_ip:
            try:
                advertise_ip = resolve_advertise_ip(get_network_interface('default'))
            except Exception:
                try:
                    advertise_ip = resolve_advertise_ip(self.poly.getNetworkInterface())
                except Exception:
                    advertise_ip = ''
        return {
            'bridge_name': str(self.Params.get('bridge_name', DEFAULT_BRIDGE_PARAMS['bridge_name'])),
            'hap_port': int(self.Params.get('hap_port', DEFAULT_BRIDGE_PARAMS['hap_port'])),
            'hap_pin': str(self.Params.get('hap_pin', '')),
            'advertise_ip': advertise_ip,
            'export_mode': str(self.Params.get('export_mode', DEFAULT_BRIDGE_PARAMS['export_mode'])),
            'mapping_mode': str(self.Params.get('mapping_mode', DEFAULT_BRIDGE_PARAMS['mapping_mode'])),
        }

    def _advertise_timeout_minutes(self) -> int:
        try:
            return max(1, int(str(self.Params.get('advertise_timeout', DEFAULT_ADVERTISE_TIMEOUT_MINUTES))))
        except (TypeError, ValueError):
            return DEFAULT_ADVERTISE_TIMEOUT_MINUTES

    def persist_is_paired(self) -> bool:
        """True if accessory.state already has Apple Home paired clients."""
        if self.bridge is not None and self.bridge.is_paired():
            return True
        path = _ACCESSORY_STATE_FILE
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            clients = data.get('paired_clients') or {}
            return bool(clients)
        except Exception:
            LOGGER.exception('Failed reading %s', path)
            return False

    def get_advertise(self) -> int:
        try:
            return int(self.getDriver('GV2') or 0)
        except Exception:
            return 0

    def _should_run_hap(self) -> bool:
        return self.get_advertise() == 1 or self.persist_is_paired()

    def _check_advertise_timeout(self) -> None:
        if self.get_advertise() != 1:
            return
        if self._advertise_until <= 0:
            return
        if time.time() < self._advertise_until:
            return
        LOGGER.info('Advertise window timed out')
        self.Notices['advertise'] = f'HomeKit Advertise timed out after {self._advertise_timeout_minutes()} minute(s).'
        self.set_advertise(0)

    def set_advertise(self, val: int) -> None:
        enabled = 1 if int(val) else 0
        if enabled:
            minutes = self._advertise_timeout_minutes()
            self._advertise_until = time.time() + (minutes * 60)
            self.setDriver('GV2', 1)
            LOGGER.info('HomeKit Advertise enabled for %s minute(s)', minutes)
            self.Notices['advertise'] = (
                f'HomeKit Advertise On for {minutes} minute(s). '
                'Pairing details are in the HomeKit pairing notice below. '
                'Apple Home finds the bridge by multicast on UDP port 5353, '
                'which requires this node server to run as polyglot.'
            )
            self.refresh_bridge(force=True)
            if self.bridge is not None and self.bridge.running:
                self.cmd_show_setup()
        else:
            self._advertise_until = 0.0
            self.setDriver('GV2', 0)
            LOGGER.info('HomeKit Advertise disabled')
            try:
                self.Notices.delete('setup')
            except Exception:
                pass
            # Keep HAP running for an already-paired Apple Home; stop when unpaired.
            if not self.persist_is_paired():
                self.stop_bridge()
            elif self.bridge is not None and self.bridge.running:
                self.setDriver('ST', 2 if self.bridge.is_paired() else 1)

    def set_err(self, code: int) -> None:
        self.setDriver('ERR', int(code), uom=25)

    def init_isy(self, restart: bool = False) -> bool:
        """Connect via PG3 ``udi_interface.ISY`` — same as udi-poly-ELK ``init_isy``.

        ELK only enables ``pyisy.auto_update`` when it has live ELK↔IoX light sync.
        We do the same: REST/node load here; event stream only when HAP is running
        (see ``_enable_isy_events``).
        """
        try:
            if restart:
                self.isy_stop()
            if self.isy is None:
                self.pyisy = None
                self.isy = ISY(self.poly)
                deadline = time.time() + 30
                while not (self.isy.valid or self.isy.unauthorized) and time.time() < deadline:
                    LOGGER.info(
                        'Waiting for IoX credentials from Plugins... valid=%s unauthorized=%s',
                        self.isy.valid,
                        self.isy.unauthorized,
                    )
                    time.sleep(1)
            if self.isy is None:
                self.set_err(ERR_ISY_CONNECT)
                self.setDriver('GV1', 0)
                LOGGER.error('Failed to create udi_interface.ISY helper')
                return False
            if self.isy.unauthorized:
                self.set_err(ERR_ISY_UNAUTHORIZED)
                self.setDriver('GV1', 0)
                self.Notices['isy_access'] = 'Enable Allow Unrestricted IoX Access by Node Server, Save, then Restart.'
                return False
            if not self.isy.valid:
                self.set_err(ERR_ISY_CONNECT)
                self.setDriver('GV1', 0)
                LOGGER.error('IoX info not available from Plugins (timed out)')
                return False
            if self.pyisy is None:
                self.pyisy = self.isy.pyisy()
            if self.pyisy is None or not self.pyisy.connected:
                self.set_err(ERR_ISY_CONNECT)
                self.setDriver('GV1', 0)
                LOGGER.error('PyISY failed to connect using Plugins IoX credentials')
                return False
            # Like ELK: do not enable auto_update here — REST is enough to scan nodes.
            self.setDriver('GV1', 1)
            self.set_err(ERR_OK)
            try:
                self.Notices.delete('isy_access')
            except Exception:
                pass
            return True
        except Exception:
            LOGGER.exception('init_isy failed')
            self.set_err(ERR_ISY_CONNECT)
            self.setDriver('GV1', 0)
            return False

    def _enable_isy_events(self) -> None:
        """Start PyISY event stream only when HomeKit accessories need live status.

        eISY JWTs break stock PyISY SOAP auth (``base64.encodebytes`` newlines) —
        apply the small patch first. ELK never hits this unless light sync is on.
        """
        if self.pyisy is None or self.pyisy.auto_update:
            return
        apply_pyisy_eisy_patches()
        try:
            self.pyisy.auto_update = True
            LOGGER.info('PyISY auto_update enabled for HomeKit status sync')
        except Exception:
            LOGGER.exception('Failed to enable PyISY auto_update; HomeKit will poll on refresh')

    def isy_stop(self) -> None:
        """Tear down PyISY (ELK-style)."""
        if self.pyisy is not None:
            try:
                self.pyisy.auto_update = False
            except Exception:
                LOGGER.debug('PyISY auto_update stop failed', exc_info=True)
            self.pyisy = None
        self.isy = None
        self.setDriver('GV1', 0)

    def _request_hap_mdns_browse(self) -> None:
        """Ask PG3 to browse ``_hap._tcp``. One request at a time; reply is ~10s."""
        bridge = self.bridge
        if bridge is None or not bridge.running:
            return
        name = str(bridge.bridge_name)
        port = int(bridge.hap_port)
        with self._mdns_lock:
            if self._mdns_inflight:
                LOGGER.debug('HAP mDNS browse already in progress')
                return
            self._mdns_inflight = True
            self._mdns_services = []
            self._mdns_payload_keys = []
            self._mdns_generation += 1
            generation = self._mdns_generation
            self._mdns_expect_name = name
            self._mdns_expect_port = port
            self._arm_mdns_timer_locked(
                'watchdog', MDNS_WATCHDOG_SEC, self._mdns_watchdog_fire, generation,
            )
            self.Notices['mdns'] = (
                '<p>Checking whether Apple Home can see this bridge on the local network. '
                'This takes about 10 seconds.</p>'
            )
        LOGGER.info(
            'Browsing _hap._tcp for %s:%s (process uid %s)',
            name,
            port,
            _process_uid(),
        )
        try:
            self.poly.bonjour('hap', None, 'tcp')
        except Exception:
            LOGGER.exception('PG3 bonjour browse failed')
            self._abort_mdns_browse(generation)

    def handler_bonjour(self, payload) -> None:
        services = normalize_services(payload)
        keys = list(payload.keys()) if isinstance(payload, dict) else []
        LOGGER.debug('BONJOUR reply keys=%s parsed=%d', keys or type(payload).__name__, len(services))
        with self._mdns_lock:
            if not self._mdns_inflight:
                LOGGER.info(
                    'BONJOUR arrived with no browse in progress (%d services)',
                    len(services),
                )
                return
            generation = self._mdns_generation
            self._mdns_services.extend(services)
            for key in keys:
                if key not in self._mdns_payload_keys:
                    self._mdns_payload_keys.append(key)
            self._arm_mdns_timer_locked(
                'debounce', MDNS_DEBOUNCE_SEC, self._mdns_debounce_fire, generation,
            )

    def _mdns_debounce_fire(self, generation: int) -> None:
        self._complete_mdns_browse(generation)

    def _mdns_watchdog_fire(self, generation: int) -> None:
        self._complete_mdns_browse(generation)

    def _complete_mdns_browse(self, generation: int) -> None:
        with self._mdns_lock:
            if generation != self._mdns_generation or not self._mdns_inflight:
                return
            services = list(self._mdns_services)
            name = self._mdns_expect_name
            port = self._mdns_expect_port
            payload_keys = list(self._mdns_payload_keys)
            self._mdns_inflight = False
            self._cancel_mdns_timers_locked()
        result = summarize(services, name, port)
        LOGGER.info(
            '%s',
            format_debug_report(services, name, port, uid=_process_uid(), payload_keys=payload_keys),
        )
        with self._mdns_lock:
            if generation != self._mdns_generation:
                return
            self.Notices['mdns'] = result.notice_html
        LOGGER.info(result.log)

    def _abort_mdns_browse(self, generation: int) -> None:
        with self._mdns_lock:
            if generation != self._mdns_generation:
                return
            self._mdns_inflight = False
            self._mdns_services = []
            self._mdns_payload_keys = []
            self._cancel_mdns_timers_locked()
            self.Notices['mdns'] = (
                '<p>Could not ask Plugins to browse for HomeKit advertisements. '
                'Check the node server log.</p>'
            )

    def _cancel_mdns_browse(self) -> None:
        with self._mdns_lock:
            self._mdns_generation += 1
            self._mdns_inflight = False
            self._mdns_services = []
            self._mdns_payload_keys = []
            self._cancel_mdns_timers_locked()
            try:
                self.Notices.delete('mdns')
            except Exception:
                LOGGER.debug('Clearing mDNS notice failed', exc_info=True)

    def _arm_mdns_timer_locked(self, which: str, seconds: float, fn, generation: int) -> None:
        current = self._mdns_debounce if which == 'debounce' else self._mdns_watchdog
        if current is not None:
            current.cancel()
        timer = threading.Timer(seconds, fn, args=(generation,))
        timer.daemon = True
        if which == 'debounce':
            self._mdns_debounce = timer
        else:
            self._mdns_watchdog = timer
        timer.start()

    def _cancel_mdns_timers_locked(self) -> None:
        for timer in (self._mdns_debounce, self._mdns_watchdog):
            if timer is not None:
                timer.cancel()
        self._mdns_debounce = None
        self._mdns_watchdog = None

    def stop_bridge(self) -> None:
        self._cancel_mdns_browse()
        if self.bridge is not None:
            try:
                self.bridge.stop()
            except Exception:
                LOGGER.exception('Bridge stop failed')
                self.set_err(ERR_BRIDGE_STOP)
            self.bridge = None
        self.setDriver('ST', 0)

    def refresh_bridge(self, force: bool = False) -> bool:
        if not self.handler_params_st and not force:
            return False
        if not self.init_isy():
            return False
        params = self._bridge_params()
        try:
            self.exported_devices = scan_export_devices(
                self.pyisy,
                params['export_mode'],
                self._typed_export_rows(),
                params['mapping_mode'],
                self.state_store,
            )
        except ValueError as exc:
            if 'too many devices' in str(exc):
                self.set_err(ERR_TOO_MANY_DEVICES)
            else:
                self.set_err(ERR_SCAN)
            LOGGER.error('Device scan failed: %s', exc)
            return False
        except Exception:
            self.set_err(ERR_SCAN)
            LOGGER.exception('Device scan failed')
            return False

        self.setDriver('GV0', len(self.exported_devices))
        self._update_config_doc()

        if not self._should_run_hap():
            self.stop_bridge()
            LOGGER.info(
                'HomeKit HAP idle (%d devices ready). Set Advertise On to pair with Apple Home.',
                len(self.exported_devices),
            )
            self.set_err(ERR_OK)
            return True

        self.stop_bridge()
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self._enable_isy_events()
            self.bridge = IsyHomeKitBridge(
                bridge_name=params['bridge_name'],
                hap_port=params['hap_port'],
                hap_pin=params['hap_pin'],
                advertise_ip=params['advertise_ip'],
                persist_file=str(_ACCESSORY_STATE_FILE),
                on_paired_change=self._update_paired_status,
            )
            self.bridge.start(self.exported_devices)
            self.setDriver('ST', 2 if self.bridge.is_paired() else 1)
            self.set_err(ERR_OK)
            self._request_hap_mdns_browse()
            return True
        except Exception as exc:
            self.set_err(ERR_BRIDGE_START)
            self.bridge = None
            self.Notices['advertise'] = (
                f'HomeKit bridge failed to start ({exc}). '
                'Check advertise_ip is a dotted IPv4 (or leave empty), then set Advertise On again.'
            )
            LOGGER.exception('Failed to start HomeKit bridge')
            return False

    def _update_paired_status(self, _paired: bool) -> None:
        if self.bridge is None:
            return
        self.setDriver('ST', 2 if self.bridge.is_paired() else 1)

    def query(self, _cmd=None) -> None:
        self.reportDrivers()

    def cmd_refresh(self, _cmd=None) -> None:
        self.refresh_bridge(force=True)

    def cmd_show_setup(self, _cmd=None) -> None:
        if self.bridge is None or self.bridge.driver is None:
            if self.get_advertise() != 1:
                self.Notices['setup'] = 'HomeKit is not advertising. Set Advertise On, then try Show HomeKit Setup again.'
                return
            self.Notices['setup'] = 'Bridge is not running yet. Wait a moment or run Refresh Devices.'
            return
        # Also print ASCII QR / PIN to the node server log (HAP-python).
        try:
            self.bridge.setup_message()
        except Exception:
            LOGGER.exception('HAP setup_message failed')

        details = build_setup_details(self.bridge)
        if details is None:
            self.Notices['setup'] = 'Unable to read HomeKit setup details from the running bridge.'
        else:
            LOGGER.info(format_setup_log_message(details))
            self.Notices['setup'] = format_setup_notice_html(details)
        self._request_hap_mdns_browse()

    def cmd_set_advertise(self, command) -> None:
        self.set_advertise(int(command.get('value')))

    def heartbeat(self, inc: int = 1) -> None:
        self.hb += inc
        if self.hb % 2 == 0:
            self.reportCmd('DON')
        else:
            self.reportCmd('DOF')

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 25},
        {'driver': 'GV0', 'value': 0, 'uom': 56},
        {'driver': 'GV1', 'value': 0, 'uom': 2},
        {'driver': 'GV2', 'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
    ]
    id = 'controller'


def _process_uid() -> str:
    for name in ('geteuid', 'getuid'):
        fn = getattr(os, name, None)
        if fn is None:
            continue
        try:
            return str(fn())
        except OSError:
            continue
    return 'unknown'
