# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |

## IPC Access Control & Privilege Model (Trade-offs)

`omarchy-usbguard` configures USBGuard IPC access for the primary desktop user with the following permissions:
```
usbguard add-user -u "$TARGET_USER" -d modify,list,listen -p modify,list -e listen -P listen
```

### Desktop Single-User Trade-off Analysis:
1. **Device Modification (`-d modify`):** Allows the active desktop session to grant temporary session authorization (`allow-device`) or block devices directly from the Quickshell bar widget without requesting root password via `sudo`/`polkit` on every physical USB insertion.
2. **Policy Modification (`-p modify`):** Allows writing permanent whitelist rules (`allow-device -p`) to `/etc/usbguard/rules.conf`.
3. **Security Consideration:** In multi-user or shared workstation environments where unprivileged users should not be allowed to trust hardware permanently, policy permissions can be restricted to `list,listen` by omitting `modify` from `-p`. For standard personal Omarchy desktop installations, `-p modify` provides a seamless zero-friction user experience while maintaining kernel-level protection against untrusted or rogue peripherals.

## Reporting a Vulnerability

We take the security of this project and the Omarchy ecosystem seriously.

If you believe you have found a security vulnerability in `omarchy-usbguard`, please do not report it through public GitHub issues or public chat channels.

### Reporting Procedure

1. Submit a report privately via GitHub Security Advisories or by contacting the maintainer directly.
2. Please include:
   - A detailed description of the vulnerability.
   - Steps to reproduce or proof-of-concept payload/descriptor.
   - The potential impact of exploitation.
   - Your system environment (Omarchy version, kernel version, USBGuard version).

### Response Timeline

- **Initial Response:** Within 48 hours of receipt.
- **Triage and Verification:** Within 5 business days.
- **Fix and Disclosure:** Fixes will be coordinated and released with credit to the reporter.
