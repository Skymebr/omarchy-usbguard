# Omarchy USBGuard Hardware Protection

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Omarchy / Arch Linux](https://img.shields.io/badge/Platform-Omarchy%20%2F%20Arch%20Linux-1793D1.svg)](https://omarchy.org)
[![Security: Kernel Level](https://img.shields.io/badge/Security-Kernel--Level-critical.svg)](https://usbguard.github.io/)
[![Architecture: Event--Driven](https://img.shields.io/badge/Architecture-Event--Driven-success.svg)](https://github.com/Skymebr/omarchy-usbguard)

A zero-friction, kernel-level USB device authorization and BadUSB mitigation suite for the **[Omarchy](https://omarchy.org)** Linux environment.

This project bridges **USBGuard** hardware authorization with the native **Quickshell / Omarchy Shell** desktop layer, providing block-by-default physical port security without interrupting standard developer workflows.

---

## Threat Model and Protection Scope

Linux systems by default automatically probe, enumerate, and bind kernel drivers to any USB device connected to a physical port. This creates distinct attack surfaces that `omarchy-usbguard` actively mitigates:

1. **BadUSB / Keystroke Injection Attacks (HID Spoofing):**
   Malicious microcontrollers (e.g., Rubber Ducky, MalDuino) disguised as standard mass storage drives or charging cables that register as high-speed keyboards to execute arbitrary shell commands.
2. **Rogue Network Interfaces:**
   Composite USB devices that advertise CDC/Ethernet or RNDIS interfaces to hijack local network routes and perform DHCP/DNS spoofing.
3. **Firmware Descriptor Exploits:**
   Malicious USB descriptors designed to trigger kernel heap/buffer overflows in legacy USB class drivers prior to user login.

---

## Architecture and Execution Flow

```
[ Physical USB Connection ]
            │
            ▼
[ Linux Kernel USB Core ] ─── (authorized = 0)
            │
            ▼
[ usbguard-daemon (IPC) ]
            │
            ▼ (via native -e event hook)
[ omarchy-usbguard-event ]
            │
    ├── 1. Interface Class Inspection (Storage 08h, HID 03h, Net 02h)
    ├── 2. BadUSB Composite Detection (Storage + HID combo inspection)
    ├── 3. Attacker String Sanitization (C0 strip, dash removal, length cap)
    ├── 4. Hardware Name Resolution (lsusb / hwdata lookup)
    └── 5. Dynamic Hash Replace ID Generation (SHA-256 slice)
            │
            ▼
[ Quickshell Desktop Notification (omarchy-notification-send) ]
            │
            ├── Right-Click: Dismiss (Keep blocked)
            └── Left-Click: Open Selection Modal (omarchy-menu-select)
                     │
                     ├── Allow for this session only (usbguard allow-device <id>)
                     ├── Trust permanently (usbguard allow-device <id> -p)
                     ├── Reject device (usbguard reject-device <id>)
                     └── Keep blocked (usbguard block-device <id>)
```

---

## Key Technical Implementations

### 1. Interface-Driven Classification (Anti-Spoofing)
Device categorization is performed strictly via 2-digit hexadecimal USB interface class codes (`08:` for Mass Storage, `03:01:01` for Boot Keyboard, `03:01:02` for Boot Mouse, `02:`/`0a:` for CDC Network, `01:` for Audio, `0e:`/`10:` for Video, `e0:` for Wireless/Bluetooth). Firmware-provided device strings (`iProduct`) are treated as untrusted and never used for security classification.

### 2. BadUSB Composite Inspection
If a single physical device descriptor advertises both Mass Storage (`08:`) and Human Interface Device (`03:`) interfaces, the event processor flags it as a high-risk BadUSB candidate, escalating notification urgency and prompting the user with an explicit security warning.

### 3. Native Event Hook (`usbguard watch -e`)
Eliminates brittle multiline stdout terminal scraping. The watcher runs `usbguard watch -w -e omarchy-usbguard-event`, receiving structured environment variables (`USBGUARD_DEVICE_ID`, `USBGUARD_DEVICE_EVENT`, `USBGUARD_DEVICE_TARGET`, `USBGUARD_DEVICE_RULE`) directly from the IPC bus.

### 4. Input Sanitization
Firmware strings (`iProduct`, `iSerial`) are sanitized before being passed to desktop notification APIs:
* Strips ASCII control characters (`\x00-\x1f\x7f`).
* Collapses sequential whitespace.
* Removes leading hyphens to prevent CLI argument injection (e.g. `--exec`).
* Enforces bounded string length limits.

### 5. Hardware Hash Validation and Dynamic Notification IDs
* **ID Recycling Protection:** `omarchy-usbguard-allow` validates the target device ID and its SHA-256 descriptor hash against the live daemon device table before applying allow/reject commands.
* **Notification Collision Prevention:** Generates unique notification replace IDs derived from the hardware descriptor hash, ensuring concurrent USB insertions do not overwrite one another.

### 6. Anti-Lockout Baseline Setup
* Automatically injects `allow with-connect-type "hardwired"` at the top of the ruleset to ensure internal webcams, onboard Bluetooth radios, and fingerprint readers are never locked out.
* Configures `PresentDevicePolicy=keep` in `/etc/usbguard/usbguard-daemon.conf` to prevent active hardware drops during daemon restarts.

---

## Installation

### Method 1: Native Omarchy Shell Plugin (Recommended)

Install and enable the status bar widget and popup panel directly via the Omarchy CLI:

```bash
omarchy plugin add https://github.com/Skymebr/omarchy-usbguard.git --enable --yes
```

Then run the one-time hardware baseline setup wizard:
```bash
omarchy-setup-security-usbguard
```

### Method 2: Manual Clone & Setup

Clone the repository and run the setup wizard:

```bash
git clone https://github.com/Skymebr/omarchy-usbguard.git
cd omarchy-usbguard
./omarchy-setup-security-usbguard
```

### Installation Flags

| Flag | Description |
| :--- | :--- |
| `-y, --yes` | Skip the interactive confirmation prompt (useful for automated scripts). |
| `--regenerate-policy` | Rebuild `/etc/usbguard/rules.conf` from currently attached hardware, saving a timestamped backup. |
| `--user <username>` | Explicitly specify the non-root user authorized for IPC access. |
| `--remove` | Perform a complete, clean rollback and uninstall. |

---

## Component Reference

| File | Purpose |
| :--- | :--- |
| `manifest.json` | Omarchy Shell plugin manifest defining bar widget and settings schema. |
| `Panel.qml` | Quickshell bar widget and interactive control panel flyout. |
| `Model.js` | Parser and classifier for USB device classes, heuristics, and rules. |
| `omarchy-setup-security-usbguard` | Installation wizard, policy generator, and rollback manager. |
| `omarchy-setup-usbguard` | Compatibility symlink mapping to setup wizard. |
| `omarchy-usbguard-watch` | Background systemd service wrapper invoking event delegation. |
| `omarchy-usbguard-event` | Structured event handler executing classification, sanitization, and desktop notifications. |
| `omarchy-usbguard-prompt` | Interactive Quickshell menu interface (`omarchy-menu-select`). |
| `omarchy-usbguard-allow` | Hash-validated authorization execution helper. |
| `omarchy-usbguard-manage` | Zero-friction trusted device revocation and whitelist manager. |

---

## Policy Management and Rollback

### Rebuilding Policy for New Hardware
When permanently attaching new desktop peripherals (e.g., a new docking station or external keyboard):

```bash
omarchy-setup-security-usbguard --regenerate-policy
```

### Clean Uninstallation
To cleanly disable USBGuard, remove systemd units, restore configuration backups, and purge installed binaries:

```bash
omarchy-setup-security-usbguard --remove
```

---

## Verification and Testing

1. Verify that both system and user services are active:
   ```bash
   systemctl is-active usbguard.service
   systemctl --user is-active omarchy-usbguard-notify.service
   ```
2. Inspect the active baseline rules:
   ```bash
   usbguard list-rules
   ```
3. Connect an unauthorized USB storage drive:
   * A desktop notification will appear detailing the resolved vendor and interface class.
   * Clicking the toast presents authorization choices.
   * Disconnecting the drive safely triggers an auto-dismissing disconnect notice.

---

## Security Policy

For vulnerability reporting guidelines, see [SECURITY.md](SECURITY.md).

---

## License

This project is licensed under the terms of the [MIT License](LICENSE).
