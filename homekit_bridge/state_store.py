"""Persist stable HAP accessory IDs and bridge metadata."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)

STATE_VERSION = 1


class BridgeStateStore:
    """Maps IoX node addresses to stable HomeKit accessory IDs (aid)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._data: Dict[str, Any] = {'version': STATE_VERSION, 'devices': [], 'next_aid': 2}

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning('Could not load bridge state %s: %s', self.path, exc)
            return
        if isinstance(data, dict):
            self._data = data
            if 'next_aid' not in self._data:
                self._data['next_aid'] = 2

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = f'{self.path}.tmp'
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def _find(self, address: str) -> Optional[Dict[str, Any]]:
        for item in self._data.get('devices', []):
            if item.get('address') == address:
                return item
        return None

    def get_aid(self, address: str) -> Optional[int]:
        item = self._find(address)
        if item is None:
            return None
        aid = item.get('aid')
        return int(aid) if aid is not None else None

    def assign_aid(self, address: str, name: str, hap_type: str) -> int:
        existing = self._find(address)
        if existing is not None and existing.get('aid') is not None:
            existing['name'] = name
            existing['hap_type'] = hap_type
            return int(existing['aid'])

        aid = int(self._data.get('next_aid', 2))
        while aid == 7:
            aid += 1
        used = {int(d['aid']) for d in self._data.get('devices', []) if d.get('aid') is not None}
        while aid in used:
            aid += 1

        entry = {'address': address, 'name': name, 'hap_type': hap_type, 'aid': aid}
        devices: List[Dict[str, Any]] = self._data.setdefault('devices', [])
        devices.append(entry)
        self._data['next_aid'] = aid + 1
        return aid

    def prune_missing(self, active_addresses: List[str]) -> None:
        active = set(active_addresses)
        self._data['devices'] = [
            d for d in self._data.get('devices', []) if d.get('address') in active
        ]
