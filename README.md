# udi-plugin-homekit-bridge

Expose selected IoX devices to **Apple Home** via a local HomeKit bridge on eISY.

## Requirements

- Python 3.10+
- Plugins with `udi_interface` 3.0.31+ (includes PyISY)
- **Allow Unrestricted IoX Access by Node Server** enabled for this node server

## Setup

See [CONFIG.md](CONFIG.md) for the quick start, export modes, Advertise pairing window, Spoken notes, typed overrides, and Apple Home setup.

Apple Home discovers the bridge only when the node server runs as **polyglot**, so it can share UDP port 5353 with the system mDNS responder. After **Advertise** is On, a Plugins notice reports whether this bridge is visible on the local network.

## License

MIT
