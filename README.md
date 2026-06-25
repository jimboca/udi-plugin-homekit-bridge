# udi-poly-homekit-bridge

Expose selected ISY / IoX devices to **Apple Home** via a local HomeKit bridge on Polisy or eISY.

Pair with the sibling plugin **`udi-poly-homekit-hub`** (which imports HomeKit accessories *into* IoX). This bridge exports IoX/ISY devices *to* Apple Home.

| Plugin | Direction |
|--------|-----------|
| `udi-poly-homekit-hub` | HomeKit accessories → ISY |
| `udi-poly-homekit-bridge` | ISY → Apple Home |

## Requirements

- Python 3.10+
- PG3 with `udi_interface` 3.0.31+ (includes PyISY)
- **Allow Unrestricted ISY Access by Node Server** enabled for this node server

## Setup

See [CONFIG.md](CONFIG.md) for export modes, Spoken notes, typed overrides, and Apple Home pairing.

## License

MIT
