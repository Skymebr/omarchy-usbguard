#!/usr/bin/env python3
"""
Omarchy USBGuard Backend Helper
Provides high-speed hardware database name resolution, BadUSB inspection,
policy management, and clean JSON formatting for the Quickshell frontend.
"""

import sys
import os
import re
import json
import subprocess
import shutil

def run_cmd(cmd, check=False):
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)
        return res.stdout.strip(), res.returncode
    except Exception:
        return "", 1

def is_daemon_active():
    out, code = run_cmd(["systemctl", "is-active", "usbguard.service"])
    return out == "active"

def is_installed():
    return shutil.which("usbguard") is not None

def resolve_hardware_name(vid_pid, raw_name=""):
    """
    Resolves official Linux hardware database name via lsusb with fallback to firmware strings.
    """
    if vid_pid and vid_pid != "----:----":
        out, code = run_cmd(["lsusb", "-d", vid_pid])
        if code == 0 and out:
            # Format: 'Bus 001 Device 002: ID 04ca:3802 Lite-On Technology Corp. MediaTek Bluetooth MT7921'
            m = re.search(r"ID [0-9a-fA-F:]+\s+(.+)$", out)
            if m:
                resolved = m.group(1).strip()
                if resolved and resolved not in ("USB Device", "Mass Storage", "Wireless_Device"):
                    return resolved

    if raw_name and raw_name not in ("USB Device", "Mass Storage", "Wireless_Device"):
        return raw_name.replace("_", " ").strip()

    if vid_pid and vid_pid != "----:----":
        return f"USB Device ({vid_pid})"

    return "USB Peripheral"

def classify_device(ifaces, raw_name, vid_pid, connect_type):
    has_hid = False
    has_storage = False
    has_net = False
    has_audio = False
    has_video = False
    has_bluetooth = False
    has_hub = False
    is_kbd = False
    is_mouse = False

    raw_lower = (raw_name or "").lower()
    codes = ifaces.split()

    for c in codes:
        c = c.lower()
        if c.startswith("08:"):
            has_storage = True
        elif c.startswith("03:01:01"):
            is_kbd = True
        elif c.startswith("03:01:02"):
            is_mouse = True
        elif c.startswith("03:"):
            has_hid = True
        elif c.startswith("02:") or c.startswith("0a:"):
            has_net = True
        elif c.startswith("01:"):
            has_audio = True
        elif c.startswith("0e:") or c.startswith("10:"):
            has_video = True
        elif c.startswith("e0:"):
            has_bluetooth = True
        elif c.startswith("09:"):
            has_hub = True

    resolved_name = resolve_hardware_name(vid_pid, raw_name)

    # BadUSB composite detection (Storage + HID / Storage + Net)
    if has_storage and (has_hid or is_kbd):
        return {
            "icon": "󰕤",
            "type_label": "High-Risk BadUSB (Storage + HID)",
            "display_name": f"⚠️ BadUSB Combo: {resolved_name}",
            "is_badusb": True,
            "is_hub": False,
            "risk": "critical",
            "category": "badusb"
        }

    if has_storage and has_net:
        return {
            "icon": "󰕤",
            "type_label": "High-Risk BadUSB (Storage + Net)",
            "display_name": f"⚠️ BadUSB Network: {resolved_name}",
            "is_badusb": True,
            "is_hub": False,
            "risk": "critical",
            "category": "badusb"
        }

    if is_kbd:
        return {
            "icon": "󰌌",
            "type_label": "USB Keyboard",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "keyboard"
        }

    if is_mouse:
        return {
            "icon": "󰍽",
            "type_label": "USB Mouse / Touchpad",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "mouse"
        }

    if has_bluetooth or "bluetooth" in raw_lower or "wireless" in raw_lower:
        return {
            "icon": "󰂯",
            "type_label": "Internal Bluetooth Radio" if connect_type == "hardwired" else "Bluetooth Adapter",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "bluetooth"
        }

    if has_video or "user facing" in raw_lower or "webcam" in raw_lower or "camera" in raw_lower:
        return {
            "icon": "󰄀",
            "type_label": "Integrated Webcam" if connect_type == "hardwired" else "USB Camera",
            "display_name": resolved_name if "webcam" in raw_lower or "camera" in raw_lower else f"{resolved_name} (Webcam)",
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "camera"
        }

    if has_storage:
        return {
            "icon": "󰕒",
            "type_label": "Mass Storage (USB Drive)",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "storage"
        }

    if has_audio or "audio" in raw_lower:
        return {
            "icon": "󰓗",
            "type_label": "Audio Device / Headset",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "audio"
        }

    if has_net or "ethernet" in raw_lower or "lan" in raw_lower:
        return {
            "icon": "󰖩",
            "type_label": "Network Adapter",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "network"
        }

    if has_hub:
        return {
            "icon": "󰕓",
            "type_label": "USB Root Hub",
            "display_name": resolved_name,
            "is_badusb": False,
            "is_hub": True,
            "risk": "info",
            "category": "hub"
        }

    return {
        "icon": "󰕓",
        "type_label": "Internal Hardware" if connect_type == "hardwired" else "USB Peripheral",
        "display_name": resolved_name,
        "is_badusb": False,
        "is_hub": False,
        "risk": "info",
        "category": "other"
    }

def get_devices():
    out, code = run_cmd(["usbguard", "list-devices"])
    if code != 0 or not out:
        return []

    devices = []
    for line in out.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue

        dev_id, rest = line.split(":", 1)
        dev_id = dev_id.strip()
        rest = rest.strip()

        parts = rest.split()
        target = parts[0] if parts else "unknown"

        vid_pid = ""
        m_vid = re.search(r"id\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", rest)
        if m_vid:
            vid_pid = m_vid.group(1).lower()

        serial = ""
        m_ser = re.search(r'serial\s+"([^"]*)"', rest)
        if m_ser:
            serial = m_ser.group(1)

        raw_name = ""
        m_name = re.search(r'name\s+"([^"]*)"', rest)
        if m_name:
            raw_name = m_name.group(1)

        dev_hash = ""
        m_hash = re.search(r'hash\s+"([^"]*)"', rest)
        if m_hash:
            dev_hash = m_hash.group(1)

        via_port = ""
        m_port = re.search(r'via-port\s+"([^"]*)"', rest)
        if m_port:
            via_port = m_port.group(1)

        connect_type = ""
        m_ct = re.search(r'with-connect-type\s+"([^"]*)"', rest)
        if m_ct:
            connect_type = m_ct.group(1)

        ifaces = ""
        m_if = re.search(r"with-interface\s+(\{[^}]+\}|[0-9a-fA-F:]+)", rest)
        if m_if:
            ifaces = m_if.group(1).replace("{", "").replace("}", "").strip()

        cls = classify_device(ifaces, raw_name, vid_pid, connect_type)

        devices.append({
            "id": dev_id,
            "target": target,
            "is_allowed": target == "allow",
            "is_blocked": target in ("block", "reject"),
            "is_reject": target == "reject",
            "vid_pid": vid_pid or "----:----",
            "serial": serial,
            "name": cls["display_name"],
            "raw_name": raw_name,
            "hash": dev_hash,
            "port": via_port,
            "connect_type": connect_type,
            "is_internal": connect_type == "hardwired",
            "is_hub": cls["is_hub"],
            "icon": cls["icon"],
            "type_label": cls["type_label"],
            "is_badusb": cls["is_badusb"],
            "risk": cls["risk"],
            "category": cls["category"]
        })

    return devices

def get_rules():
    out, code = run_cmd(["usbguard", "list-rules"])
    if code != 0 or not out:
        return []

    rules = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue

        if ":" not in line:
            # Top-level fallback rule like 'allow with-connect-type "hardwired"'
            ct = ""
            m_ct = re.search(r'with-connect-type\s+"([^"]*)"', line)
            if m_ct:
                ct = m_ct.group(1)

            rules.append({
                "id": "",
                "target": "allow" if line.startswith("allow") else "block",
                "name": "Hardwired Safety Baseline",
                "vid_pid": "",
                "hash": "",
                "icon": "󰕥",
                "type_label": "Baseline Policy",
                "subtitle": "Anti-lockout protection for internal hardware",
                "connect_type": ct,
                "is_internal": ct == "hardwired",
                "is_hardwired": True
            })
            continue

        rule_id, rest = line.split(":", 1)
        rule_id = rule_id.strip()
        rest = rest.strip()

        parts = rest.split()
        target = parts[0] if parts else "allow"

        vid_pid = ""
        m_vid = re.search(r"id\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", rest)
        if m_vid:
            vid_pid = m_vid.group(1).lower()

        raw_name = ""
        m_name = re.search(r'name\s+"([^"]*)"', rest)
        if m_name:
            raw_name = m_name.group(1)

        dev_hash = ""
        m_hash = re.search(r'hash\s+"([^"]*)"', rest)
        if m_hash:
            dev_hash = m_hash.group(1)

        connect_type = ""
        m_ct = re.search(r'with-connect-type\s+"([^"]*)"', rest)
        if m_ct:
            connect_type = m_ct.group(1)

        ifaces = ""
        m_if = re.search(r"with-interface\s+(\{[^}]+\}|[0-9a-fA-F:]+)", rest)
        if m_if:
            ifaces = m_if.group(1).replace("{", "").replace("}", "").strip()

        cls = classify_device(ifaces, raw_name, vid_pid, connect_type)

        if not vid_pid and connect_type == "hardwired":
            display_name = "Hardwired Safety Baseline"
            subtitle = "Anti-lockout protection for internal hardware"
            icon = "󰕥"
        else:
            display_name = cls["display_name"] or f"Whitelist Rule #{rule_id}"
            subtitle = "Internal Hardware Baseline" if connect_type == "hardwired" else "Permanent Whitelist"
            if vid_pid:
                subtitle += f" · {vid_pid}"
            icon = cls["icon"] if connect_type != "hardwired" else "󰕥"

        rules.append({
            "id": rule_id,
            "target": target,
            "vid_pid": vid_pid,
            "name": display_name,
            "hash": dev_hash,
            "icon": icon,
            "type_label": cls["type_label"],
            "subtitle": subtitle,
            "connect_type": connect_type,
            "is_internal": connect_type == "hardwired",
            "is_hardwired": connect_type == "hardwired"
        })

    return rules

def get_status_payload():
    daemon_act = is_daemon_active()
    installed = is_installed()
    devices = get_devices() if daemon_act else []
    rules = get_rules() if daemon_act else []

    blocked_count = sum(1 for d in devices if d["is_blocked"] and not d["is_hub"])
    badusb_count = sum(1 for d in devices if d["is_badusb"])
    visible_count = sum(1 for d in devices if not d["is_hub"])

    return {
        "installed": installed,
        "daemon_active": daemon_act,
        "needs_setup": not daemon_act or len(rules) == 0,
        "blocked_count": blocked_count,
        "badusb_count": badusb_count,
        "visible_count": visible_count,
        "devices": devices,
        "rules": rules
    }

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--status", "status"):
        print(json.dumps(get_status_payload(), indent=2))
        return

    cmd = sys.argv[1]

    if cmd == "--allow" and len(sys.argv) >= 3:
        dev_id = sys.argv[2]
        permanent = "--permanent" in sys.argv or "-p" in sys.argv
        if permanent:
            run_cmd(["usbguard", "allow-device", str(dev_id), "-p"])
        else:
            run_cmd(["usbguard", "allow-device", str(dev_id)])
        print(json.dumps({"success": True}))
        return

    if cmd == "--block" and len(sys.argv) >= 3:
        dev_id = sys.argv[2]
        run_cmd(["usbguard", "block-device", str(dev_id)])
        print(json.dumps({"success": True}))
        return

    if cmd == "--reject" and len(sys.argv) >= 3:
        dev_id = sys.argv[2]
        run_cmd(["usbguard", "reject-device", str(dev_id)])
        print(json.dumps({"success": True}))
        return

    if cmd == "--remove-rule" and len(sys.argv) >= 3:
        rule_id = sys.argv[2]
        run_cmd(["usbguard", "remove-rule", str(rule_id)])
        print(json.dumps({"success": True}))
        return

    print(json.dumps({"error": f"Unknown command {cmd}"}), file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
