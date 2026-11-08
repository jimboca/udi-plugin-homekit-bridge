"""Known IoX nodeDef id → HomeKit type.

Classification uses this table first. The device name is not a type.
A nodeDef that is not listed here is classified from PyISY capabilities
(dimmable, lock, thermostat, climate drivers, Insteon/Z-Wave on/off).

Kasa ids are listed in full. A newer ``SmartBulb_*`` / ``SmartPlug_*`` /
``SmartDimmer_*`` / ``SmartLightStrip_*`` / ``SmartStripPlug_*`` id still resolves,
because that plugin encodes capabilities in the suffix (D dimmable, T color
temperature, C color, E energy, N absent). That suffix is not a name guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from const import (
    HAP_TYPE_BLIND,
    HAP_TYPE_CONTACT,
    HAP_TYPE_FAN,
    HAP_TYPE_GARAGE,
    HAP_TYPE_LIGHT,
    HAP_TYPE_LOCK,
    HAP_TYPE_MOTION,
    HAP_TYPE_OUTLET,
    HAP_TYPE_SWITCH,
    HAP_TYPE_THERMOSTAT,
    HAP_TYPE_VALVE,
)


@dataclass(frozen=True)
class NodeDefSpec:
    """``hap_type`` None means the nodeDef is known and must not be exported."""

    hap_type: Optional[str]
    dimmable: bool = False
    color: bool = False
    color_temperature: bool = False
    brightness_percent: bool = False
    motion_from_alarm: bool = False


_SKIP = NodeDefSpec(None)

# Node server controllers, hubs, and cameras. A camera ST is enable/privacy,
# not a switch, and HomeKit video streaming is not implemented.
_SKIP_IDS = (
    'controller',
    'Controller',
    'host',
    'KasaController',
    'SmartHub_N',
    'SmartCamera_N',
    'SmartCamera_B',
)


def _light(
    *,
    dimmable: bool = False,
    color: bool = False,
    color_temperature: bool = False,
) -> NodeDefSpec:
    return NodeDefSpec(
        HAP_TYPE_LIGHT,
        dimmable=dimmable,
        color=color,
        color_temperature=color_temperature,
        brightness_percent=dimmable,
    )


def _outlet() -> NodeDefSpec:
    return NodeDefSpec(HAP_TYPE_OUTLET)


def _kasa_light_spec(code: str) -> NodeDefSpec:
    return _light(
        dimmable=('D' in code or 'C' in code or 'T' in code),
        color='C' in code,
        color_temperature='T' in code,
    )


def _kasa_family_spec(node_def: str) -> Optional[NodeDefSpec]:
    """Capability suffix for a Kasa nodeDef that is not in the explicit table."""
    for prefix in ('SmartLightStrip_', 'SmartBulb_', 'SmartDimmer_'):
        if node_def.startswith(prefix):
            return _kasa_light_spec(node_def[len(prefix):].split('_', 1)[0])
    for prefix in ('SmartStripPlug_', 'SmartPlug_'):
        if node_def.startswith(prefix):
            return _outlet()
    # The strip parent is one on/off for every socket, not a socket itself.
    if node_def.startswith('SmartStrip_'):
        return NodeDefSpec(HAP_TYPE_SWITCH)
    return None


def _build_map() -> dict[str, NodeDefSpec]:
    table: dict[str, NodeDefSpec] = {node_def: _SKIP for node_def in _SKIP_IDS}

    # Insteon / IoX standard device nodeDefs.
    # Insteon dimmers use the 0–255 scale, not Kasa's 0–100.
    for node_def in (
        'DimmerLampSwitch',
        'DimmerLampSwitch_ADV',
        'KeypadDimmer',
        'KeypadDimmer_ADV',
        'InsteonDimmer',
        'OutletLincDimmer',
    ):
        table[node_def] = NodeDefSpec(HAP_TYPE_LIGHT, dimmable=True)
    for node_def in (
        'RelayLampSwitch',
        'RelayLampSwitch_ADV',
        'KeypadButton',
        'KeypadButton_ADV',
    ):
        table[node_def] = NodeDefSpec(HAP_TYPE_SWITCH)
    for node_def in ('OutletLinc', 'OutletLincOnOff'):
        table[node_def] = _outlet()
    for node_def in ('FanLincMotor', 'FanMotor'):
        table[node_def] = NodeDefSpec(HAP_TYPE_FAN)
    for node_def in (
        'MotionSensor_ADV',
        'MotionSensor_ISY',
    ):
        table[node_def] = NodeDefSpec(HAP_TYPE_MOTION)
    for node_def in (
        'DoorSensor_ADV',
        'DoorSensor_ISY',
        'OpenCloseSensor_ADV',
        'OpenCloseSensor_ISY',
    ):
        table[node_def] = NodeDefSpec(HAP_TYPE_CONTACT)
    for node_def in (
        'Thermostat',
        'ThermostatHeatCool',
        'ThermostatHeat',
        'ThermostatCool',
        'ThermostatF',
        'ThermostatC',
        'ECO_CTR',
    ):
        table[node_def] = NodeDefSpec(HAP_TYPE_THERMOSTAT)
    for node_def in ('LockDoor_ADV', 'LockDoor_ISY'):
        table[node_def] = NodeDefSpec(HAP_TYPE_LOCK)
    for node_def in ('WindowCovering', 'WindowShade'):
        table[node_def] = NodeDefSpec(HAP_TYPE_BLIND)

    # Konnected.
    table['gdo'] = NodeDefSpec(HAP_TYPE_GARAGE)
    table['gdolt'] = _light()

    # Camect. Camera motion is the ALARM driver. ST is camera enabled.
    table['camera'] = NodeDefSpec(HAP_TYPE_MOTION, motion_from_alarm=True)
    for node_def in ('human', 'vehicle', 'animal', 'insect', 'objdet'):
        table[node_def] = NodeDefSpec(HAP_TYPE_MOTION)

    # Moen Flo shutoff. ST 0 closed, 1 open. Command is SET_VALVE, not DON/DOF.
    table['modev'] = NodeDefSpec(HAP_TYPE_VALVE)

    # ELK loads that are actually lights, outputs, or thermostats.
    # Zones are not listed: a zone can be motion, contact, or a life-safety sensor.
    table['light'] = _light()
    table['output'] = NodeDefSpec(HAP_TYPE_SWITCH)

    # Kasa. Explicit ids from udi-poly-kasa profile/nodedef/nodedefs.xml.
    kasa_lights = {
        'SmartBulb_NNNN': '',
        'SmartBulb_DNNN': 'D',
        'SmartBulb_DTNN': 'DT',
        'SmartBulb_DTCN': 'DTC',
        'SmartBulb_DTCE': 'DTC',
        'SmartBulb_DTNE': 'DT',
        'SmartBulb_DNNE': 'D',
        'SmartBulb_DNNE_old': 'D',
        'SmartLightStrip_DTCE': 'DTC',
        'SmartLightStrip_DTCN': 'DTC',
        'SmartLightStrip_DNCE': 'DC',
        'SmartDimmer_DN': 'D',
        'SmartDimmer_DE': 'D',
        'SmartDimmer_NN': '',
    }
    for node_def, code in kasa_lights.items():
        table[node_def] = _kasa_light_spec(code)
    for node_def in (
        'SmartPlug_NN',
        'SmartPlug_NE',
        'SmartPlug_DN',
        'SmartPlug_DE',
        'SmartStripPlug_N',
        'SmartStripPlug_E',
    ):
        table[node_def] = _outlet()
    # HS300 and similar. One switch for every socket. Children are the outlets.
    table['SmartStrip_N'] = NodeDefSpec(HAP_TYPE_SWITCH)
    table['SmartStrip_E'] = NodeDefSpec(HAP_TYPE_SWITCH)
    return table


NODEDEF_MAP: dict[str, NodeDefSpec] = _build_map()


def lookup_nodedef(node_def: str) -> Optional[NodeDefSpec]:
    """Return the spec for a known nodeDef, or None when it is not in the map.

    Ecobee ids are ``EcobeeHKC_<id>`` (the template token is replaced per device).
    """
    if not node_def:
        return None
    spec = NODEDEF_MAP.get(node_def)
    if spec is not None:
        return spec
    if node_def.startswith('Ecobee'):
        return NodeDefSpec(HAP_TYPE_THERMOSTAT)
    return _kasa_family_spec(node_def)
