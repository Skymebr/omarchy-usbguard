#!/usr/bin/env python3
"""
Omarchy USBGuard High-Performance Backend Helper
Blazing fast hardware database resolution, BadUSB inspection,
unified device-to-rule linking, and clean JSON formatting for Quickshell.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict

SUBPROCESS_TIMEOUT = 2.5
MAX_DEVICES = 256
MAX_RULES = 512
MAX_STR_LEN = 96
MAX_ID_LEN = 32

def sanitize_field(text, max_len=MAX_STR_LEN):
    """
    Sanitizes untrusted hardware/user strings: removes control characters,
    strips HTML-like tags, collapses whitespace, and enforces hard length bounds.
    """
    if text is None:
        return ""
    s = str(text)
    # Remove control characters and non-printable bytes
    s = re.sub(r'[\x00-\x1f\x7f]', ' ', s)
    # Remove HTML tags to prevent RichText injection in QML
    s = re.sub(r'<[^>]*>', '', s)
    # Collapse multiple whitespaces
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) > max_len:
        s = s[:max_len - 1] + "…"
    return s

def scan_sysfs_usb():
    """
    Scans sysfs for connected USB device metadata with bounded iterations.
    Returns dictionaries indexed by port (e.g. '1-1.2') and by 'vid:pid'.
    """
    sys_by_port = {}
    sys_by_vidpid = {}

    paths = glob.glob("/sys/bus/usb/devices/*")[:MAX_DEVICES]
    for p in paths:
        port_name = sanitize_field(os.path.basename(p), 32)
        id_vendor_f = os.path.join(p, "idVendor")
        id_product_f = os.path.join(p, "idProduct")

        if os.path.isfile(id_vendor_f) and os.path.isfile(id_product_f):
            try:
                with open(id_vendor_f, "r", encoding="utf-8", errors="ignore") as f:
                    vid = f.read(16).strip().lower()
                with open(id_product_f, "r", encoding="utf-8", errors="ignore") as f:
                    pid = f.read(16).strip().lower()
            except (OSError, UnicodeDecodeError):
                continue

            if not re.match(r'^[0-9a-f]{4}$', vid) or not re.match(r'^[0-9a-f]{4}$', pid):
                continue

            mfg = ""
            prod = ""
            mfg_f = os.path.join(p, "manufacturer")
            prod_f = os.path.join(p, "product")

            if os.path.isfile(mfg_f):
                try:
                    with open(mfg_f, "r", encoding="utf-8", errors="ignore") as f:
                        mfg = sanitize_field(f.read(MAX_STR_LEN))
                except (OSError, UnicodeDecodeError):
                    pass
            if os.path.isfile(prod_f):
                try:
                    with open(prod_f, "r", encoding="utf-8", errors="ignore") as f:
                        prod = sanitize_field(f.read(MAX_STR_LEN))
                except (OSError, UnicodeDecodeError):
                    pass

            info = {
                "manufacturer": mfg,
                "product": prod,
                "vid_pid": f"{vid}:{pid}",
                "port": port_name
            }

            sys_by_port[port_name] = info
            vp = f"{vid}:{pid}"
            if vp not in sys_by_vidpid or (mfg or prod):
                sys_by_vidpid[vp] = info

    return {
        "by_port": sys_by_port,
        "by_vidpid": sys_by_vidpid
    }

def resolve_hardware_names_bulk(target_vid_pids):
    """
    Resolves USB vendor and product names from /usr/share/hwdata/usb.ids in bulk.
    """
    results = {}
    vendors = {}
    if not target_vid_pids:
        return results, vendors

    targets = {vp.lower() for vp in target_vid_pids if vp and vp != "----:----"}
    if not targets:
        return results, vendors

    target_vids = {vp.split(":")[0] for vp in targets if ":" in vp}
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
        except (OSError, UnicodeDecodeError):
            pass

    return results, vendors

def classify_device(ifaces, raw_name, vid_pid, connect_type, resolved_hw_name="", vendor_db_name="", sysfs_info=None):
    """
    Classifies a USB device strictly by interface descriptors.
    Detects BadUSB composite threats (Storage + HID, Storage + Network).
    """
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
    codes = (ifaces or "").replace("{", "").replace("}", "").split()

    for c in codes:
        c = c.lower()
        if c.startswith("08:"):
            has_storage = True
        elif c.startswith("03:01:01"):
            is_kbd = True
            has_hid = True
        elif c.startswith("03:01:02"):
            is_mouse = True
            has_hid = True
        elif c.startswith("03:"):
            has_hid = True
        elif c.startswith(("02:", "0a:")):
            has_net = True
        elif c.startswith("01:"):
            has_audio = True
        elif c.startswith(("0e:", "10:")):
            has_video = True
        elif c.startswith("e0:"):
            has_bluetooth = True
        elif c.startswith("09:"):
            has_hub = True

    mfg = (sysfs_info.get("manufacturer") if sysfs_info else "") or vendor_db_name
    prod = (sysfs_info.get("product") if sysfs_info else "") or raw_name or resolved_hw_name

    if resolved_hw_name and resolved_hw_name not in ("USB Device", "Mass Storage", "Wireless_Device"):
        display_name = sanitize_field(resolved_hw_name)
    elif mfg and prod and mfg.lower() not in prod.lower():
        display_name = sanitize_field(f"{mfg} {prod}")
    elif prod and prod not in ("USB Device", "Mass Storage", "Wireless_Device"):
        display_name = sanitize_field(prod.replace("_", " ").strip())
    elif mfg:
        display_name = sanitize_field(f"{mfg} USB Device")
    elif vid_pid and vid_pid != "----:----":
        display_name = sanitize_field(f"USB Device ({vid_pid})")
    else:
        display_name = "USB Peripheral"

    # BadUSB composite detection
    if has_storage and (has_hid or is_kbd):
        return {
            "icon": "󰕤",
            "type_label": "High-Risk BadUSB (Storage + HID)",
            "display_name": sanitize_field(f"⚠️ BadUSB: {display_name}"),
            "is_badusb": True,
            "is_hub": False,
            "risk": "critical",
            "category": "badusb"
        }

    if has_storage and has_net:
        return {
            "icon": "󰕤",
            "type_label": "High-Risk BadUSB (Storage + Net)",
            "display_name": sanitize_field(f"⚠️ BadUSB Net: {display_name}"),
            "is_badusb": True,
            "is_hub": False,
            "risk": "critical",
            "category": "badusb"
        }

    if is_kbd:
        return {
            "icon": "󰌌",
            "type_label": "USB Keyboard",
            "display_name": display_name,
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "keyboard"
        }

    if is_mouse:
        return {
            "icon": "󰍽",
            "type_label": "USB Mouse / Touchpad",
            "display_name": display_name,
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
            "is_badusb": False,
            "is_hub": False,
            "risk": "info",
            "category": "bluetooth"
        }

    if has_video or "user facing" in raw_lower or "webcam" in raw_lower or "camera" in raw_lower:
        return {
            "icon": "󰄀",
            "type_label": "Integrated Webcam" if connect_type == "hardwired" else "USB Camera",
            "display_name": display_name if "webcam" in display_name.lower() or "camera" in display_name.lower() else sanitize_field(f"{display_name} (Webcam)"),
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
            "is_badusb": False,
            "is_hub": True,
            "risk": "info",
            "category": "hub"
        }

    return {
        "icon": "󰕓",
        "type_label": "Internal Hardware" if connect_type == "hardwired" else "USB Peripheral",
        "display_name": display_name,
        "is_badusb": False,
        "is_hub": False,
        "risk": "info",
        "category": "other"
    }

def get_status_payload():
    """
    Fetches full status from usbguard daemon with bounded timeout.
    """
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

    dev_out = ""
    rules_out = ""
    daemon_active = False

    try:
        p_dev = subprocess.Popen(["usbguard", "list-devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p_rules = subprocess.Popen(["usbguard", "list-rules"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        dev_out, _ = p_dev.communicate(timeout=SUBPROCESS_TIMEOUT)
        rules_out, _ = p_rules.communicate(timeout=SUBPROCESS_TIMEOUT)
        daemon_active = (p_dev.returncode == 0)
    except subprocess.TimeoutExpired:
        try:
            p_dev.kill()
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            p_rules.kill()
        except (OSError, subprocess.SubprocessError):
            pass
        dev_out, rules_out = "", ""
        daemon_active = False
    except (OSError, subprocess.SubprocessError):
        daemon_active = False

    sysfs_data = scan_sysfs_usb()
    sysfs_ports = sysfs_data["by_port"]
    sysfs_vids = sysfs_data["by_vidpid"]

    all_vid_pids = set()
    raw_devices = []
    raw_rules = []

    if daemon_active and dev_out:
        for line in dev_out.splitlines():
            line = line.strip()
            if line and ":" in line:
                m_vid = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", line)
                if m_vid:
                    all_vid_pids.add(m_vid.group(1).lower())
                raw_devices.append(line)
                if len(raw_devices) >= MAX_DEVICES:
                    break

    if daemon_active and rules_out:
        for line in rules_out.splitlines():
            line = line.strip()
            if line:
                m_vid = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", line)
                if m_vid:
                    all_vid_pids.add(m_vid.group(1).lower())
                raw_rules.append(line)
                if len(raw_rules) >= MAX_RULES:
                    break

    hw_db, vendor_db = resolve_hardware_names_bulk(all_vid_pids)

    # 1. Parse rules first into defaultdict lists to prevent overwriting identical device rules
    rules = []
    rules_by_hash = defaultdict(list)
    rules_by_vidpid = defaultdict(list)

    for line in raw_rules:
        if ":" not in line:
            ct = ""
            m_ct = re.search(r'with-connect-type\s+"([^"]*)"', line)
            if m_ct:
                ct = sanitize_field(m_ct.group(1), 32)

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
        rule_id = sanitize_field(rule_id.strip(), 32)
        rest = rest.strip()

        parts = rest.split()
        target = sanitize_field(parts[0] if parts else "allow", 16)

        vid_pid = ""
        m_vid = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", rest)
        if m_vid:
            vid_pid = m_vid.group(1).lower()

        raw_name = ""
        m_name = re.search(r'name\s+"([^"]*)"', rest)
        if m_name:
            raw_name = sanitize_field(m_name.group(1))

        dev_hash = ""
        m_hash = re.search(r'hash\s+"([^"]*)"', rest)
        if m_hash:
            dev_hash = sanitize_field(m_hash.group(1), 64)

        connect_type = ""
        m_ct = re.search(r'with-connect-type\s+"([^"]*)"', rest)
        if m_ct:
            connect_type = sanitize_field(m_ct.group(1), 32)

        ifaces = ""
        m_if = re.search(r"with-interface\s+(\{[^}]+\}|[0-9a-fA-F:]+)", rest)
        if m_if:
            ifaces = m_if.group(1).replace("{", "").replace("}", "").strip()

        vid = vid_pid.split(":")[0] if ":" in vid_pid else ""
        hw_name = hw_db.get(vid_pid, "")
        vendor_name = vendor_db.get(vid, "")
        sys_info = sysfs_vids.get(vid_pid)

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

        rule_obj = {
            "id": rule_id,
            "target": target,
            "vid_pid": vid_pid,
            "name": sanitize_field(display_name),
            "hash": dev_hash,
            "icon": icon,
            "type_label": sanitize_field(cls["type_label"]),
            "subtitle": sanitize_field(subtitle),
            "connect_type": connect_type,
            "is_internal": connect_type == "hardwired",
            "is_hardwired": connect_type == "hardwired"
        }
        rules.append(rule_obj)

        if dev_hash and connect_type != "hardwired":
            rules_by_hash[dev_hash].append(rule_id)
        if vid_pid and connect_type != "hardwired":
            rules_by_vidpid[vid_pid].append(rule_id)

    # 2. Parse devices and link corresponding rule ID if trusted
    devices = []
    for line in raw_devices:
        dev_id, rest = line.split(":", 1)
        dev_id = sanitize_field(dev_id.strip(), 32)
        rest = rest.strip()

        parts = rest.split()
        target = sanitize_field(parts[0] if parts else "unknown", 16)

        vid_pid = ""
        m_vid = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", rest)
        if m_vid:
            vid_pid = m_vid.group(1).lower()

        serial = ""
        m_ser = re.search(r'serial\s+"([^"]*)"', rest)
        if m_ser:
            serial = sanitize_field(m_ser.group(1), 64)

        raw_name = ""
        m_name = re.search(r'name\s+"([^"]*)"', rest)
        if m_name:
            raw_name = sanitize_field(m_name.group(1))

        dev_hash = ""
        m_hash = re.search(r'hash\s+"([^"]*)"', rest)
        if m_hash:
            dev_hash = sanitize_field(m_hash.group(1), 64)

        via_port = ""
        m_port = re.search(r'via-port\s+"([^"]*)"', rest)
        if m_port:
            via_port = sanitize_field(m_port.group(1), 32)

        connect_type = ""
        m_ct = re.search(r'with-connect-type\s+"([^"]*)"', rest)
        if m_ct:
            connect_type = sanitize_field(m_ct.group(1), 32)

        ifaces = ""
        m_if = re.search(r"with-interface\s+(\{[^}]+\}|[0-9a-fA-F:]+)", rest)
        if m_if:
            ifaces = m_if.group(1).replace("{", "").replace("}", "").strip()

        vid = vid_pid.split(":")[0] if ":" in vid_pid else ""
        hw_name = hw_db.get(vid_pid, "")
        vendor_name = vendor_db.get(vid, "")
        sys_info = sysfs_ports.get(via_port) or sysfs_vids.get(vid_pid)

        cls = classify_device(ifaces, raw_name, vid_pid, connect_type, hw_name, vendor_name, sys_info)

        # Match permanent rule if present
        matched_rule_id = ""
        if connect_type != "hardwired":
            if dev_hash and dev_hash in rules_by_hash:
                matched_rule_id = rules_by_hash[dev_hash][0]
            elif vid_pid and vid_pid in rules_by_vidpid:
                matched_rule_id = rules_by_vidpid[vid_pid][0]

        devices.append({
            "id": dev_id,
            "target": target,
            "is_allowed": target == "allow",
            "is_blocked": target in ("block", "reject"),
            "is_reject": target == "reject",
            "is_trusted": bool(matched_rule_id),
            "rule_id": matched_rule_id,
            "vid_pid": vid_pid or "----:----",
            "serial": serial,
            "name": sanitize_field(cls["display_name"]),
            "raw_name": raw_name,
            "hash": dev_hash,
            "port": via_port,
            "connect_type": connect_type,
            "is_internal": connect_type == "hardwired",
            "is_hub": cls["is_hub"],
            "icon": cls["icon"],
            "type_label": sanitize_field(cls["type_label"]),
            "is_badusb": cls["is_badusb"],
            "risk": cls["risk"],
            "category": cls["category"]
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
        "devices": devices[:MAX_DEVICES],
        "rules": rules[:MAX_RULES]
    }

def untrust_and_block(dev_id):
    """
    Atomic operation: removes the exact permanent whitelist rule for a device AND blocks it immediately.
    Uses exact token matching to prevent accidental substring deletion.
    """
    dev_id_clean = re.sub(r'\D', '', str(dev_id))
    if not dev_id_clean:
        return

    dev_out = ""
    rules_out = ""
    try:
        p1 = subprocess.Popen(["usbguard", "list-devices"], stdout=subprocess.PIPE, text=True)
        dev_out, _ = p1.communicate(timeout=SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        p2 = subprocess.Popen(["usbguard", "list-rules"], stdout=subprocess.PIPE, text=True)
        rules_out, _ = p2.communicate(timeout=SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        pass

    dev_hash = ""
    dev_vid = ""
    for line in (dev_out or "").splitlines():
        if re.match(rf"^{re.escape(dev_id_clean)}\s*:", line):
            m_h = re.search(r'hash\s+"([^"]*)"', line)
            if m_h:
                dev_hash = m_h.group(1)
            m_v = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", line)
            if m_v:
                dev_vid = m_v.group(1).lower()
            break

    # Find matching rule using strict pattern
    if rules_out:
        for rline in rules_out.splitlines():
            if ":" in rline:
                rid, rrest = rline.split(":", 1)
                rid = rid.strip()
                if '"hardwired"' in rrest:
                    continue

                matched = False
                if dev_hash and re.search(r'(^|\s)hash\s+"' + re.escape(dev_hash) + r'"', rrest) or dev_vid and re.search(r'(^|\s)id\s+' + re.escape(dev_vid) + r'(\s|$)', rrest, re.IGNORECASE):
                    matched = True

                if matched and re.match(r'^\d+$', rid):
                    try:
                        subprocess.run(["usbguard", "remove-rule", rid], check=False, timeout=SUBPROCESS_TIMEOUT)
                    except (OSError, subprocess.SubprocessError):
                        pass

    # Block device
    try:
        subprocess.run(["usbguard", "block-device", dev_id_clean], check=False, timeout=SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        pass

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--status", "status"):
        payload = get_status_payload()
        print(json.dumps(payload, indent=2))
        return

    cmd = sys.argv[1]

    if cmd == "--classify":
        ifaces = sys.argv[2] if len(sys.argv) > 2 else ""
        raw_name = sys.argv[3] if len(sys.argv) > 3 else ""
        vid_pid = sys.argv[4] if len(sys.argv) > 4 else ""
        connect_type = sys.argv[5] if len(sys.argv) > 5 else ""

        hw_db, vendor_db = resolve_hardware_names_bulk([vid_pid] if vid_pid else [])
        vid = vid_pid.split(":")[0] if ":" in vid_pid else ""
        hw_name = hw_db.get(vid_pid.lower(), "")
        vendor_name = vendor_db.get(vid.lower(), "")

        res = classify_device(ifaces, raw_name, vid_pid, connect_type, hw_name, vendor_name)
        if "--json" in sys.argv:
            print(json.dumps(res))
        else:
            combo = "combo" if res["is_badusb"] else "single"
            print(f"{res['type_label']}|{res['icon']}|{res['risk']}|{1 if res['is_badusb'] else 0}|{combo}|{res['display_name']}")
        return

    if cmd == "--resolve" and len(sys.argv) >= 3:
        vid_pid = sys.argv[2].lower()
        raw = sys.argv[3] if len(sys.argv) > 3 else ""
        hw_db, _ = resolve_hardware_names_bulk([vid_pid])
        name = hw_db.get(vid_pid, "") or raw or f"USB Device ({vid_pid})"
        print(sanitize_field(name))
        return

    if cmd == "--allow" and len(sys.argv) >= 3:
        dev_id = re.sub(r'\D', '', sys.argv[2])
        if not dev_id:
            print(json.dumps({"error": "Invalid device ID"}), file=sys.stderr)
            sys.exit(1)
        permanent = "--permanent" in sys.argv or "-p" in sys.argv
        args = ["usbguard", "allow-device", dev_id]
        if permanent:
            args.append("-p")
        try:
            subprocess.run(args, check=False, timeout=SUBPROCESS_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            pass
        print(json.dumps({"success": True}))
        return

    if cmd == "--untrust" and len(sys.argv) >= 3:
        dev_id = re.sub(r'\D', '', sys.argv[2])
        if dev_id:
            untrust_and_block(dev_id)
        print(json.dumps({"success": True}))
        return

    if cmd == "--block" and len(sys.argv) >= 3:
        dev_id = re.sub(r'\D', '', sys.argv[2])
        if dev_id:
            try:
                subprocess.run(["usbguard", "block-device", dev_id], check=False, timeout=SUBPROCESS_TIMEOUT)
            except (OSError, subprocess.SubprocessError):
                pass
        print(json.dumps({"success": True}))
        return

    if cmd == "--reject" and len(sys.argv) >= 3:
        dev_id = re.sub(r'\D', '', sys.argv[2])
        if dev_id:
            try:
                subprocess.run(["usbguard", "reject-device", dev_id], check=False, timeout=SUBPROCESS_TIMEOUT)
            except (OSError, subprocess.SubprocessError):
                pass
        print(json.dumps({"success": True}))
        return

    if cmd == "--remove-rule" and len(sys.argv) >= 3:
        rule_id = re.sub(r'\D', '', sys.argv[2])
        if rule_id:
            try:
                subprocess.run(["usbguard", "remove-rule", rule_id], check=False, timeout=SUBPROCESS_TIMEOUT)
            except (OSError, subprocess.SubprocessError):
                pass
        print(json.dumps({"success": True}))
        return

    print(json.dumps({"error": f"Unknown command {cmd}"}), file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
