"""Shared constants for the IoX HomeKit exporter."""

VERSION = '1.0.0'

TYPED_EXPORT_DEVICES_KEY = 'export_devices'

EXPORT_MODE_SPOKEN = 'spoken'
EXPORT_MODE_HYBRID = 'hybrid'
EXPORT_MODE_ALL = 'all'
EXPORT_MODES = (EXPORT_MODE_SPOKEN, EXPORT_MODE_HYBRID, EXPORT_MODE_ALL)

MAPPING_MODE_COMMON = 'common'
MAPPING_MODE_BROAD = 'broad'
MAPPING_MODES = (MAPPING_MODE_COMMON, MAPPING_MODE_BROAD)

HAP_TYPE_LIGHT = 'light'
HAP_TYPE_SWITCH = 'switch'
HAP_TYPE_FAN = 'fan'
HAP_TYPE_THERMOSTAT = 'thermostat'
HAP_TYPE_CONTACT = 'contact'
HAP_TYPE_MOTION = 'motion'
HAP_TYPE_LOCK = 'lock'
HAP_TYPE_BLIND = 'blind'
HAP_TYPE_TEMP_SENSOR = 'temp_sensor'
HAP_TYPE_HUMIDITY_SENSOR = 'humidity_sensor'

MAX_BRIDGE_ACCESSORIES = 150

# Default Advertise window (minutes) before mDNS/HAP pairing stops when unpaired.
DEFAULT_ADVERTISE_TIMEOUT_MINUTES = 5

# IoX ERR driver (UOM 25)
ERR_OK = 0
ERR_BRIDGE_START = 1
ERR_ISY_UNAUTHORIZED = 2
ERR_ISY_CONNECT = 3
ERR_SCAN = 4
ERR_BRIDGE_STOP = 5
ERR_TOO_MANY_DEVICES = 6

DEFAULT_BRIDGE_PARAMS = {
    'export_mode': EXPORT_MODE_SPOKEN,
    'mapping_mode': MAPPING_MODE_COMMON,
    'hap_port': '51826',
    'hap_pin': '',
    'bridge_name': 'IoX Bridge',
    'advertise_ip': '',
    'advertise_timeout': str(DEFAULT_ADVERTISE_TIMEOUT_MINUTES),
}

BRIDGE_RESTART_KEYS = (
    'export_mode',
    'mapping_mode',
    'hap_port',
    'hap_pin',
    'bridge_name',
    'advertise_ip',
)
