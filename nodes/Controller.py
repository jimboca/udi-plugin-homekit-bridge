#!/usr/bin/env python3
"""PG3 controller for the ISY → HomeKit bridge."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import markdown2
from udi_interface import Custom, ISY, LOGGER, LOG_HANDLER, Node, get_network_interface

from const import (
    BRIDGE_RESTART_KEYS,
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

_CONFIG_DIR = Path('config')
_BRIDGE_STATE_FILE = _CONFIG_DIR / 'bridge_state.json'
_ACCESSORY_STATE_FILE = _CONFIG_DIR / 'accessory.state'


class Controller(Node):
    """Single IoX node that runs the HomeKit bridge."""

    def __init__(self, poly, primary, address, name):
        super().__init__(poly, primary, address, name)
        self.hb = 0
        self.isy: Optional[ISY] = None
        self.pyisy = None
        self.bridge: Optional[IsyHomeKitBridge] = None
        self.state_store = BridgeStateStore(str(_BRIDGE_STATE_FILE))
        self.exported_devices = []
        self.handler_params_st = False
        self.handler_config_st = False
        self._config_snap: Dict[str, str] = {}
        self.Notices = Custom(poly, 'notices')
        self.Params = Custom(poly, 'customparams')
        self.TypedParams = Custom(poly, 'customtypedparams')
        self.TypedData = Custom(poly, 'customtypeddata')
        poly.subscribe(poly.START, self.handler_start, address)
        poly.subscribe(poly.POLL, self.handler_poll)
        poly.subscribe(poly.CUSTOMPARAMS, self.handler_custom_params)
        poly.subscribe(poly.CUSTOMTYPEDPARAMS, self.handler_typed_params)
        poly.subscribe(poly.CUSTOMTYPEDDATA, self.handler_typed_data)
        poly.subscribe(poly.LOGLEVEL, self.handler_log_level)
        poly.subscribe(poly.CONFIGDONE, self.handler_config_done)
        poly.subscribe(poly.STOP, self.handler_stop)
        self.commands = {
            'REFRESH': self.cmd_refresh,
            'SHOW_SETUP': self.cmd_show_setup,
        }
        self.init_typed_params()
        self.Notices.clear()
        poly.ready()
        poly.addNode(self, conn_status='ST')

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
                            'title': 'Forced HAP type (light, switch, fan, thermostat, contact, motion, lock, blind)',
                            'isRequired': False,
                        },
                    ],
                }
            ],
            True,
        )

    def handler_start(self) -> None:
        LOGGER.info('Started ISY HomeKit bridge %s', self.poly.serverdata.get('version'))
        config_help = Path(__file__).resolve().parent.parent / 'CONFIG.md'
        if config_help.is_file():
            try:
                self.poly.setCustomParamsDoc(
                    markdown2.markdown_path(
                        str(config_help),
                        extras=['tables', 'fenced-code-blocks'],
                    )
                )
            except Exception:
                LOGGER.exception('Failed to load CONFIG.md')
        self.setDriver('ST', 0)
        self.setDriver('GV0', 0)
        self.setDriver('GV1', 0)
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
            for key, value in defaults.items():
                self.Params[key] = value
            return
        self.Params.load(data)
        for key, value in defaults.items():
            if key not in data or data[key] in (None, ''):
                self.Params[key] = value
        export_mode = str(self.Params.get('export_mode', defaults['export_mode'])).strip().lower()
        if export_mode not in EXPORT_MODES:
            self.Params['export_mode'] = defaults['export_mode']
        mapping_mode = str(self.Params.get('mapping_mode', defaults['mapping_mode'])).strip().lower()
        if mapping_mode not in MAPPING_MODES:
            self.Params['mapping_mode'] = defaults['mapping_mode']
        self.handler_params_st = True

    def handler_typed_params(self, _data) -> None:
        self.init_typed_params()

    def handler_typed_data(self, data) -> None:
        if data is not None:
            self.TypedData.load(data)

    def handler_config_done(self) -> None:
        self.poly.addLogLevel('DEBUG_MODULES', 9, 'Debug + Modules')
        self._config_snap = self._params_snapshot()
        self.state_store.load()
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
            if self.bridge is None or not self.bridge.running:
                self.refresh_bridge(force=False)

    def handler_stop(self) -> None:
        self.stop_bridge()

    def _params_snapshot(self) -> Dict[str, str]:
        snap = {}
        for key in DEFAULT_BRIDGE_PARAMS:
            snap[key] = str(self.Params.get(key, DEFAULT_BRIDGE_PARAMS[key]))
        return snap

    def _maybe_restart_on_config_change(self) -> None:
        current = self._params_snapshot()
        if any(current.get(k) != self._config_snap.get(k) for k in BRIDGE_RESTART_KEYS):
            LOGGER.info('Bridge config changed; restarting')
            self._config_snap = current
            self.refresh_bridge(force=True)

    def _typed_export_rows(self) -> List[Dict[str, Any]]:
        try:
            rows = self.TypedData.get(TYPED_EXPORT_DEVICES_KEY)
        except Exception:
            return []
        return rows if isinstance(rows, list) else []

    def _bridge_params(self) -> Dict[str, Any]:
        advertise_ip = str(self.Params.get('advertise_ip', '')).strip()
        if not advertise_ip:
            try:
                advertise_ip = get_network_interface('default') or ''
            except Exception:
                advertise_ip = self.poly.getNetworkInterface() or ''
        return {
            'bridge_name': str(self.Params.get('bridge_name', DEFAULT_BRIDGE_PARAMS['bridge_name'])),
            'hap_port': int(self.Params.get('hap_port', DEFAULT_BRIDGE_PARAMS['hap_port'])),
            'hap_pin': str(self.Params.get('hap_pin', '')),
            'advertise_ip': advertise_ip,
            'export_mode': str(self.Params.get('export_mode', DEFAULT_BRIDGE_PARAMS['export_mode'])),
            'mapping_mode': str(self.Params.get('mapping_mode', DEFAULT_BRIDGE_PARAMS['mapping_mode'])),
        }

    def set_err(self, code: int) -> None:
        self.setDriver('ERR', int(code), uom=25)

    def init_isy(self) -> bool:
        if self.isy is None:
            self.isy = ISY(self.poly)
            deadline = time.time() + 30
            while not (self.isy.valid or self.isy.unauthorized) and time.time() < deadline:
                time.sleep(0.5)
        if self.isy.unauthorized:
            self.set_err(ERR_ISY_UNAUTHORIZED)
            self.setDriver('GV1', 0)
            self.Notices.send(
                'isy_access',
                'Enable Allow Unrestricted ISY Access by Node Server, Save, then Restart.',
            )
            return False
        if not self.isy.valid:
            self.set_err(ERR_ISY_CONNECT)
            self.setDriver('GV1', 0)
            return False
        if self.pyisy is None:
            self.pyisy = self.isy.pyisy()
        if self.pyisy is None or not self.pyisy.connected:
            self.set_err(ERR_ISY_CONNECT)
            self.setDriver('GV1', 0)
            return False
        self.pyisy.auto_update = True
        self.setDriver('GV1', 1)
        self.set_err(ERR_OK)
        return True

    def stop_bridge(self) -> None:
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
        self.stop_bridge()
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
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
            return True
        except Exception:
            self.set_err(ERR_BRIDGE_START)
            LOGGER.exception('Failed to start HomeKit bridge')
            return False

    def _update_paired_status(self, _paired: bool) -> None:
        if self.bridge is None:
            return
        self.setDriver('ST', 2 if self.bridge.is_paired() else 1)

    def cmd_refresh(self, _cmd=None) -> None:
        self.refresh_bridge(force=True)

    def cmd_show_setup(self, _cmd=None) -> None:
        if self.bridge is None or self.bridge.driver is None:
            self.Notices.send('setup', 'Bridge is not running. Run REFRESH first.')
            return
        self.bridge.setup_message()
        pin = self.bridge.driver.state.pincode.decode()
        self.Notices.send('setup', f'HomeKit setup code: {pin} (also printed in the node server log)')

    def heartbeat(self, inc: int = 1) -> None:
        self.hb += inc
        if self.hb % 2 == 0:
            self.reportCmd('DON')
        else:
            self.reportCmd('DOF')
