#!/usr/bin/env python3
"""Polyglot PG3x ISY → HomeKit bridge Node Server entry point."""

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
        polyglot = Interface([Controller])
        polyglot.start(VERSION)
        polyglot.updateProfile()
        Controller(polyglot, 'controller', 'controller', 'ISY HomeKit Bridge')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning('Interrupt or exit')
    except Exception as err:
        LOGGER.error('Fatal: %s', err, exc_info=True)
    sys.exit(0)


if __name__ == '__main__':
    main()
