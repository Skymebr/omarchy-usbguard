# 🛡️ Omarchy USBGuard Hardware Protection

Native, zero-friction USB device authorization and BadUSB mitigation framework for **[Omarchy](https://omarchy.org)** Linux.

Integrates enterprise-grade hardware authorization via **USBGuard** directly into the **Quickshell / Omarchy Shell** desktop environment.

---

## ✨ Key Features & Architecture

- **Block-by-Default Kernel Protection:** Automatically isolates unknown USB peripherals at the Linux Kernel level before drivers are bound.
- **BadUSB & Keystroke Injection Inspection:** Inspects interface descriptor combinations to detect malicious composite devices (e.g. devices claiming to be both Mass Storage `08:` and Keyboard/HID `03:`).
- **Event-Driven Daemon (`usbguard watch -e`):** Zero regex stdout parsing. Uses the native USBGuard event execution hook with structured environment variables.
- **Dynamic Hash-Based Notification IDs:** Computes notification replace IDs per device hash, preventing multi-device collisions and toast overwrites.
- **Input Sanitization:** Strips control characters, collapses whitespace, and removes leading hyphens to prevent argument injection attacks from attacker-controlled `iProduct` strings.
- **Hardware Name Resolution:** Queries the official Linux USB hardware database (`lsusb`) to resolve real vendor and model names (e.g. `Alcor Micro Corp. Flash Drive` instead of generic `Mass Storage`).
- **Interactive Quickshell Menu (`omarchy-menu-select`):** 
  - 󰋊 **Allow for this session only** *(Temporary access until unplugged)*
  -  **Trust permanently** *(Appends signature to `/etc/usbguard/rules.conf`)*
  - 󰅙 **Reject device** *(Unbinds communication and removes device node in kernel)*
  - 󰌾 **Keep blocked** *(No change)*
- **Anti-Lockout Baseline Setup:** Automatically whitelists internal `hardwired` peripherals (webcams, Bluetooth, fingerprint sensors) and configures `PresentDevicePolicy=keep`.
- **Safe Rollback & Policy Regeneration:** Supports `--remove` for clean 1-command uninstall and `--regenerate-policy` with automatic timestamped backups.

---

## 🚀 Quick Install

Clone the repository and run the setup wizard:

```bash
git clone https://github.com/Skymebr/omarchy-usbguard.git
cd omarchy-usbguard
./omarchy-setup-security-usbguard
```

The installer will:
1. Display a prominent confirmation banner warning to keep your keyboard and mouse plugged in.
2. Install `usbguard` via `pacman` if not present.
3. Automatically auto-allow internal `hardwired` hardware and generate a baseline policy.
4. Configure non-root IPC permissions specifically for your user.
5. Enable and start the system daemon and user-space Quickshell notification watcher.

---

## 🛠️ Usage

### When a new USB device is connected:
1. The device is blocked immediately by the Kernel.
2. Omarchy Shell displays a notification toast with the device icon and resolved vendor name:
   ```text
   󰋊 USB Device Blocked
      Alcor Micro Corp. Flash Drive · Mass Storage
      Click to manage authorization.
   ```
3. **Click the notification** to open the interactive selection menu.
4. **Right-click the notification** to dismiss it without action.

### Rebuilding Baseline Policy
If you attach a permanent new dock or keyboard that you want included in the baseline:
```bash
./omarchy-setup-security-usbguard --regenerate-policy
```

### Uninstallation / Rollback
To disable USBGuard and cleanly remove all user notification services and binaries:
```bash
./omarchy-setup-security-usbguard --remove
```

---

## 🏗️ File Structure

```
omarchy-usbguard/
├── omarchy-setup-security-usbguard  # Automated installation, regeneration & rollback wizard
├── omarchy-setup-usbguard           # Symlink for backward compatibility
├── omarchy-usbguard-watch           # Lightweight daemon delegating to event handler
├── omarchy-usbguard-event           # Per-event handler (sanitization, BadUSB check, notifications)
├── omarchy-usbguard-prompt          # Interactive Quickshell modal selector
├── omarchy-usbguard-allow           # Hash-validated authorization helper
└── README.md
```

---

## 📄 License

MIT License. Open source and free for the Omarchy community.
