# Changelog

## [Unreleased]

## [1.0.0] - 2026-10-15

### Added

- Configuration quick start. Default `export_mode` is `spoken` (Spoken notes only). `all` exports every mapped device and uses `mapping_mode` (`common` or `broad`). `hybrid` adds the Exported devices table. Refresh with **Refresh Devices** or a dashboard **Restart**, then review the exported-devices table.
- Garage door openers. Konnected `gdo` nodes, and nodes whose names contain “garage door”, map to HomeKit garage doors. Force the type with `hap_type=garage` when auto-detect misses.
- Saving configuration refreshes the exported devices and rebuilds the bridge. The Configuration help page lists the devices that will be sent to Apple Home.
- After the bridge starts, and from **Show HomeKit Setup**, browse `_hap._tcp` and post a notice when this bridge’s name and port are visible. `logs/debug.log` lists every browsed bridge and whether it matches. Live advertising is still HomeKit multicast on UDP port 5353 and requires the node server to run as **polyglot**.

### Fixed

- The visibility notice reads the Plugins browse reply and treats a suffixed advertisement name such as **IoX Bridge 5E6BDE** as this bridge when the port matches.
- Enable the eISY PyISY event-stream patch only when HomeKit accessories need live status.
