"""IoX node type classification for HomeKit mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from pyisy import constants as pyisy_constants

from const import (
    HAP_TYPE_BLIND,
    HAP_TYPE_CONTACT,
    HAP_TYPE_FAN,
    HAP_TYPE_HUMIDITY_SENSOR,
    HAP_TYPE_LIGHT,
    HAP_TYPE_LOCK,
    HAP_TYPE_MOTION,
    HAP_TYPE_SWITCH,
    HAP_TYPE_TEMP_SENSOR,
    HAP_TYPE_THERMOSTAT,
    MAPPING_MODE_BROAD,
    MAPPING_MODE_COMMON,
)

KPL_SUB_BUTTON = re.compile(r'^[0-9A-F]{2}\s[0-9A-F]{2}\s[0-9A-F]{2}\s[2-9]+')

CONTACT_NODE_DEFS = {
    'DoorSensor_ADV',
    'DoorSensor_ISY',
    'OpenCloseSensor_ADV',
}
MOTION_NODE_DEFS = {
    'MotionSensor_ADV',
    'MotionSensor_ISY',
}
THERMOSTAT_NODE_DEFS = {
    'Thermostat',
    'ThermostatHeatCool',
    'ThermostatHeat',
    'ThermostatCool',
    'ECO_CTR',
}
FAN_NODE_DEFS = {
    'FanLincMotor',
    'FanMotor',
}
LOCK_NODE_DEFS = {
    'LockDoor_ADV',
    'LockDoor_ISY',
}
BLIND_NODE_DEFS = {
    'WindowCovering',
    'WindowShade',
}


@dataclass
class NodeTraits:
    dimmable: bool = False
    is_scene: bool = False
    set_scene: bool = False


def is_kpl_sub_button(address: str) -> bool:
    return KPL_SUB_BUTTON.match(address or '') is not None


def node_traits(node: Any) -> NodeTraits:
    traits = NodeTraits()
    if getattr(node, 'protocol', None) == pyisy_constants.PROTO_GROUP:
        traits.is_scene = True
        traits.set_scene = True
        traits.dimmable = True
        return traits

    if getattr(node, 'dimmable', False) and not is_kpl_sub_button(getattr(node, 'address', '')):
        traits.dimmable = True
    return traits


def _node_def_id(node: Any) -> str:
    return str(getattr(node, 'node_def_id', '') or '')


def _name_blob(node: Any) -> str:
    return f"{getattr(node, 'name', '')} {_node_def_id(node)}".lower()


def classify_node(
    node: Any,
    mapping_mode: str = MAPPING_MODE_COMMON,
    forced_hap_type: Optional[str] = None,
    strict: bool = False,
) -> Optional[str]:
    if forced_hap_type:
        return forced_hap_type

    node_def = _node_def_id(node)
    name_blob = _name_blob(node)

    if node_def in THERMOSTAT_NODE_DEFS or 'thermostat' in name_blob:
        return HAP_TYPE_THERMOSTAT
    if node_def in CONTACT_NODE_DEFS or 'contact' in name_blob or 'door' in name_blob:
        return HAP_TYPE_CONTACT
    if node_def in MOTION_NODE_DEFS or 'motion' in name_blob:
        return HAP_TYPE_MOTION
    if node_def in FAN_NODE_DEFS or re.search(r'\bfan\b', name_blob):
        return HAP_TYPE_FAN

    if mapping_mode == MAPPING_MODE_BROAD:
        if node_def in LOCK_NODE_DEFS or 'lock' in name_blob:
            return HAP_TYPE_LOCK
        if node_def in BLIND_NODE_DEFS or 'shade' in name_blob or 'blind' in name_blob:
            return HAP_TYPE_BLIND
        if 'humidity' in name_blob:
            return HAP_TYPE_HUMIDITY_SENSOR
        if 'temperature' in name_blob and 'thermostat' not in name_blob:
            return HAP_TYPE_TEMP_SENSOR
        if node_def.startswith('n') and '_' in getattr(node, 'address', ''):
            # Plugins node-server devices often have nNNN_ addresses.
            if any(token in name_blob for token in ('sensor', 'weather')):
                return HAP_TYPE_TEMP_SENSOR

    traits = node_traits(node)
    if traits.is_scene or traits.dimmable:
        return HAP_TYPE_LIGHT
    if getattr(node, 'protocol', None) == pyisy_constants.PROTO_GROUP:
        return HAP_TYPE_LIGHT

    # Default on/off nodes to switch in common mode, light if name suggests it.
    if any(token in name_blob for token in ('light', 'lamp', 'dimmer', 'bulb')):
        return HAP_TYPE_LIGHT
    if any(token in name_blob for token in ('switch', 'outlet', 'relay', 'plug')):
        return HAP_TYPE_SWITCH
    return HAP_TYPE_SWITCH if not strict else None
