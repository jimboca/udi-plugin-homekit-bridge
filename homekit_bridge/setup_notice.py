"""HomeKit setup payload and Plugins notice formatting."""

from __future__ import annotations

import base64
import html
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def notice_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')


@dataclass(frozen=True)
class HomeKitSetupDetails:
    bridge_name: str
    pincode: str
    xhm_uri: str
    advertise_ip: str
    hap_port: int
    paired: bool


def homekit_qr_notice_html(payload: str) -> str:
    """Inline QR image for Plugins notices, or empty string if rendering unavailable."""
    if not payload:
        return ''
    try:
        import segno
    except ImportError:
        LOGGER.warning('segno not installed; HomeKit QR image omitted from notice')
        return ''

    try:
        qr = segno.make(payload, error='m', boost_error=False)
        buf = io.BytesIO()
        qr.save(buf, kind='png', scale=5, border=2)
        png_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        LOGGER.exception('Failed to render HomeKit QR code')
        return ''

    return (
        '<p><b>Scan with Apple Home</b></p>'
        f'<p><img src="data:image/png;base64,{png_b64}" alt="HomeKit QR code" '
        'style="max-width:220px;height:auto;border:1px solid #ccc"/></p>'
        f'<p><small><code>{html.escape(payload)}</code></small></p>'
    )


def build_setup_details(bridge: Any) -> Optional[HomeKitSetupDetails]:
    """Extract PIN + X-HM URI from a running IsyHomeKitBridge / AccessoryDriver."""
    driver = getattr(bridge, 'driver', None)
    if driver is None:
        return None
    accessory = getattr(driver, 'accessory', None)
    state = getattr(driver, 'state', None)
    if accessory is None or state is None:
        return None

    pincode = state.pincode.decode() if isinstance(state.pincode, (bytes, bytearray)) else str(state.pincode)
    xhm_uri = ''
    try:
        if hasattr(accessory, 'xhm_uri'):
            xhm_uri = str(accessory.xhm_uri())
    except Exception:
        LOGGER.exception('Failed to build HomeKit X-HM URI (install HAP-python[QRCode])')

    advertise_ip = ''
    try:
        addresses = getattr(state, 'addresses', None) or []
        if addresses:
            advertise_ip = str(addresses[0])
        elif getattr(state, 'address', None):
            advertise_ip = str(state.address)
    except Exception:
        pass

    paired = False
    try:
        paired = bool(getattr(bridge, 'is_paired', lambda: False)())
    except Exception:
        paired = False

    return HomeKitSetupDetails(
        bridge_name=str(getattr(accessory, 'display_name', None) or getattr(bridge, 'bridge_name', 'IoX Bridge')),
        pincode=pincode,
        xhm_uri=xhm_uri,
        advertise_ip=advertise_ip,
        hap_port=int(getattr(state, 'port', 0) or getattr(bridge, 'hap_port', 0) or 0),
        paired=paired,
    )


def format_setup_notice_html(details: HomeKitSetupDetails) -> str:
    """HTML body for the Plugins Notices panel (HomeKit pairing)."""
    status = 'Paired' if details.paired else 'Awaiting pairing'
    qr_html = homekit_qr_notice_html(details.xhm_uri) if details.xhm_uri else (
        '<p><i>QR payload unavailable — install HAP-python[QRCode] and segno, '
        'then run Show HomeKit Setup again. You can still enter the setup code below.</i></p>'
    )
    ip_line = (
        f'<tr><td>IP</td><td><code>{html.escape(details.advertise_ip)}</code></td></tr>'
        if details.advertise_ip
        else ''
    )
    uri_line = (
        f'<tr><td>HomeKit QR payload</td><td><code>{html.escape(details.xhm_uri)}</code></td></tr>'
        if details.xhm_uri
        else ''
    )
    return (
        f'<p><small>{html.escape(notice_timestamp())}</small></p>'
        f'<p><b>HomeKit pairing</b> — {html.escape(details.bridge_name)} '
        f'(<i>{html.escape(status)}</i>)</p>'
        f'{qr_html}'
        '<table>'
        f'<tr><td>Setup code</td><td><code>{html.escape(details.pincode)}</code></td></tr>'
        f'{uri_line}'
        f'{ip_line}'
        f'<tr><td>Port</td><td><code>{details.hap_port}</code></td></tr>'
        '</table>'
        '<p><b>Apple Home:</b> scan the QR code above, or Home app → <b>+</b> → <b>Add Accessory</b> → '
        'enter the setup code.</p>'
        '<p>Phone must be on the <b>same Wi‑Fi / LAN</b> as the eISY. '
        '<b>Advertise</b> must be On (timed window) for discovery.</p>'
        '<p>Run <b>Show HomeKit Setup</b> on the controller node to refresh these details.</p>'
    )


def format_setup_log_message(details: HomeKitSetupDetails) -> str:
    lines = [
        f'HomeKit bridge: {details.bridge_name}',
        f'Setup code: {details.pincode}',
    ]
    if details.xhm_uri:
        lines.append(f'HomeKit QR: {details.xhm_uri}')
    if details.advertise_ip:
        lines.append(f'IP: {details.advertise_ip}')
    lines.append(f'Port: {details.hap_port}')
    return '\n'.join(lines)
