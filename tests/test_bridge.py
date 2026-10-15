import tempfile
import unittest

from const import EXPORT_MODE_ALL, EXPORT_MODE_HYBRID, EXPORT_MODE_SPOKEN, MAPPING_MODE_COMMON
from homekit_bridge.brightness import hap_to_isy_brightness, isy_to_hap_brightness
from homekit_bridge.bridge_server import resolve_advertise_ip
from homekit_bridge.mdns_diag import format_debug_report, normalize_services, service_matches, summarize
from homekit_bridge.garage_door import (
    HAP_CURRENT_CLOSED,
    HAP_CURRENT_OPEN,
    HAP_CURRENT_OPENING,
    HAP_TARGET_CLOSED,
    HAP_TARGET_OPEN,
    iox_to_hap_current,
    iox_to_hap_target,
)
from homekit_bridge.isy_scanner import scan_export_devices
from homekit_bridge.mapping import classify_node, is_kpl_sub_button
from homekit_bridge.state_store import BridgeStateStore


class _EventStub:
    def subscribe(self, _cb):
        return None


class FakeNode:
    def __init__(
        self,
        address,
        name,
        *,
        spoken=None,
        dimmable=False,
        protocol=None,
        node_def_id='RelayLampSwitch_ADV',
        status=0,
    ):
        self.address = address
        self.name = name
        self.spoken = spoken
        self.dimmable = dimmable
        self.protocol = protocol
        self.node_def_id = node_def_id
        self.status = status
        self.status_events = _EventStub()

    def get_groups(self, responder=False):
        return []


class Node(FakeNode):
    """Alias with PyISY-compatible class name for scanner filters."""


class FakeNodes:
    def __init__(self, nodes):
        self._nodes = nodes

    def __iter__(self):
        for node in self._nodes:
            yield node.address, node

    def __getitem__(self, key):
        for node in self._nodes:
            if node.address == key:
                return node
        raise KeyError(key)

    def get_by_id(self, key):
        for node in self._nodes:
            if node.address == key or node.name == key:
                return node
        return None


class FakePyISY:
    def __init__(self, nodes):
        self.nodes = FakeNodes(nodes)


class AdvertiseIpTests(unittest.TestCase):
    def test_dict_from_get_network_interface(self):
        self.assertEqual(
            resolve_advertise_ip({'addr': '192.168.1.89', 'netmask': '255.255.255.0'}),
            '192.168.1.89',
        )

    def test_string_and_invalid(self):
        self.assertEqual(resolve_advertise_ip('10.0.0.5'), '10.0.0.5')
        self.assertEqual(resolve_advertise_ip(''), '')
        self.assertEqual(resolve_advertise_ip('not-an-ip'), '')
        self.assertEqual(resolve_advertise_ip({'addr': False}), '')


class BrightnessTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(isy_to_hap_brightness(255), 100)
        self.assertEqual(isy_to_hap_brightness(0), 0)
        self.assertEqual(hap_to_isy_brightness(100), 255)
        self.assertEqual(hap_to_isy_brightness(0), 0)

    def test_mid_values(self):
        self.assertEqual(isy_to_hap_brightness(128), 50)
        self.assertEqual(hap_to_isy_brightness(50), 128)


class MappingTests(unittest.TestCase):
    def test_kpl_sub_button(self):
        self.assertTrue(is_kpl_sub_button('2E AD 73 2'))
        self.assertFalse(is_kpl_sub_button('2E AD 73 1'))

    def test_classify_light_and_switch(self):
        dim = FakeNode('a1', 'Lamp', dimmable=True)
        sw = FakeNode('a2', 'Outlet', dimmable=False, node_def_id='OutletLincOnOff')
        self.assertEqual(classify_node(dim), 'light')
        self.assertEqual(classify_node(sw), 'switch')

    def test_classify_motion(self):
        motion = FakeNode('m1', 'Hall Motion', node_def_id='MotionSensor_ADV')
        self.assertEqual(classify_node(motion), 'motion')

    def test_classify_konnected_gdo(self):
        gdo = FakeNode('gdo6d27f50327', 'GDO-South', node_def_id='gdo')
        light = FakeNode('gdo6d27f503lt', 'Garage Light', node_def_id='gdolt')
        named = FakeNode('n001_xyz', 'Main Garage Door', node_def_id='RelayLampSwitch_ADV')
        plain = FakeNode('11 22 33 1', 'Garage', node_def_id='OutletLincOnOff')
        self.assertEqual(classify_node(gdo), 'garage')
        self.assertEqual(classify_node(light), 'light')  # gdolt / "Garage Light"
        self.assertEqual(classify_node(named), 'garage')
        self.assertEqual(classify_node(plain), 'switch')  # plain "Garage" is not a GDO

    def test_forced_hap_type_garage(self):
        node = FakeNode('x1', 'Mystery', node_def_id='RelayLampSwitch_ADV')
        self.assertEqual(classify_node(node, forced_hap_type='garage'), 'garage')


class GarageDoorMappingTests(unittest.TestCase):
    def test_iox_to_hap_current(self):
        self.assertEqual(iox_to_hap_current(0), HAP_CURRENT_CLOSED)
        self.assertEqual(iox_to_hap_current(1), HAP_CURRENT_OPEN)
        self.assertEqual(iox_to_hap_current(4), HAP_CURRENT_OPENING)

    def test_iox_to_hap_target(self):
        self.assertEqual(iox_to_hap_target(1), HAP_TARGET_OPEN)
        self.assertEqual(iox_to_hap_target(4), HAP_TARGET_OPEN)
        self.assertEqual(iox_to_hap_target(0), HAP_TARGET_CLOSED)
        self.assertEqual(iox_to_hap_target(3), HAP_TARGET_CLOSED)


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(delete=False)
        self._tmp.close()
        self.store = BridgeStateStore(self._tmp.name)

    def test_spoken_mode(self):
        nodes = [
            Node('11 22 33 1', 'Kitchen', spoken='Kitchen Light'),
            Node('11 22 33 2', 'Garage'),
        ]
        devices = scan_export_devices(
            FakePyISY(nodes),
            EXPORT_MODE_SPOKEN,
            [],
            MAPPING_MODE_COMMON,
            self.store,
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].display_name, 'Kitchen Light')

    def test_hybrid_exclude_wins(self):
        nodes = [Node('11 22 33 1', 'Kitchen', spoken='Kitchen Light')]
        rows = [{'node_address': '11 22 33 1', 'action': 'exclude'}]
        devices = scan_export_devices(
            FakePyISY(nodes),
            EXPORT_MODE_HYBRID,
            rows,
            MAPPING_MODE_COMMON,
            self.store,
        )
        self.assertEqual(devices, [])

    def test_all_mode_include_supported(self):
        nodes = [
            Node('11 22 33 1', 'Kitchen', dimmable=True),
            Node('11 22 33 2', 'Unknown', node_def_id='UnsupportedThing'),
        ]
        devices = scan_export_devices(
            FakePyISY(nodes),
            EXPORT_MODE_ALL,
            [],
            MAPPING_MODE_COMMON,
            self.store,
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].hap_type, 'light')

    def test_typed_include_adds_non_spoken(self):
        nodes = [Node('11 22 33 1', 'Garage')]
        rows = [{'node_address': 'Garage', 'action': 'include', 'homekit_name': 'Garage Switch'}]
        devices = scan_export_devices(
            FakePyISY(nodes),
            EXPORT_MODE_HYBRID,
            rows,
            MAPPING_MODE_COMMON,
            self.store,
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].display_name, 'Garage Switch')

    def test_stable_aid(self):
        nodes = [Node('11 22 33 1', 'Kitchen', spoken='1')]
        pyisy = FakePyISY(nodes)
        first = scan_export_devices(pyisy, EXPORT_MODE_SPOKEN, [], MAPPING_MODE_COMMON, self.store)
        second = scan_export_devices(pyisy, EXPORT_MODE_SPOKEN, [], MAPPING_MODE_COMMON, self.store)
        self.assertEqual(first[0].aid, second[0].aid)


class MdnsDiagTests(unittest.TestCase):
    def test_list_and_single_dict(self):
        listed = normalize_services([
            {'name': 'IoX Bridge', 'host': 'eisy.local', 'port': '51826', 'addresses': ['192.168.1.89']},
            {'name': 'Other', 'port': 51827, 'referer': {'address': '10.0.0.8'}},
        ])
        self.assertEqual(len(listed), 2)
        self.assertEqual(listed[0].port, 51826)
        self.assertEqual(listed[0].addresses, ('192.168.1.89',))
        self.assertEqual(listed[1].addresses, ('10.0.0.8',))

        single = normalize_services({'name': 'IoX Bridge', 'port': 51826})
        self.assertEqual(len(single), 1)
        self.assertEqual(single[0].name, 'IoX Bridge')

    def test_services_wrapper_and_fqdn_name(self):
        wrapped = normalize_services({
            'services': [{'fqdn': 'Kitchen._hap._tcp.local.', 'port': 51826, 'host': 'eisy.local.'}],
        })
        self.assertEqual(wrapped[0].name, 'Kitchen')
        self.assertEqual(wrapped[0].host, 'eisy.local')

    def test_empty_and_none(self):
        self.assertEqual(normalize_services([]), [])
        self.assertEqual(normalize_services(None), [])
        summary = summarize([], 'IoX Bridge', 51826)
        self.assertFalse(summary.found)
        self.assertEqual(summary.count, 0)
        self.assertIn('No HomeKit bridges were seen', summary.log)
        self.assertIn('polyglot', summary.notice_html)

    def test_match_name_and_port(self):
        services = normalize_services([
            {'name': 'iox bridge', 'host': 'eisy.local', 'port': 51826, 'addresses': ['192.168.1.89']},
        ])
        self.assertTrue(service_matches(services[0], 'IoX Bridge', 51826))
        summary = summarize(services, 'IoX Bridge', 51826)
        self.assertTrue(summary.found)
        self.assertIn('is visible', summary.log)
        self.assertIn('192.168.1.89', summary.log)

        missed = summarize(services, 'IoX Bridge', 51827)
        self.assertFalse(missed.found)
        self.assertIn('was not seen', missed.log)
        self.assertIn('polyglot', missed.log)

    def test_pg3_mdns_wrapper_and_hap_suffix(self):
        services = normalize_services({
            'command': 'bonjour',
            'mdns': [
                {'name': 'Office Hallway', 'host': 'ecobee.local', 'port': 35931, 'addresses': ['192.168.1.175']},
                {
                    'name': 'IoX Bridge 5E6BDE',
                    'host': 'eisy.local',
                    'port': 51826,
                    'addresses': ['192.168.1.89'],
                    'referer': {'address': '192.168.1.89', 'port': 5353},
                },
            ],
        })
        self.assertEqual([service.name for service in services], ['Office Hallway', 'IoX Bridge 5E6BDE'])
        self.assertEqual(services[1].port, 51826)
        summary = summarize(services, 'IoX Bridge', 51826)
        self.assertTrue(summary.found)
        self.assertIn('is visible', summary.log)
        self.assertIn('Office Hallway', summary.log)
        report = format_debug_report(
            services, 'IoX Bridge', 51826, uid='349', payload_keys=('command', 'mdns'),
        )
        self.assertIn('expect \'IoX Bridge\' port 51826 uid 349 reply_keys command,mdns', report)
        self.assertIn('MATCH: \'IoX Bridge 5E6BDE\' eisy.local:51826 [192.168.1.89]', report)
        self.assertIn('other: \'Office Hallway\'', report)


if __name__ == '__main__':
    unittest.main()
