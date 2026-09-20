#!/usr/bin/env python3
"""Plugins IoX → HomeKit bridge plugin entry point."""

import sys

from udi_interface import Interface, LOGGER

from nodes import VERSION, Controller


def main() -> None:
    if sys.version_info < (3, 10):
        LOGGER.error(
            'Python 3.10+ is required, not %s.%s',
            sys.version_info[0],
            sys.version_info[1],
        )
        sys.exit(1)
    try:
        plugin = Interface([Controller])
        plugin.start(VERSION)
        plugin.updateProfile()
        Controller(plugin, 'controller', 'controller', 'IoX HomeKit Bridge')
        plugin.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning('Interrupt or exit')
    except Exception as err:
        LOGGER.error('Fatal: %s', err, exc_info=True)
    sys.exit(0)


if __name__ == '__main__':
    main()
