"""PyISY compatibility patches for eISY / IoX 5+.

PG3 hands plugins a JWT as the IoX password via ``udi_interface.ISY``.
Stock PyISY (2.x) builds the event-stream Basic auth with
``base64.encodebytes()``, which inserts newlines every 76 characters.
eISY then rejects the SOAP ``/services`` Subscribe with HTTP 400, and
unsubscribe crashes with ``KeyError: 'sid'``.

Also normalize SOAP templates to CRLF (HTTP requires it; PyISY uses bare LF).

Call ``apply_pyisy_eisy_patches()`` once before ``pyisy.auto_update = True``.
REST / node load works without this; only the event stream needs it.
"""

from __future__ import annotations

import base64
import logging

_LOGGER = logging.getLogger(__name__)
_APPLIED = False


def apply_pyisy_eisy_patches() -> None:
    """Idempotent patches for PyISY event-stream use on eISY."""
    global _APPLIED
    if _APPLIED:
        return
    try:
        from pyisy import strings
        from pyisy.connection import Connection
    except ImportError:
        _LOGGER.warning('PyISY not installed; skipping eISY patches')
        return

    for name in ('SUB_MSG', 'UNSUB_MSG', 'RESUB_MSG'):
        msg = getattr(strings, name, None)
        if not isinstance(msg, dict):
            continue
        for key in ('head', 'body'):
            text = msg.get(key)
            if isinstance(text, str):
                msg[key] = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')

    @property
    def connection_info(self):
        info = {}
        authstr = bytes(f'{self._username}:{self._password}', 'ascii')
        # b64encode — NOT encodebytes — so JWT passwords stay on one header line.
        info['auth'] = base64.b64encode(authstr).decode('ascii')
        info['addr'] = self._address
        info['port'] = int(self._port)
        info['passwd'] = self._password
        info['webroot'] = self._webroot
        if self._tls_ver:
            info['tls'] = self._tls_ver
        return info

    Connection.connection_info = connection_info
    _APPLIED = True
    _LOGGER.info('Applied PyISY eISY event-stream patches (auth b64 + SOAP CRLF)')
