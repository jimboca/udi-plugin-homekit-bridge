"""Turn a PG3 Bonjour browse into a short HomeKit visibility report.

PG3 only searches for advertised services. This module does not publish.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence

# PG3 waits about 10s, then delivers results (or nothing, if the list is empty).
MDNS_DEBOUNCE_SEC = 1.0
MDNS_WATCHDOG_SEC = 15.0

_SERVICE_KEYS = ('name', 'port', 'host', 'fqdn', 'addresses', 'fullname')
_MAX_LISTED = 8


@dataclass(frozen=True)
class HapService:
    name: str
    host: str
    port: int
    addresses: tuple


@dataclass(frozen=True)
class MdnsSummary:
    found: bool
    count: int
    log: str
    notice_html: str


def normalize_services(payload: Any) -> List[HapService]:
    """Accept one service dict, a list of them, or a ``services`` wrapper."""
    return [_as_service(item) for item in _unwrap(payload) if isinstance(item, dict)]


def service_matches(service: HapService, bridge_name: str, hap_port: int) -> bool:
    expected = str(bridge_name or '').strip().casefold()
    actual = service.name.casefold()
    if not expected or not actual:
        return False
    try:
        port = int(hap_port)
    except (TypeError, ValueError):
        return False
    if service.port != port:
        return False
    # HAP-python advertises "IoX Bridge 5E6BDE", not the bare display name.
    return actual == expected or actual.startswith(expected + ' ')


def format_debug_report(
    services: Sequence[HapService],
    bridge_name: str,
    hap_port: int,
    *,
    uid: str = '',
    payload_keys: Sequence[str] = (),
) -> str:
    """One log line per advertised bridge, plus whether it is ours."""
    name = str(bridge_name or '').strip() or 'this bridge'
    try:
        port = int(hap_port)
    except (TypeError, ValueError):
        port = 0
    keys = ','.join(payload_keys) if payload_keys else '-'
    lines = [
        (
            f'HAP mDNS browse detail: expect {name!r} port {port} '
            f'uid {uid or "-"} reply_keys {keys} count {len(services)}'
        )
    ]
    if not services:
        lines.append('  (no _hap._tcp services in the Plugins reply)')
    for service in services:
        mark = 'MATCH' if service_matches(service, bridge_name, port) else 'other'
        host = service.host or '-'
        addrs = ', '.join(service.addresses) or '-'
        lines.append(f'  {mark}: {service.name!r} {host}:{service.port} [{addrs}]')
    return '\n'.join(lines)


def summarize(
    services: Sequence[HapService],
    bridge_name: str,
    hap_port: int,
) -> MdnsSummary:
    """Say whether this bridge's name and port appeared in a browse."""
    name = str(bridge_name or '').strip() or 'this bridge'
    try:
        port = int(hap_port)
    except (TypeError, ValueError):
        port = 0
    found = any(service_matches(service, bridge_name, port) for service in services)
    text = _summary_text(services, name, port, found)
    return MdnsSummary(
        found=found,
        count=len(services),
        log='HAP mDNS browse: ' + text,
        notice_html=f'<p>{html.escape(text)}</p>',
    )


def _unwrap(payload: Any) -> List[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping):
        for key in ('mdns', 'services', 'bonjour'):
            inner = payload.get(key)
            if isinstance(inner, list):
                return inner
        if any(key in payload for key in _SERVICE_KEYS):
            return [payload]
    return []


def _as_service(item: Mapping[str, Any]) -> HapService:
    return HapService(
        name=_service_name(item),
        host=str(item.get('host') or '').strip().rstrip('.'),
        port=_port(item.get('port')),
        addresses=tuple(_addresses(item)),
    )


def _service_name(item: Mapping[str, Any]) -> str:
    name = str(item.get('name') or '').strip()
    if name:
        return name
    fqdn = str(item.get('fqdn') or item.get('fullname') or '').strip()
    lowered = fqdn.casefold()
    for suffix in ('._hap._tcp.local.', '._hap._tcp.local'):
        if lowered.endswith(suffix):
            return fqdn[: -len(suffix)]
    return fqdn


def _port(value: Any) -> int:
    try:
        if value is None or value == '':
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _addresses(item: Mapping[str, Any]) -> List[str]:
    raw = item.get('addresses')
    found: List[str] = []
    if isinstance(raw, (list, tuple)):
        for entry in raw:
            text = _address_text(entry)
            if text:
                found.append(text)
    elif isinstance(raw, str) and raw.strip():
        found.append(raw.strip())
    if found:
        return found
    referer = item.get('referer')
    if isinstance(referer, Mapping):
        text = _address_text(referer.get('address'))
        if text:
            return [text]
    return []


def _address_text(entry: Any) -> str:
    if isinstance(entry, (list, tuple)):
        entry = entry[0] if entry else ''
    if isinstance(entry, Mapping):
        entry = entry.get('address') or entry.get('addr') or ''
    text = str(entry or '').strip()
    return text


def _summary_text(
    services: Sequence[HapService],
    name: str,
    port: int,
    found: bool,
) -> str:
    if not services:
        return (
            'No HomeKit bridges were seen on the local network. '
            'Advertise uses multicast on UDP port 5353, which works only when '
            'this node server runs as polyglot (the same user as the system mDNS responder).'
        )
    shown = list(services[:_MAX_LISTED])
    details = '; '.join(_format_service(service) for service in shown)
    extra = len(services) - len(shown)
    if extra > 0:
        details = f'{details}; and {extra} more'
    if found:
        return (
            f'This bridge ({name}, port {port}) is visible on the local network. '
            f'Seen ({len(services)}): {details}.'
        )
    return (
        f'This bridge ({name}, port {port}) was not seen on the local network. '
        f'Other HomeKit advertisements ({len(services)}): {details}. '
        'The node server must run as polyglot to share UDP port 5353.'
    )


def _format_service(service: HapService) -> str:
    label = service.name or '(unnamed)'
    if service.host and service.addresses:
        place = f'{service.host}:{service.port} [{", ".join(service.addresses)}]'
    elif service.host:
        place = f'{service.host}:{service.port}'
    elif service.addresses:
        place = f'{service.addresses[0]}:{service.port}'
    else:
        place = f'?:{service.port}'
    return f'{label} {place}'
