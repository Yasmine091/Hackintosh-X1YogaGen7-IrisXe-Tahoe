# X1 Yoga Gen 7 kext and driver coverage

This is a hardware-coverage audit, not a claim that any macOS driver has been runtime-tested on the Yoga. The Recovery EFI intentionally contains only the components needed for a first boot, keyboard/pointer access, and the AX211 Wi-Fi experiment. Adding every available kext to Recovery would increase boot risk without making unsupported devices work.

| Yoga hardware/function | Current Recovery candidate | Later candidate or requirement | Evidence and status |
|---|---|---|---|
| Core i7-1265U, 2P+8E | No CPU kext; candidate CPUID emulation and `ProvideCurrentCpuInfo` in OpenCore | Reassess CPU scheduling/power after boot; do not copy Dell PL1/PL2 | Static config only; Yoga boot behavior untested |
| Iris Xe `8086:46A8` and AUO eDP | WhateverGreen is present with `-igfxvesa`; acceleration is deliberately disabled | Separate experimental NootedGreen/Tiger Lake graphics and Metal stack; Yoga topology, framebuffer, VBT and eDP must be validated | No Metal acceleration in this Recovery EFI; target not tested |
| Intel AX211 `8086:51F0` Wi-Fi | Tahoe AirportItlwm candidate | Keep this exact Tahoe build only if association works; fallback installer must not rely on Wi-Fi | Bundle matches PCI ID; Recovery association untested |
| AX211 Bluetooth | None | `IntelBluetoothFirmware`, `IntelBTPatcher`, `BlueToolFixup` are present in the repository; verify Tahoe compatibility and pairing later | Not included or tested in Recovery |
| Built-in keyboard and TrackPoint | VoodooPS2Controller plus keyboard and mouse plugins | Verify Fn keys and TrackPoint buttons later | Candidate based on Linux PS/2 devices; hardware behavior untested |
| Synaptics SYNA8016 touchpad; Wacom WACF2200 touch/pen | None | VoodooI2C + VoodooI2CHID are repository candidates; derive Yoga-specific I2C/GPIO ACPI routing first | Linux identifies I2C-HID on I2C0/I2C1; no Yoga macOS ACPI yet |
| Realtek ALC287 `10ec:0287` | None | Add a Tahoe-compatible audio path only after confirming AppleALC layout/codec support or another driver | Codec confirmed in Linux; no audio kext currently staged |
| Micron NVMe | No extra kext | macOS native NVMe path first; NVMeFix is available but optional and should be separately tested | Device model known; macOS behavior untested |
| USB-A/USB-C and installer media | XHCI-unsupported candidate is enabled for Alder Lake IDs; no USB port map | Confirm the Yoga XHCI PCI ID. Create a Yoga-specific map before relying on USB after macOS takes over; repository UTBDefault is Dell-specific and excluded | Linux connector-path observations exist; macOS port-map validation absent |
| Battery and power reporting | None | SMCBatteryManager is available; validate Lenovo EC/ACPI before enabling | No runtime test; Dell sensor plugins are not appropriate |
| IPU6 camera `8086:465d` | None | No verified macOS IPU6 driver identified | Linux-only camera fix does not establish macOS support |
| Fingerprint reader `06cb:00fc` | None | No native Touch ID path expected | No macOS driver identified |
| Thunderbolt/USB-C PCIe features | None | Inventory and validate separately after boot | PCIe topology and device behavior not fully captured |

## What is included now

The staged Recovery configuration has Lilu, VirtualSMC, WhateverGreen, Tahoe AirportItlwm, VoodooPS2Controller with its keyboard and mouse plugins, XHCI-unsupported, OpenRuntime, and OpenHfsPlus. Every enabled kext and EFI driver has a corresponding file, and the plist validates with OpenCore 1.0.8 `ocvalidate`. This confirms configuration structure and file presence only; it does not prove driver attachment, Wi-Fi, display, or USB behavior on the laptop.

For installation, the missing touchpad, touchscreen, stylus, Bluetooth, audio, battery, camera, fingerprint, and GPU-acceleration drivers are not all prerequisites. The AX211 Recovery path is the important unproven dependency because there is no built-in Ethernet. If it fails, use a verified offline installer or compatible wired adapter rather than treating the kext match as proof of Wi-Fi.
