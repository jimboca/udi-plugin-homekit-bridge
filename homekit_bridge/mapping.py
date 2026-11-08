"""IoX node type classification for HomeKit mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from pyisy import constants as pyisy_constants

from const import (
    HAP_TYPE_HUMIDITY_SENSOR,
    HAP_TYPE_LIGHT,
    HAP_TYPE_LOCK,
    HAP_TYPE_SWITCH,
    HAP_TYPE_TEMP_SENSOR,
    HAP_TYPE_THERMOSTAT,
    MAPPING_MODE_BROAD,
    MAPPING_MODE_COMMON,
)
from homekit_bridge.nodedef_map import lookup_nodedef

KPL_SUB_BUTTON = re.compile(r'^[0-9A-F]{2}\s[0-9A-F]{2}\s[0-9A-F]{2}\s[2-9]+')

# Climate drivers. Setpoints mean a thermostat. CO2 / VOC / pressure mean an
# air-quality sensor, which is not a temperature sensor.
_THERMOSTAT_DRIVERS = frozenset({'CLISPH', 'CLISPC', 'CLIMD'})
_AIR_QUALITY_DRIVERS = frozenset({'CO2LVL', 'VOCLVL', 'BARPRES'})
_BINARY_PROTOCOLS = frozenset({
    pyisy_constants.PROTO_INSTEON,
    pyisy_constants.PROTO_ZWAVE,
    pyisy_constants.PROTO_ZIGBEE,
})


@dataclass
class NodeTraits:
    dimmable: bool = False
    is_scene: bool = False
    set_scene: bool = False
    color: bool = False
    color_temperature: bool = False
    # Kasa ST / DON use 0–100. Insteon dimmers stay on the 0–255 scale.
    brightness_percent: bool = False
    # Camect camera motion is the ALARM aux driver, not ST.
    motion_from_alarm: bool = False


def is_kpl_sub_button(address: str) -> bool:
    return KPL_SUB_BUTTON.match(address or '') is not None


def _driver_ids(node: Any) -> frozenset[str]:
    aux = getattr(node, 'aux_properties', None) or {}
    try:
        keys = aux.keys()
    except AttributeError:
        return frozenset()
    return frozenset(str(key).upper() for key in keys)


def _is_dimmable(node: Any) -> bool:
    if is_kpl_sub_button(getattr(node, 'address', '')):
        return False
    if getattr(node, 'is_dimmable', None):
        return True
    return bool(getattr(node, 'dimmable', False))


def node_traits(node: Any) -> NodeTraits:
    traits = NodeTraits()
    if getattr(node, 'protocol', None) == pyisy_constants.PROTO_GROUP:
        traits.is_scene = True
        traits.set_scene = True
        traits.dimmable = True
        return traits

    spec = lookup_nodedef(_node_def_id(node))
    if spec is not None and spec.hap_type is not None:
        traits.dimmable = spec.dimmable
        traits.color = spec.color
        traits.color_temperature = spec.color_temperature
        traits.brightness_percent = spec.brightness_percent
        traits.motion_from_alarm = spec.motion_from_alarm
    if _is_dimmable(node):
        traits.dimmable = True
    return traits


def _node_def_id(node: Any) -> str:
    return str(getattr(node, 'node_def_id', '') or '')


def _excluded_from_export(node: Any) -> bool:
    """Nodes that must not be advertised, including in export_mode=all.

    - HomeKit Hub copies (nodeDef ``HKHub…``, or the pairing node title).
    - IoX Auto DR, address ``ADR…``. It is a system scene, not a dimmer.
    """
    node_def = _node_def_id(node)
    if node_def.upper().startswith('HKHUB'):
        return True
    name = str(getattr(node, 'name', '') or '').strip()
    if name.endswith('(Pairing)'):
        return True
    address = str(getattr(node, 'address', '') or '').strip().upper()
    if address.startswith('ADR') or name.casefold() == 'auto dr':
        return True
    return False


def _classify_by_capability(node: Any, mapping_mode: str) -> Optional[str]:
    """Type from the node itself when its nodeDef is not in the map."""
    if getattr(node, 'is_lock', False):
        return HAP_TYPE_LOCK
    drivers = _driver_ids(node)
    if getattr(node, 'is_thermostat', False) or drivers & _THERMOSTAT_DRIVERS:
        return HAP_TYPE_THERMOSTAT
    if drivers & _AIR_QUALITY_DRIVERS:
        # Temperature plus CO2, VOC, or pressure is an air-quality sensor.
        return None
    if mapping_mode == MAPPING_MODE_BROAD:
        if 'CLITEMP' in drivers:
            return HAP_TYPE_TEMP_SENSOR
        if 'CLIHUM' in drivers:
            return HAP_TYPE_HUMIDITY_SENSOR

    if getattr(node, 'protocol', None) == pyisy_constants.PROTO_GROUP or _is_dimmable(node):
        return HAP_TYPE_LIGHT
    if getattr(node, 'protocol', None) in _BINARY_PROTOCOLS:
        return HAP_TYPE_SWITCH
    return None


def explain_classification(
    node: Any,
    mapping_mode: str = MAPPING_MODE_COMMON,
    forced_hap_type: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Return ``(hap_type, via)``.

    ``via`` is ``excluded``, ``forced``, ``nodedef``, ``nodedef-skip``,
    ``capability``, ``air-quality``, or ``unmapped``.
    """
    if _excluded_from_export(node):
        return None, 'excluded'
    if forced_hap_type:
        return forced_hap_type, 'forced'
    spec = lookup_nodedef(_node_def_id(node))
    if spec is not None:
        if spec.hap_type is None:
            return None, 'nodedef-skip'
        return spec.hap_type, 'nodedef'
    if _driver_ids(node) & _AIR_QUALITY_DRIVERS:
        return None, 'air-quality'
    hap_type = _classify_by_capability(node, mapping_mode)
    if hap_type:
        return hap_type, 'capability'
    return None, 'unmapped'


def classify_node(
    node: Any,
    mapping_mode: str = MAPPING_MODE_COMMON,
    forced_hap_type: Optional[str] = None,
    strict: bool = False,
) -> Optional[str]:
    """Map a node to a HomeKit type.

    Order: export exclusions, typed ``hap_type``, the known nodeDef table,
    then capabilities. ``strict`` is accepted for callers; unknown node
    servers stay unexported in either mode.
    """
    del strict
    hap_type, _via = explain_classification(
        node,
        mapping_mode=mapping_mode,
        forced_hap_type=forced_hap_type,
    )
    return hap_type


def _prop_text(prop: Any) -> str:
    if isinstance(prop, dict):
        value = prop.get('value')
        uom = prop.get('uom') or ''
        formatted = prop.get('formatted')
    else:
        value = getattr(prop, 'value', prop)
        uom = getattr(prop, 'uom', '') or ''
        formatted = getattr(prop, 'formatted', None)
    text = '' if value is None else str(value)
    if formatted not in (None, '', value) and str(formatted) != text:
        text = f'{text}({formatted})'
    if uom:
        text = f'{text}/{uom}'
    return text


def format_node_debug(
    node: Any,
    *,
    hap_type: Optional[str],
    via: str,
    exported: bool,
) -> str:
    """One log line: identity, drivers, and why it did or did not export."""
    aux = getattr(node, 'aux_properties', None) or {}
    try:
        items = list(aux.items())
    except AttributeError:
        items = []
    drivers = ','.join(
        f'{key}={_prop_text(prop)}' for key, prop in sorted(items, key=lambda item: str(item[0]))
    )
    traits = node_traits(node)
    trait_bits = []
    if traits.dimmable:
        trait_bits.append('dim')
    if traits.brightness_percent:
        trait_bits.append('percent')
    if traits.color:
        trait_bits.append('color')
    if traits.color_temperature:
        trait_bits.append('ct')
    if traits.motion_from_alarm:
        trait_bits.append('alarm')
    if traits.is_scene:
        trait_bits.append('scene')
    name = str(getattr(node, 'name', '') or '').replace("'", '')
    return (
        "HomeKit device "
        f"addr='{getattr(node, 'address', '')}' "
        f"name='{name}' "
        f"nodeDef='{_node_def_id(node)}' "
        f"protocol='{getattr(node, 'protocol', '') or ''}' "
        f"family='{getattr(node, 'family', '') or ''}' "
        f"type='{getattr(node, 'type', '') or ''}' "
        f"dimmable={_is_dimmable(node)} "
        f"lock={bool(getattr(node, 'is_lock', False))} "
        f"thermostat={bool(getattr(node, 'is_thermostat', False))} "
        f"status={getattr(node, 'status', '')} "
        f"uom='{getattr(node, 'uom', '') or ''}' "
        f"drivers='{drivers}' "
        f"traits='{','.join(trait_bits)}' "
        f"class='{hap_type or ''}' "
        f"via='{via}' "
        f"export={'yes' if exported else 'no'}"
    )
