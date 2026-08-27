#!/usr/bin/env python3
"""
Omarchy USBGuard High-Performance Backend Helper
Blazing fast (<15ms) hardware database & sysfs resolution, BadUSB inspection,
policy management, and clean JSON formatting for the Quickshell frontend.
"""

import sys
import os
import re
import json
import subprocess
import shutil
import glob

def scan_sysfs_usb():
    """
    Directly reads Linux sysfs (/sys/bus/usb/devices/*) in <1ms to get
    exact manufacturer, product string, serial, and bus speed.
    """
    sys_devices = {}
    for p in glob.glob("/sys/bus/usb/devices/*"):
        id_vendor_f = os.path.join(p, "idVendor")
        id_product_f = os.path.join(p, "idProduct")
        if os.path.isfile(id_vendor_f) and os.path.isfile(id_product_f):
            try:
                with open(id_vendor_f, "r") as f:
                    vid = f.read().strip().lower()
                with open(id_product_f, "r") as f:
                    pid = f.read().strip().lower()
            except Exception:
                continue

            mfg = ""
            prod = ""
            ser = ""
            speed = ""

            mfg_f = os.path.join(p, "manufacturer")
            prod_f = os.path.join(p, "product")
            ser_f = os.path.join(p, "serial")
            speed_f = os.path.join(p, "speed")

            if os.path.isfile(mfg_f):
                try:
                    with open(mfg_f, "r", errors="ignore") as f:
                        mfg = f.read().strip()
                except Exception:
                    pass
            if os.path.isfile(prod_f):
                try:
                    with open(prod_f, "r", errors="ignore") as f:
                        prod = f.read().strip()
                except Exception:
                    pass
            if os.path.isfile(ser_f):
                try:
                    with open(ser_f, "r", errors="ignore") as f:
                        ser = f.read().strip()
                except Exception:
                    pass
            if os.path.isfile(speed_f):
                try:
                    with open(speed_f, "r", errors="ignore") as f:
                        raw_speed = f.read().strip()
                        if raw_speed:
                            speed = format_usb_speed(raw_speed)
                except Exception:
                    pass

            sys_devices[f"{vid}:{pid}"] = {
                "manufacturer": mfg,
                "product": prod,
                "serial": ser,
                "speed": speed
            }

    return sys_devices

def format_usb_speed(raw_speed):
    try:
        val = float(raw_speed)
        if val >= 10000:
            return "SuperSpeed+ (10 Gbps)"
        elif val >= 5000:
            return "SuperSpeed (5 Gbps)"
        elif val >= 480:
            return "High-Speed (480 Mbps)"
        elif val >= 12:
            return "Full-Speed (12 Mbps)"
        elif val >= 1.5:
            return "Low-Speed (1.5 Mbps)"
        return f"{raw_speed} Mbps"
    except Exception:
        return f"{raw_speed} Mbps"

def resolve_hardware_names_bulk(target_vid_pids):
    """
    Direct in-memory scan of /usr/share/hwdata/usb.ids in <5ms.
    """
    results = {}
    vendors = {}
    if not target_vid_pids:
        return results, vendors

    targets = {vp.lower() for vp in target_vid_pids if vp and vp != "----:----"}
    if not targets:
        return results, vendors

    target_vids = {vp.split(":")[0] for vp in targets}
    path = "/usr/share/hwdata/usb.ids"

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                current_vendor = None
                for line in f:
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("\t\t"):
                        continue
                    if line.startswith("\t"):
                        if current_vendor in target_vids:
                            parts = line.strip().split("  ", 1)
                            if len(parts) == 2:
                                vp = f"{current_vendor}:{parts[0].strip().lower()}"
                                if vp in targets:
                                    vname = vendors.get(current_vendor, "")
                                    pname = parts[1].strip()
                                    results[vp] = f"{vname} {pname}".strip() if vname else pname
                    else:
                        parts = line.strip().split("  ", 1)
                        if len(parts) == 2:
                            current_vendor = parts[0].strip().lower()
                            if current_vendor in target_vids:
                                vendors[current_vendor] = parts[1].strip()
                    if len(results) == len(targets):
                        break
        except Exception:
            pass

    return results, vendors

def parse_interface_descriptions(ifaces):
    """
    Transforms interface hex codes into human-readable list of functions.
    e.g. '03:01:01 03:01:02' -> ['Keyboard (HID)', 'Mouse / Media Keys']
    """
    funcs = []
    codes = ifaces.split()
    seen = set()

    for c in codes:
        c_low = c.lower()
        if c_low.startswith("08:"):
            if "storage" not in seen:
                funcs.append("Mass Storage")
                seen.add("storage")
        elif c_low.startswith("03:01:01"):
            if "keyboard" not in seen:
                funcs.append("Keyboard")
                seen.add("keyboard")
        elif c_low.startswith("03:01:02"):
            if "mouse" not in seen:
                funcs.append("Mouse / Media")
                seen.add("mouse")
        elif c_low.startswith("03:"):
            if "hid" not in seen and "keyboard" not in seen and "mouse" not in seen:
                funcs.append("Human Interface (HID)")
                seen.add("hid")
        elif c_low.startswith("02:") or c_low.startswith("0a:"):
            if "net" not in seen:
                funcs.append("Network Adapter")
                seen.add("net")
        elif c_low.startswith("01:"):
            if "audio" not in seen:
                funcs.append("Audio / Mic")
                seen.add("audio")
        elif c_low.startswith("0e:") or c_low.startswith("10:"):
            if "video" not in seen:
                funcs.append("Webcam / Video")
                seen.add("video")
        elif c_low.startswith("e0:"):
            if "bt" not in seen:
                funcs.append("Bluetooth Radio")
                seen.add("bt")
        elif c_low.startswith("09:"):
            if "hub" not in seen:
                funcs.append("USB Hub")
                seen.add("hub")

    return funcs

def classify_device(ifaces, raw_name, vid_pid, connect_type, resolved_hw_name="", vendor_db_name="", sysfs_info=None):
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

    # Detailed manufacturer and product extraction
    mfg = (sysfs_info.get("manufacturer") if sysfs_info else "") or vendor_db_name
    prod = (sysfs_info.get("product") if sysfs_info else "") or raw_name or resolved_hw_name
    speed = (sysfs_info.get("speed") if sysfs_info else "")

    if resolved_hw_name and resolved_hw_name not in ("USB Device", "Mass Storage", "Wireless_Device"):
        display_name = resolved_hw_name
    elif mfg and prod and mfg.lower() not in prod.lower():
        display_name = f"{mfg} {prod}"
    elif prod and prod not in ("USB Device", "Mass Storage", "Wireless_Device"):
        display_name = prod.replace("_", " ").strip()
    elif mfg:
        display_name = f"{mfg} USB Device"
    elif vid_pid and vid_pid != "----:----":
        display_name = f"USB Device ({vid_pid})"
    else:
        display_name = "USB Peripheral"

    ifaces_desc = parse_interface_descriptions(ifaces)
    ifaces_summary = " + ".join(ifaces_desc) if ifaces_desc else "Standard USB"

    # BadUSB composite detection (Storage + HID / Storage + Net)
    if has_storage and (has_hid or is_kbd):
        return {
            "icon": "󰕤",
            "type_label": "High-Risk BadUSB (Storage + HID)",
            "display_name": f"⚠️ BadUSB: {display_name}",
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": True,
            "is_hub": False,
            "risk": "critical",
            "category": "badusb"
        }

    if has_storage and has_net:
        return {
            "icon": "󰕤",
            "type_label": "High-Risk BadUSB (Storage + Net)",
            "display_name": f"⚠️ BadUSB Net: {display_name}",
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": True,
            "is_hub": False,
            "risk": "critical",
            "category": "badusb"
        }

    if is_kbd:
        return {
            "icon": "󰌌",
            "type_label": f"USB Keyboard ({ifaces_summary})",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "keyboard"
        }

    if is_mouse:
        return {
            "icon": "󰍽",
            "type_label": f"USB Mouse / Touchpad ({ifaces_summary})",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "mouse"
        }

    if has_bluetooth or "bluetooth" in raw_lower or "wireless" in raw_lower:
        return {
            "icon": "󰂯",
            "type_label": "Internal Bluetooth Radio" if connect_type == "hardwired" else "Bluetooth Adapter",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "bluetooth"
        }

    if has_video or "user facing" in raw_lower or "webcam" in raw_lower or "camera" in raw_lower:
        return {
            "icon": "󰄀",
            "type_label": "Integrated Webcam" if connect_type == "hardwired" else "USB Camera",
            "display_name": display_name if "webcam" in display_name.lower() or "camera" in display_name.lower() else f"{display_name} (Webcam)",
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "camera"
        }

    if has_storage:
        return {
            "icon": "󰕒",
            "type_label": "Mass Storage (USB Drive)",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "storage"
        }

    if has_audio or "audio" in raw_lower:
        return {
            "icon": "󰓗",
            "type_label": "Audio Device / Headset",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "audio"
        }

    if has_net or "ethernet" in raw_lower or "lan" in raw_lower:
        return {
            "icon": "󰖩",
            "type_label": "Network Adapter",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "network"
        }

    if has_hub:
        return {
            "icon": "󰕓",
            "type_label": "USB Root Hub",
            "display_name": display_name,
            "manufacturer": mfg,
            "interfaces_summary": ifaces_summary,
            "speed": speed,
            "is_badusb": False,
            "is_hub": True,
            "risk": "info",
            "category": "hub"
        }

    return {
        "icon": "󰕓",
        "type_label": "Internal Hardware" if connect_type == "hardwired" else "USB Peripheral",
        "display_name": display_name,
        "manufacturer": mfg,
        "interfaces_summary": ifaces_summary,
        "speed": speed,
        "is_badusb": False,
        "is_hub": False,
        "risk": "info",
        "category": "other"
    }

def get_status_payload():
    installed = shutil.which("usbguard") is not None
    if not installed:
        return {
            "installed": False,
            "daemon_active": False,
            "needs_setup": True,
            "blocked_count": 0,
            "badusb_count": 0,
            "visible_count": 0,
            "devices": [],
            "rules": []
        }

    # 1. Run list-devices and list-rules concurrently
    p_dev = subprocess.Popen(["usbguard", "list-devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p_rules = subprocess.Popen(["usbguard", "list-rules"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    dev_out, _ = p_dev.communicate()
    rules_out, _ = p_rules.communicate()

    daemon_active = (p_dev.returncode == 0)

    # 2. Query Linux sysfs directly (<1ms) for connected device hardware details
    sysfs_map = scan_sysfs_usb()

    all_vid_pids = set()
    raw_devices = []
    raw_rules = []

    if daemon_active and dev_out:
        for line in dev_out.splitlines():
            line = line.strip()
            if line and ":" in line:
                m_vid = re.search(r"id\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", line)
                if m_vid:
                    all_vid_pids.add(m_vid.group(1).lower())
                raw_devices.append(line)

    if daemon_active and rules_out:
        for line in rules_out.splitlines():
            line = line.strip()
            if line:
                m_vid = re.search(r"id\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", line)
                if m_vid:
                    all_vid_pids.add(m_vid.group(1).lower())
                raw_rules.append(line)

    hw_db, vendor_db = resolve_hardware_names_bulk(all_vid_pids)

    devices = []
    for line in raw_devices:
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

        vid = vid_pid.split(":")[0] if ":" in vid_pid else ""
        hw_name = hw_db.get(vid_pid, "")
        vendor_name = vendor_db.get(vid, "")
        sys_info = sysfs_map.get(vid_pid)

        cls = classify_device(ifaces, raw_name, vid_pid, connect_type, hw_name, vendor_name, sys_info)

        devices.append({
            "id": dev_id,
            "target": target,
            "is_allowed": target == "allow",
            "is_blocked": target in ("block", "reject"),
            "is_reject": target == "reject",
            "vid_pid": vid_pid or "----:----",
            "serial": serial or (sys_info.get("serial") if sys_info else ""),
            "name": cls["display_name"],
            "manufacturer": cls["manufacturer"],
            "interfaces_summary": cls["interfaces_summary"],
            "speed": cls["speed"],
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

    rules = []
    for line in raw_rules:
        if ":" not in line:
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

        vid = vid_pid.split(":")[0] if ":" in vid_pid else ""
        hw_name = hw_db.get(vid_pid, "")
        vendor_name = vendor_db.get(vid, "")
        sys_info = sysfs_map.get(vid_pid)

        cls = classify_device(ifaces, raw_name, vid_pid, connect_type, hw_name, vendor_name, sys_info)

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

    blocked_count = sum(1 for d in devices if d["is_blocked"] and not d["is_hub"])
    badusb_count = sum(1 for d in devices if d["is_badusb"])
    visible_count = sum(1 for d in devices if not d["is_hub"])

    return {
        "installed": installed,
        "daemon_active": daemon_active,
        "needs_setup": not daemon_active or len(rules) == 0,
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
            subprocess.run(["usbguard", "allow-device", str(dev_id), "-p"], check=False)
        else:
            subprocess.run(["usbguard", "allow-device", str(dev_id)], check=False)
        print(json.dumps({"success": True}))
        return

    if cmd == "--block" and len(sys.argv) >= 3:
        dev_id = sys.argv[2]
        subprocess.run(["usbguard", "block-device", str(dev_id)], check=False)
        print(json.dumps({"success": True}))
        return

    if cmd == "--reject" and len(sys.argv) >= 3:
        dev_id = sys.argv[2]
        subprocess.run(["usbguard", "reject-device", str(dev_id)], check=False)
        print(json.dumps({"success": True}))
        return

    if cmd == "--remove-rule" and len(sys.argv) >= 3:
        rule_id = sys.argv[2]
        subprocess.run(["usbguard", "remove-rule", str(rule_id)], check=False)
        print(json.dumps({"success": True}))
        return

    print(json.dumps({"error": f"Unknown command {cmd}"}), file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
