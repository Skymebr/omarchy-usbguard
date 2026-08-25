# 🛡️ Omarchy USBGuard Hardware Protection

Native, zero-friction USB device authorization and BadUSB mitigation framework for **[Omarchy](https://omarchy.org)** Linux.

Integrates enterprise-grade hardware authorization via **USBGuard** directly into the **Quickshell / Omarchy Shell** desktop environment.

---

## ✨ Features

- **Block-by-Default Hardware Security:** Automatically isolates unknown USB peripherals at the Linux Kernel level.
- **BadUSB & HID Injection Protection:** Inspects USB descriptors and flags suspicious devices claiming to be keyboards or network cards.
- **Hardware Name Resolution:** Queries the official Linux USB hardware database (`lsusb`) to resolve real vendor and model names (e.g., `Kingston DataTraveler 3.0` instead of generic `Mass Storage`).
- **Interactive Quickshell Menu (`omarchy-menu-select`):** 
  - 󰋊 **Allow for this session only** *(Temporary access until unplugged)*
  -  **Trust permanently** *(Adds device signature to `/etc/usbguard/rules.conf`)*
  - 󰅙 **Keep blocked** *(Rejects device communication)*
- **Smart Debouncing:** Filters multi-event Kernel bursts into a single, clean desktop toast.
- **Disconnect Alerts:** Automatic notification when a device is safely unplugged.
- **Lightweight:** Runs in user space consuming only **~1.5 MB of RAM** and 0% idle CPU.
- **1-Command Setup & Removal:** Automatic baseline whitelist generation and clean rollback support (`--remove`).

---

## 🚀 Quick Install

Clone the repository and run the setup wizard:

```bash
git clone https://github.com/YOUR_USERNAME/omarchy-usbguard.git
cd omarchy-usbguard
./omarchy-setup-usbguard
```

The installer will:
1. Ensure `usbguard` is installed via `pacman`.
2. Generate an automatic baseline whitelist for all currently connected native hardware (keyboard, mouse, webcam).
3. Configure non-root IPC permissions for the `wheel` group.
4. Enable and start the system daemon and user-space Quickshell notification watcher.

---

## 🛠️ Usage

### When a new USB device is connected:
1. The device is blocked immediately by the Kernel.
2. Omarchy Shell displays a notification toast with the device icon and vendor name:
   ```text
   󰋊 USB Device Blocked
      Alcor Micro Corp. Flash Drive · Storage
      Click to manage authorization.
   ```
3. **Click the notification** to open the interactive selection menu:
   - **Allow for this session only**
   - **Trust permanently**
   - **Keep blocked**
4. **Right-click the notification** to dismiss it without taking action.

### Uninstallation / Rollback
To disable USBGuard and remove user notification services cleanly:
```bash
./omarchy-setup-usbguard --remove
```

---

## 🏗️ Architecture

```
omarchy-usbguard/
├── omarchy-setup-usbguard    # Automated installation & rollback wizard
├── omarchy-usbguard-watch    # User-space IPC event listener and hardware classifier
├── omarchy-usbguard-prompt   # Interactive Quickshell modal selector
├── omarchy-usbguard-allow    # Authorization helper (session & permanent)
└── README.md
```

---

## 📄 License

MIT License. Open source and free for the Omarchy community.
