# udi-plugin-homekit-bridge

Expose selected IoX devices to **Apple Home** via a local HomeKit bridge on eISY.

## Requirements

- Python 3.10+
- Plugins with `udi_interface` 3.0.31+ (includes PyISY)
- **Allow Unrestricted IoX Access by Node Server** enabled for this node server

## Setup

See [CONFIG.md](CONFIG.md) for the quick start, export modes, Advertise pairing window, Spoken notes, typed overrides, and Apple Home setup. Color bulbs and light strips are advertised as HomeKit color lights. Plugs and outlets use the HomeKit Outlet service. The Moen Flo shutoff is a HomeKit valve. Camect doorbell detections are motion sensors. Device type comes from the known nodeDef table, not from the device name. An unknown thermostat temperature does not stop the bridge from listening.

Apple Home discovers the bridge only when the node server runs as **polyglot**, so it can share UDP port 5353 with the system mDNS responder. After **Advertise** is On, a Plugins notice reports whether this bridge is visible on the local network.

## License

MIT
