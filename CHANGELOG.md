# Changelog

## [Unreleased]

### Added

- Plugs and outlets advertise as the HomeKit **Outlet** service. Wall switches and relays stay switches.
- HomeKit type comes from a table of known IoX nodeDefs, then from the node's capabilities. The device name is not used. A node server device that is not in the table is left out. Set `hap_type` on that row to force one.
- Moen Flo shutoff (`modev`) advertises as a HomeKit valve. Open and closed are on and off (`SET_VALVE`).
- Each device refresh logs one debug line per node: nodeDef, driver values, the HomeKit type, and why it was or was not exported.
- A Kasa power strip (`SmartStrip HS300`) is a switch, not an outlet. On and off switch every socket. Each socket on the strip remains an outlet.
- Kasa color light strips and color bulbs advertise as HomeKit color lights (on, brightness, hue, saturation, and color temperature when the nodeDef has it). Dimmable Kasa lights advertise brightness even when IoX does not mark the node server node as dimmable.
- Camect camera and object-detection nodes (human, vehicle, animal, insect) advertise as motion sensors. A camera named Doorbell is no longer a contact sensor.

### Fixed

- A device is no longer typed from its name. Doorbell and Outdoor Light are not contact sensors, and a name containing "garage" is not a garage door. A garage door is the Konnected `gdo` nodeDef.
- HomeKit Hub nodes (nodeDef `HKHub…`) and names ending with `(Pairing)` are not exported. Those nodes are the hub's copy of this bridge.
- **Auto DR** (`ADR…`) is not exported. It is an IoX system scene, not a dimmer.

## [1.0.0] - 2026-10-15

### Added

- Configuration quick start. Default `export_mode` is `spoken` (Spoken notes only). `all` exports every mapped device and uses `mapping_mode` (`common` or `broad`). `hybrid` adds the Exported devices table. Refresh with **Refresh Devices** or a dashboard **Restart**, then review the exported-devices table.
- Garage door openers. Konnected `gdo` nodes, and nodes whose names contain “garage door”, map to HomeKit garage doors. Force the type with `hap_type=garage` when auto-detect misses.
- Saving configuration refreshes the exported devices and rebuilds the bridge. The Configuration help page lists the devices that will be sent to Apple Home.
- After the bridge starts, and from **Show HomeKit Setup**, browse `_hap._tcp` and post a notice when this bridge’s name and port are visible. `logs/debug.log` lists every browsed bridge and whether it matches. Live advertising is still HomeKit multicast on UDP port 5353 and requires the node server to run as **polyglot**.

### Fixed

- The visibility notice reads the Plugins browse reply and treats a suffixed advertisement name such as **IoX Bridge 5E6BDE** as this bridge when the port matches.
- Enable the eISY PyISY event-stream patch only when HomeKit accessories need live status.
