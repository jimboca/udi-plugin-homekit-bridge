# ISY HomeKit Bridge — Configuration

This node server advertises a **HomeKit bridge** on your LAN. Add it in the Apple Home app, then control exported ISY devices from HomeKit and Siri.

## Prerequisites

1. Install **HomeKit Bridge** in the Polyglot store.
2. Open the node server **Configuration** page.
3. Enable **Allow Unrestricted ISY Access by Node Server**, click **Save**, then **Restart** the node server.

ISY credentials are provided by PG3 through `udi_interface.ISY` — you do not enter ISY host/user/password here.

## Custom parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `export_mode` | `spoken` | `spoken`, `hybrid`, or `all` |
| `mapping_mode` | `common` | `common` or `broad` |
| `hap_port` | `51826` | HomeKit HAP TCP port |
| `hap_pin` | *(auto)* | 8-digit setup code (`123-45-678`). Leave empty to auto-generate and persist. |
| `bridge_name` | `ISY Bridge` | Name shown in Apple Home |
| `advertise_ip` | *(auto)* | LAN IP to advertise. Leave empty to use the Polisy/eISY default interface. |

### Export modes

| Mode | Behavior |
|------|----------|
| `spoken` | Export nodes with the ISY **Spoken** note (set `1` to use the device name, same as Hue Emulator) |
| `hybrid` | Spoken nodes plus typed **Exported devices** rows (`include` / `exclude` / `rename`) |
| `all` | Export all ISY nodes that map to a supported HomeKit type; typed `exclude` rows still apply |

### Mapping modes

| Mode | Device types |
|------|----------------|
| `common` | Lights, switches, fans, thermostats, contact and motion sensors |
| `broad` | Above plus locks, blinds/shades, temperature and humidity sensors, and many PG3 node-server devices |

### Typed table: Exported devices

| Column | Description |
|--------|-------------|
| `node_address` | ISY node address or name |
| `action` | `include`, `exclude`, or `rename` |
| `homekit_name` | Optional display name in Apple Home |
| `hap_type` | Optional forced type: `light`, `switch`, `fan`, `thermostat`, `contact`, `motion`, `lock`, `blind` |

## Apple Home pairing

1. Confirm the controller **Status** driver is **Running** or **Paired**.
2. Send the **Show HomeKit Setup** command (`SHOW_SETUP`) from IoX or check the node server log for the setup code and QR payload.
3. In the Apple Home app: **Add Accessory** → enter the code or scan the QR.
4. Exported devices appear as accessories under the bridge.

**Note:** HomeKit bridges support up to about **150** accessories. Use `hybrid` mode with explicit includes for large installations.

## IoX controller

| Driver | Meaning |
|--------|---------|
| `ST` | `Stopped` / `Running` / `Paired` |
| `GV0` | Exported device count |
| `GV1` | ISY connected |
| `ERR` | Error code (see profile NLS) |

| Command | Action |
|---------|--------|
| `REFRESH` | Rescan ISY and restart the bridge |
| `SHOW_SETUP` | Log/display HomeKit pairing code |

## Spoken property (spoken export mode)

In the ISY Admin Console, open a device's **Notes** and set **Spoken**:

- `1` — use the device name in HomeKit
- Any other plain ASCII string — custom spoken name

For scenes, prefer setting Spoken on the scene controller you want to track (same caveat as Hue Emulator).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ERR` = ISY access not authorized | Enable unrestricted ISY access and restart |
| No devices exported | Check Spoken notes or switch to `hybrid`/`all` |
| Home app cannot find bridge | Verify `hap_port` is not blocked; set `advertise_ip` to your LAN IP |
| Devices changed IDs in HomeKit | Do not delete `config/bridge_state.json` or `config/accessory.state` |

## Related plugins

- **udi-poly-homekit-hub** — pairs *to* HomeKit accessories (Ecobee, etc.); orthogonal to this exporter.
- **udi-poly-hue-emu** — ISY → Hue API for Harmony/Alexa; similar Spoken selection logic.
