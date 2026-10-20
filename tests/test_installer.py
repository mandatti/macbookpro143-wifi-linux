import base64
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('wifi', Path(__file__).parents[1] / 'macbook_wifi.py')
wifi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wifi)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / 'private' / 'state.json'
        self.override = patch.object(wifi, 'STATE_FILE', self.state)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.addCleanup(self.temp.cleanup)

    def test_reinstall_then_uninstall_preserves_original_and_mode(self):
        existing = self.root / 'existing'
        absent = self.root / 'new'
        existing.write_bytes(b'original local config')
        existing.chmod(0o640)
        state = wifi.install_files({existing: b'first', absent: b'first new'}, None, {})
        state = wifi.install_files({existing: b'second', absent: b'second new'}, state, {})
        wifi.uninstall_files(state)
        self.assertEqual(existing.read_bytes(), b'original local config')
        self.assertEqual(existing.stat().st_mode & 0o777, 0o640)
        self.assertFalse(absent.exists())
        self.assertFalse(self.state.exists())

    def test_failure_mid_install_restores_previous_files_and_state(self):
        a, b = self.root / 'a', self.root / 'b'
        a.write_bytes(b'old-a')
        previous = wifi.install_files({a: b'installed-a', b: b'installed-b'}, None, {})
        original_state = self.state.read_bytes()
        actual_write = wifi.atomic_write
        def fail(path, data, mode=0o644):
            if path == b and data == b'update-b':
                raise OSError('simulated full disk')
            return actual_write(path, data, mode)
        with patch.object(wifi, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                wifi.install_files({a: b'update-a', b: b'update-b'}, previous, {})
        self.assertEqual(a.read_bytes(), b'installed-a')
        self.assertEqual(b.read_bytes(), b'installed-b')
        self.assertEqual(self.state.read_bytes(), original_state)

    def test_uninstall_refuses_local_edits_before_touching_other_files(self):
        a, b = self.root / 'a', self.root / 'b'
        state = wifi.install_files({a: b'ours-a', b: b'ours-b'}, None, {})
        b.write_bytes(b'user edit')
        with self.assertRaises(ValueError):
            wifi.uninstall_files(state)
        self.assertEqual(a.read_bytes(), b'ours-a')
        self.assertEqual(b.read_bytes(), b'user edit')
        self.assertTrue(self.state.exists())

    def test_symbolic_link_never_overwrites_destination(self):
        target, link = self.root / 'target', self.root / 'link'
        target.write_bytes(b'keep')
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            wifi.install_files({link: b'unsafe'}, None, {})
        self.assertEqual(target.read_bytes(), b'keep')

    def test_bad_source_digest_is_rejected(self):
        bad = self.root / 'wrong-nvram'
        bad.write_text('ccode=DE\n')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            wifi.source_data(bad)
        self.assertFalse(self.state.exists())

    def test_render_changes_only_country_revision_and_mac(self):
        source = 'ccode=00\nregrev=245\nmacaddr=xx:xx:xx:xx:xx:xx\nboardflags3=0x300\n'
        result = wifi.render_nvram(source, 'DE', '02:11:22:33:44:55').decode()
        self.assertIn('ccode=DE\nregrev=0\n', result)
        self.assertIn('boardflags3=0x300\n', result)
        self.assertNotIn('xx:', result)
        with self.assertRaises(ValueError):
            wifi.render_nvram(source + 'ccode=US\n', 'DE', '02:11:22:33:44:55')

    def test_generated_address_is_local_unicast_and_stable(self):
        with patch.object(wifi, 'read', return_value='00:90:4c:0d:f4:3e'):
            mac = wifi.choose_mac('wlan0', None)
        first = int(mac.split(':')[0], 16)
        self.assertEqual(first & 3, 2)
        self.assertTrue(wifi.usable_mac(mac))
        self.assertEqual(wifi.choose_mac('wlan0', {'mac': mac}), mac)
        self.assertFalse(wifi.usable_mac('ff:ff:ff:ff:ff:ff'))

    def test_country_rejects_world_and_non_iso_codes(self):
        with patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'read_text', return_value='# test\nDE Germany\nBR Brazil\nGB United Kingdom\n'):
            self.assertEqual(wifi.country_code('de'), 'DE')
            for value in ('00', 'UK', 'DE;reboot', '../DE'):
                with self.assertRaises(ValueError):
                    wifi.country_code(value)

    def test_wrong_model_rejected_before_pci_or_file_changes(self):
        with patch.object(wifi, 'read', side_effect=['MacBookPro15,1', 'Apple Inc.']):
            with self.assertRaisesRegex(ValueError, 'Supported model'):
                wifi.hardware()
        self.assertFalse(self.state.exists())

    def test_diagnostics_redact_network_identifiers(self):
        raw = 'Connected to aa:bb:cc:dd:ee:ff\n\tSSID: My private home WiFi\naddr 192.168.2.159/24\nssid Secret\nsignal: -44 dBm\n'
        cleaned = wifi.clean_output(raw)
        for private in ('aa:bb:cc:dd:ee:ff', 'My private home WiFi', '192.168.2.159', 'Secret'):
            self.assertNotIn(private, cleaned)
        self.assertIn('-44 dBm', cleaned)

    def test_state_path_injection_rejected(self):
        hw = {'model': wifi.MODEL, 'vendor': 'Apple Inc.', 'interface': 'wlan0'}
        state = {'model': wifi.MODEL, 'original': {'/etc/passwd': None}, 'installed': {'/etc/passwd': 'x'}}
        with self.assertRaises(ValueError):
            wifi.validate_state(state, hw)


if __name__ == '__main__':
    unittest.main()
