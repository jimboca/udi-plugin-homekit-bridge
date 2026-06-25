"""Discover ISY nodes to export based on export_mode and typed overrides."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from const import (
    EXPORT_MODE_ALL,
    EXPORT_MODE_HYBRID,
    EXPORT_MODE_SPOKEN,
    MAPPING_MODE_COMMON,
    MAX_BRIDGE_ACCESSORIES,
)
from homekit_bridge.mapping import classify_node, node_traits
from homekit_bridge.state_store import BridgeStateStore

LOGGER = logging.getLogger(__name__)


@dataclass
class ExportedDevice:
    address: str
    display_name: str
    hap_type: str
    node: Any
    control_node: Any
    scene_node: Any
    traits: Any
    aid: int = 0
    spoken: Optional[str] = None
    override_action: Optional[str] = None


def _normalize_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {str(k): '' if v is None else str(v).strip() for k, v in row.items()}


def _typed_rows_by_address(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        row = _normalize_row(raw)
        address = row.get('node_address', '')
        if address:
            out[address.lower()] = row
    return out


def _find_node(pyisy: Any, key: str) -> Optional[Any]:
    if not key:
        return None
    try:
        node = pyisy.nodes.get_by_id(key)
        if node is not None:
            return node
    except Exception:
        pass
    key_l = key.lower()
    for _, child in pyisy.nodes:
        ctype = type(child).__name__
        if ctype == 'Folder':
            continue
        if child.address.lower() == key_l or child.name.lower() == key_l:
            return child
        if child.name.lower().startswith(key_l) or child.address.lower().startswith(key_l):
            return child
    return None


def _spoken_name(node: Any) -> Optional[str]:
    spoken = getattr(node, 'spoken', None)
    if spoken is None:
        return None
    spoken_s = str(spoken).strip()
    if not spoken_s:
        return None
    if spoken_s == '1':
        return node.name
    return spoken_s


def _resolve_scene_controller(pyisy: Any, node: Any) -> tuple[Any, Any]:
    scene_node = False
    if type(node).__name__ == 'Node':
        groups = node.get_groups(responder=False)
        if groups:
            scene_node = pyisy.nodes[groups[0]]
    elif getattr(node, 'protocol', None) is not None:
        scene_node = node
    control_node = scene_node if scene_node is not False else node
    return control_node, scene_node


def _build_device(
    node: Any,
    pyisy: Any,
    mapping_mode: str,
    typed_row: Optional[Dict[str, str]],
    state_store: BridgeStateStore,
    *,
    strict: bool = False,
) -> Optional[ExportedDevice]:
    forced = typed_row.get('hap_type') if typed_row else None
    hap_type = classify_node(
        node,
        mapping_mode=mapping_mode,
        forced_hap_type=forced or None,
        strict=strict,
    )
    if hap_type is None:
        return None

    control_node, scene_node = _resolve_scene_controller(pyisy, node)
    traits = node_traits(node)
    if scene_node is not False:
        traits.set_scene = True

    spoken = _spoken_name(node)
    if typed_row and typed_row.get('homekit_name'):
        display_name = typed_row['homekit_name']
    elif spoken:
        display_name = spoken
    else:
        display_name = node.name

    aid = state_store.assign_aid(node.address, display_name, hap_type)
    return ExportedDevice(
        address=node.address,
        display_name=display_name,
        hap_type=hap_type,
        node=node,
        control_node=control_node,
        scene_node=scene_node,
        traits=traits,
        aid=aid,
        spoken=spoken,
        override_action=(typed_row or {}).get('action') or None,
    )


def scan_export_devices(
    pyisy: Any,
    export_mode: str,
    typed_rows: Sequence[Dict[str, Any]],
    mapping_mode: str,
    state_store: BridgeStateStore,
) -> List[ExportedDevice]:
    typed_by_address = _typed_rows_by_address(typed_rows)
    devices: List[ExportedDevice] = []
    seen: set[str] = set()

    def add_node(node: Any, typed_row: Optional[Dict[str, str]] = None, *, strict: bool = False) -> None:
        if node is None or node.address in seen:
            return
        device = _build_device(node, pyisy, mapping_mode, typed_row, state_store, strict=strict)
        if device is None:
            return
        seen.add(node.address)
        devices.append(device)

    if export_mode in (EXPORT_MODE_SPOKEN, EXPORT_MODE_HYBRID):
        for _, child in pyisy.nodes:
            ctype = type(child).__name__
            if ctype not in ('Node', 'Group'):
                continue
            spoken = _spoken_name(child)
            if spoken is None and export_mode == EXPORT_MODE_SPOKEN:
                continue
            if spoken is None and export_mode == EXPORT_MODE_HYBRID:
                row = typed_by_address.get(child.address.lower()) or typed_by_address.get(child.name.lower())
                if not row or row.get('action') != 'include':
                    continue
            row = typed_by_address.get(child.address.lower()) or typed_by_address.get(child.name.lower())
            if row and row.get('action') == 'exclude':
                continue
            add_node(child, row)

    if export_mode == EXPORT_MODE_HYBRID:
        for key, row in typed_by_address.items():
            if row.get('action') != 'include':
                continue
            node = _find_node(pyisy, row.get('node_address') or key)
            add_node(node, row)

    if export_mode == EXPORT_MODE_ALL:
        for _, child in pyisy.nodes:
            ctype = type(child).__name__
            if ctype not in ('Node', 'Group'):
                continue
            row = typed_by_address.get(child.address.lower()) or typed_by_address.get(child.name.lower())
            if row and row.get('action') == 'exclude':
                continue
            hap_type = classify_node(
                child,
                mapping_mode=mapping_mode,
                forced_hap_type=(row or {}).get('hap_type') or None,
                strict=True,
            )
            if hap_type is None:
                continue
            add_node(child, row, strict=True)

    # Apply rename-only typed rows.
    for device in devices:
        row = typed_by_address.get(device.address.lower()) or typed_by_address.get(device.display_name.lower())
        if row and row.get('action') == 'rename' and row.get('homekit_name'):
            device.display_name = row['homekit_name']

    if len(devices) > MAX_BRIDGE_ACCESSORIES:
        LOGGER.error('Export list has %d devices; HomeKit bridge limit is %d', len(devices), MAX_BRIDGE_ACCESSORIES)
        raise ValueError(f'too many devices: {len(devices)} > {MAX_BRIDGE_ACCESSORIES}')

    state_store.prune_missing([d.address for d in devices])
    state_store.save()
    return devices
