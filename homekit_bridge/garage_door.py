"""IoX ↔ HAP garage door state mapping (Konnected GDO and similar).

Konnected / ratgdo-style IoX ST (uom 25):
  0 Closed, 1 Open, 2 Stopped, 3 Closing, 4 Opening, 9 Unknown

HAP GarageDoorOpener CurrentDoorState:
  0 Open, 1 Closed, 2 Opening, 3 Closing, 4 Stopped

HAP TargetDoorState: 0 Open, 1 Closed
"""

from __future__ import annotations

from typing import Any, Optional

# IoX ST indexes (udi-plugin-konnected)
IOX_CLOSED = 0
IOX_OPEN = 1
IOX_STOPPED = 2
IOX_CLOSING = 3
IOX_OPENING = 4
IOX_UNKNOWN = 9

# HAP CurrentDoorState
HAP_CURRENT_OPEN = 0
HAP_CURRENT_CLOSED = 1
HAP_CURRENT_OPENING = 2
HAP_CURRENT_CLOSING = 3
HAP_CURRENT_STOPPED = 4

# HAP TargetDoorState
HAP_TARGET_OPEN = 0
HAP_TARGET_CLOSED = 1

_IOX_TO_HAP_CURRENT = {
    IOX_CLOSED: HAP_CURRENT_CLOSED,
    IOX_OPEN: HAP_CURRENT_OPEN,
    IOX_STOPPED: HAP_CURRENT_STOPPED,
    IOX_CLOSING: HAP_CURRENT_CLOSING,
    IOX_OPENING: HAP_CURRENT_OPENING,
    IOX_UNKNOWN: HAP_CURRENT_STOPPED,
}


def iox_to_hap_current(iox_state: int) -> int:
    return _IOX_TO_HAP_CURRENT.get(int(iox_state), HAP_CURRENT_STOPPED)


def iox_to_hap_target(iox_state: int) -> int:
    """Target mirrors open/opening vs everything else (closed/closing/stopped)."""
    if int(iox_state) in (IOX_OPEN, IOX_OPENING):
        return HAP_TARGET_OPEN
    return HAP_TARGET_CLOSED


def aux_obstruction_detected(node: Any) -> bool:
    """Read IoX GV1 (Konnected Obstruction: 0 Clear, 1 Active, 101 Unknown)."""
    aux = getattr(node, 'aux_properties', None) or {}
    prop = aux.get('GV1')
    if prop is None:
        return False
    try:
        return int(getattr(prop, 'value', prop)) == 1
    except (TypeError, ValueError):
        return False
