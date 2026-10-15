"""Build Plugins Configuration help: CONFIG.md plus exported-devices table."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple


def exported_devices_signature(devices: Sequence[Any]) -> Tuple[Tuple[str, str, str, str, str, str], ...]:
    """Stable signature so we only republish when the inventory changes."""
    rows = []
    for device in devices or []:
        rows.append(
            (
                str(getattr(device, 'address', '') or ''),
                str(getattr(device, 'display_name', '') or ''),
                str(getattr(device, 'hap_type', '') or ''),
                str(getattr(device, 'aid', '') or ''),
                str(getattr(device, 'spoken', '') or ''),
                str(getattr(device, 'override_action', '') or ''),
            )
        )
    return tuple(sorted(rows, key=lambda r: (r[1].lower(), r[0].lower())))


def format_exported_devices_table_html(devices: Iterable[Any]) -> str:
    """Read-only HTML table of devices currently selected for HomeKit export."""
    devices_list = list(devices or [])
    parts = [
        '<h3>Exported devices (read-only)</h3>',
        '<p>Devices currently selected for Apple Home based on <code>export_mode</code>, '
        'Spoken notes, and the typed <b>Exported devices</b> overrides above. '
        'This list updates after <b>Refresh Devices</b> / configuration changes. '
        'It is not the editable typed table.</p>',
        f'<p><b>{len(devices_list)}</b> device(s).</p>',
        '<table border="1" cellpadding="4" cellspacing="0">',
        '<thead><tr>'
        '<th>Address</th>'
        '<th>HomeKit name</th>'
        '<th>HAP type</th>'
        '<th>AID</th>'
        '<th>Spoken</th>'
        '<th>Override</th>'
        '</tr></thead>',
        '<tbody>',
    ]
    for device in sorted(
        devices_list,
        key=lambda d: (
            str(getattr(d, 'display_name', '') or '').lower(),
            str(getattr(d, 'address', '') or '').lower(),
        ),
    ):
        parts.append(
            '<tr>'
            f'<td>{html.escape(str(getattr(device, "address", "") or ""))}</td>'
            f'<td>{html.escape(str(getattr(device, "display_name", "") or ""))}</td>'
            f'<td>{html.escape(str(getattr(device, "hap_type", "") or ""))}</td>'
            f'<td>{html.escape(str(getattr(device, "aid", "") or ""))}</td>'
            f'<td>{html.escape(str(getattr(device, "spoken", "") or ""))}</td>'
            f'<td>{html.escape(str(getattr(device, "override_action", "") or ""))}</td>'
            '</tr>'
        )
    if not devices_list:
        parts.append(
            '<tr><td colspan="6"><i>No devices exported yet. '
            'Set Spoken notes or typed includes, then Refresh Devices.</i></td></tr>'
        )
    parts.append('</tbody></table>')
    return '\n'.join(parts)


def build_custom_params_doc_html(
    config_md_path: Path,
    devices: Sequence[Any],
    *,
    markdown_path_fn,
    markdown_extras: Optional[list] = None,
) -> str:
    """CONFIG.md (HTML) + horizontal rule + exported devices table."""
    extras = markdown_extras or ['tables', 'fenced-code-blocks']
    base = markdown_path_fn(str(config_md_path), extras=extras)
    return base + '\n<hr/>\n' + format_exported_devices_table_html(devices)
