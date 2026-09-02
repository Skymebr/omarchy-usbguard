#!/usr/bin/env python3
import unittest

from backend import classify_device, sanitize_field, scan_sysfs_usb


class TestUSBGuardBackend(unittest.TestCase):

    def test_badusb_storage_hid(self):
        # 08: (Storage) and 03: (HID)
        res = classify_device("08:06:50 03:01:01", "Rubber Ducky", "1234:5678", "hotplug")
        self.assertTrue(res["is_badusb"])
        self.assertEqual(res["risk"], "critical")
        self.assertEqual(res["category"], "badusb")
        self.assertIn("BadUSB", res["type_label"])

    def test_badusb_storage_network(self):
        # 08: (Storage) and 02: (CDC Ethernet)
        res = classify_device("08:06:50 02:02:01", "Malicious Key", "aaaa:bbbb", "hotplug")
        self.assertTrue(res["is_badusb"])
        self.assertEqual(res["risk"], "critical")

    def test_keyboard_classification(self):
        res = classify_device("03:01:01", "Mechanical Keyboard", "1a2c:6004", "hotplug")
        self.assertFalse(res["is_badusb"])
        self.assertEqual(res["category"], "keyboard")
        self.assertEqual(res["icon"], "󰌌")

    def test_mouse_classification(self):
        res = classify_device("03:01:02", "Logitech Mouse", "046d:c077", "hotplug")
        self.assertFalse(res["is_badusb"])
        self.assertEqual(res["category"], "mouse")
        self.assertEqual(res["icon"], "󰍽")

    def test_mass_storage_classification(self):
        res = classify_device("08:06:50", "Kingston DataTraveler", "0951:1666", "hotplug")
        self.assertFalse(res["is_badusb"])
        self.assertEqual(res["category"], "storage")
        self.assertEqual(res["icon"], "󰕒")

    def test_webcam_classification(self):
        res = classify_device("0e:01:00 0e:02:00", "Integrated Camera", "04f2:b6d9", "hardwired")
        self.assertFalse(res["is_badusb"])
        self.assertEqual(res["category"], "camera")
        self.assertEqual(res["icon"], "󰄀")

    def test_bluetooth_classification(self):
        res = classify_device("e0:01:01", "MediaTek Bluetooth", "0489:e0cd", "hardwired")
        self.assertFalse(res["is_badusb"])
        self.assertEqual(res["category"], "bluetooth")
        self.assertEqual(res["icon"], "󰂯")

    def test_hub_classification(self):
        res = classify_device("09:00:00", "Root Hub", "1d6b:0002", "hardwired")
        self.assertTrue(res["is_hub"])
        self.assertEqual(res["category"], "hub")

    def test_sysfs_scan_structure(self):
        data = scan_sysfs_usb()
        self.assertIn("by_port", data)
        self.assertIn("by_vidpid", data)
        self.assertIsInstance(data["by_port"], dict)
        self.assertIsInstance(data["by_vidpid"], dict)

    def test_sanitize_field(self):
        self.assertEqual(sanitize_field("<b>Safe Name</b>"), "Safe Name")
        self.assertEqual(sanitize_field("<script>alert(1)</script>Device"), "alert(1)Device")
        self.assertEqual(sanitize_field("Device\x00\x1bName"), "Device Name")
        long_str = "A" * 200
        sanitized = sanitize_field(long_str, max_len=50)
        self.assertLessEqual(len(sanitized), 50)
        self.assertTrue(sanitized.endswith("…"))

if __name__ == "__main__":
    unittest.main()
