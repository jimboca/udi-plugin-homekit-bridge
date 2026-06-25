import tempfile
import unittest

from const import EXPORT_MODE_ALL, EXPORT_MODE_HYBRID, EXPORT_MODE_SPOKEN, MAPPING_MODE_COMMON
from homekit_bridge.brightness import hap_to_isy_brightness, isy_to_hap_brightness
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


if __name__ == '__main__':
    unittest.main()
