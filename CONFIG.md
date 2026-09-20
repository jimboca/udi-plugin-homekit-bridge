# IoX HomeKit Bridge — Configuration

This node server can expose selected IoX devices to **Apple Home**. It does **not** advertise or accept HomeKit connections until you turn **Advertise** On (timed window).

## Prerequisites

1. Install **HomeKit Bridge** in the Plugins store.
2. Open the node server **Configuration** page.
3. Enable **Allow Unrestricted IoX Access by Node Server**, click **Save**, then **Restart** the node server.

IoX credentials are provided by Plugins through `udi_interface.ISY` — you do not enter IoX host/user/password here.

## Custom parameters

Unless you change them on the Configuration page, the plugin uses these defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `export_mode` | `spoken` | Which IoX devices are offered to Apple Home |
| `mapping_mode` | `common` | How device types map to HomeKit accessories |
| `hap_port` | `51826` | HomeKit HAP TCP port |
| `hap_pin` | *(empty / auto)* | 8-digit setup code; empty = auto-generate and persist |
| `bridge_name` | `IoX Bridge` | Name shown in Apple Home |
| `advertise_ip` | *(empty / auto)* | LAN IP advertised over mDNS |
| `advertise_timeout` | `5` | Minutes **Advertise** stays On |

After changing any of these (except `advertise_timeout`), run **Refresh Devices** or restart the node server so the bridge rebuilds.

### `export_mode`

**What it is for:** Controls *which* IoX nodes become HomeKit accessories. HomeKit bridges are limited to about **150** accessories, so prefer an explicit selection on large systems.

**How to use it:** Set `export_mode` to one of the values below, **Save**, then **Refresh Devices**. Watch **Exported Device Count** (`GV0`) to confirm the result.

Default: **`spoken`**.

#### `spoken`

Only nodes that have an IoX **Spoken** note are exported.

1. In the IoX Admin Console or eisy-ui, open the device → **Notes**.
2. Set **Spoken** to:
   - `1` — use the device’s IoX name in Apple Home
   - any other plain ASCII string — use that string as the Apple Home name
3. Save notes, then **Refresh Devices** on the bridge controller.

Use this when you want an opt-in list (same idea as Hue Emulator). Typed **Exported devices** rows do **not** add or remove devices in this mode (selection is Spoken-only).

For scenes, set Spoken on the scene controller you care about.

#### `hybrid`

Exports every Spoken node **plus** devices you list in the typed **Exported devices** table.

Typical workflow:

1. Keep Spoken notes on the devices you always want.
2. Add typed rows with `action` = `include` for devices that should appear without Spoken.
3. Use `exclude` to hide a Spoken device you do not want in Apple Home.
4. Use `rename` (with `homekit_name`) to change the Apple Home name without editing Spoken.

Best for mid-size installs: Spoken for most devices, typed rows for exceptions.

#### `all`

Walks all IoX nodes and exports every one that maps to a supported HomeKit type (see `mapping_mode`).

- Typed `exclude` rows still remove devices.
- Typed `include` is usually unnecessary (already exporting everything mappable).
- Typed `rename` / `homekit_name` / `hap_type` still apply.

Use for small systems or first-time exploration. On large IoX trees this can hit the ~150 accessory limit quickly — then switch to `spoken` or `hybrid` with explicit includes.

### `mapping_mode`

**What it is for:** Controls *how* an exported IoX node is classified as a HomeKit accessory (light, switch, thermostat, etc.). It does not choose *which* nodes export; `export_mode` does that.

**How to use it:** Start with `common`. Switch to `broad` only if you need locks, blinds, standalone temp/humidity sensors, or more Plugins node-server devices. You can override a single device with `hap_type` in the typed table without changing the global mode.

Default: **`common`**.

#### `common`

Maps everyday home devices:

- Lights (including dimmers and many scenes)
- Switches / outlets
- Fans
- Thermostats
- Contact (door/window) and motion sensors

Unrecognized on/off nodes usually become a **switch**. Prefer this unless you need the extra types below.

#### `broad`

Everything in `common`, plus:

- Door locks
- Blinds / shades / window coverings
- Temperature-only and humidity sensors
- Additional Plugins node-server devices when the name/nodeDef looks like a sensor

More devices appear in Apple Home, but mis-classification is more likely (for example a oddly named node becoming a lock). Fix individual mistakes with a typed row `hap_type`.

### `hap_port`

**What it is for:** TCP port the HomeKit Accessory Protocol (HAP) server listens on. Apple Home / your phone reach the bridge at `advertise_ip`:`hap_port`.

**How to use it:** Leave `51826` unless that port is already in use on the eISY or blocked by a firewall. If you change it, ensure LAN clients can reach the new port, then **Refresh Devices** during an Advertise window (or after already paired).

### `hap_pin`

**What it is for:** The 8-digit HomeKit setup code shown as `123-45-678` (Apple Home “Add Accessory” numeric entry). Also embedded in the QR payload.

**How to use it:**

- Leave **empty** (recommended) — the plugin generates a code, stores it in `config/accessory.state`, and reuses it across restarts.
- Or set a fixed code such as `123-45-678` / `12345678` if you need a known PIN.

Changing the PIN after Apple Home has paired usually requires removing the bridge from Apple Home and pairing again.

### `bridge_name`

**What it is for:** Display name of the HomeKit **bridge** accessory in Apple Home (the parent that holds your exported devices).

**How to use it:** Set something recognizable (for example `Kitchen IoX` or `eISY Bridge`). Changing the name after pairing may show as a rename in Apple Home; if pairing breaks, remove and re-add the accessory during an Advertise window.

### `advertise_ip`

**What it is for:** The LAN IPv4 address published in mDNS so Apple devices know where to connect.

**How to use it:** Leave empty to use the eISY’s default interface. Set explicitly (for example `192.168.1.50`) when:

- The eISY has multiple NICs / VLANs and Apple Home is on a specific subnet
- Auto-detection picks the wrong interface (Wi‑Fi vs ethernet)

The phone and any Home hub must be able to reach this IP.

### `advertise_timeout`

**What it is for:** How long **Advertise** stays On after you enable it (via **SET_ADVERTISE** or the Plugins **Discover** button). While On, the bridge advertises for pairing; when the timer ends, Advertise turns Off.

**How to use it:** Default `5` minutes is enough for most pairings. Increase if you need more time (large homes, slow discovery). This value alone does not restart the HAP server when changed — it applies the next time Advertise is turned On.

**Behavior when the timer ends:**

- **Not yet paired** — HAP/mDNS stops (nothing left advertising).
- **Already paired** — Advertise goes Off, but the bridge keeps running so Apple Home / Siri continue to work.

### Typed table: Exported devices

**What it is for:** Per-device overrides on the Configuration page (Custom Typed parameters). Used mainly with `export_mode` = `hybrid` or `all`.

**How to use it:** Add a row per device. Identify the node with address (`2E AD 73 1`) or exact IoX name. Reload the full Configuration page after **Discover** / saves if rows do not appear immediately.

| Column | Description |
|--------|-------------|
| `node_address` | IoX node address or name |
| `action` | `include`, `exclude`, or `rename` (see below) |
| `homekit_name` | Optional display name in Apple Home |
| `hap_type` | Optional forced type: `light`, `switch`, `fan`, `thermostat`, `contact`, `motion`, `lock`, `blind` |

#### Actions

| Action | What it does |
|--------|----------------|
| `include` | Export this node even if it has no Spoken note. Used in **`hybrid`** to add devices beyond Spoken. In **`spoken`** mode typed rows are ignored for selection. In **`all`** mode every supported node is already exported, so `include` is unnecessary. |
| `exclude` | Never export this node. Works in **`hybrid`** (overrides Spoken) and **`all`**. Ignored in **`spoken`** mode (selection is Spoken-only). |
| `rename` | Keep the node’s normal export membership, but set its Apple Home name from `homekit_name`. The node must already be selected by Spoken / `include` / `all`. |

**`homekit_name` tip:** On an `include` row, `homekit_name` also sets the Apple Home display name when present. For Spoken-selected devices you want to keep exporting, use `rename` plus `homekit_name` instead of changing the Spoken note.

**`hap_type` tip:** Optional on any row. Forces the HomeKit accessory type when auto-mapping is wrong (for example treat a dimmer as `light`).

## Apple Home pairing

HomeKit discovery/pairing is **off by default**.

1. Set Spoken notes (or typed export rows) so devices will export; **Exported Device Count** should be greater than 0 after **Refresh Devices**.
2. On the controller node, set **Advertise** to **On** (`SET_ADVERTISE`), **or** click **Discover** in the Plugins UI (same action). This opens a window for `advertise_timeout` minutes (default 5).
3. Send **Show HomeKit Setup** (or open the **HomeKit pairing** Plugins Notice) for the setup code and scannable QR.
4. In the Apple Home app: **Add Accessory** → scan the QR, or enter the setup code.
5. When the Advertise window ends, **Advertise** returns to **Off**. If the bridge is **not** yet paired, HAP/mDNS stops. If it **is** paired, the bridge stays running so Apple Home / Siri keep working.

**Note:** HomeKit bridges support up to about **150** accessories. Use `hybrid` mode with explicit includes for large installations.

## IoX controller

| Driver | Meaning |
|--------|---------|
| `ST` | `Stopped` / `Running` / `Paired` |
| `GV0` | Exported device count |
| `GV1` | IoX connected |
| `GV2` | **Advertise** — HomeKit discovery/pairing window On/Off |
| `ERR` | Error code (see profile NLS) |

| Command | Action |
|---------|--------|
| `REFRESH` | Rescan IoX and (re)start the bridge only if Advertise is On or already paired |
| `SHOW_SETUP` | Publish HomeKit pairing Notice with QR + setup code (also logs ASCII QR) |
| `SET_ADVERTISE` | Turn **Advertise** On/Off (On starts a timed pairing window) |
| **Discover** (Plugins UI) | Same as setting **Advertise** On |

## Spoken property (spoken export mode)

In the IoX Admin Console or eisy-ui, open a device's **Notes** and set **Spoken**:

- `1` — use the device name in HomeKit
- Any other plain ASCII string — custom spoken name

For scenes, prefer setting Spoken on the scene controller you want to track (same caveat as Hue Emulator).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ERR` = IoX access not authorized | Enable unrestricted IoX access and restart |
| No devices exported | Check Spoken notes or switch to `hybrid`/`all` |
| Home app cannot find bridge | Set **Advertise** On, confirm it has not timed out, verify `hap_port` / `advertise_ip` |
| Devices changed IDs in HomeKit | Do not delete `config/bridge_state.json` or `config/accessory.state` |

## Related plugins

- **udi-plugin-hue-emu** — IoX → Hue API for Harmony/Alexa; similar Spoken selection logic.
