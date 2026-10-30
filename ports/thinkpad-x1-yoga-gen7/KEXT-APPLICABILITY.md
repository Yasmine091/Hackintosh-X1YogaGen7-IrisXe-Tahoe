# X1 Yoga Gen 7 kext and driver coverage

This is a hardware-coverage audit, not a claim that any macOS driver has been runtime-tested on the Yoga. The Recovery EFI intentionally contains only the components needed for a first boot, keyboard/pointer access, and the AX211 Wi-Fi experiment. Adding every available kext to Recovery would increase boot risk without making unsupported devices work.

| Yoga hardware/function | Current Recovery candidate | Later candidate or requirement | Evidence and status |
|---|---|---|---|
| Core i7-1265U, 2P+8E | No CPU kext; CPUID emulation plus `ProvideCurrentCpuInfo`; `AppleXcpmCfgLock` enabled because the Yoga's MSR 0xE2 read has bit 15 set | Defer topology rebuild and power tuning; do not copy Dell PL1/PL2 | Same-CPU report supports the CPUID candidate; this Yoga's installer stability and power management remain untested |
| Iris Xe `8086:46A8` and AUO eDP | Recovery uses WhateverGreen with `-igfxvesa`; this is an unaccelerated boot path | Separate post-install profile and official WhateverXe 0.6.1 + AMFIPass Mod bundles are now staged in the Yoga port. It accepts `46A8`, but Alder Lake-P/U internal eDP is experimental and not hardware-tested; it needs Tahoe 26.7+, matching Graphics package, AMFIPass Mod, and reduced SIP. Never load with WhateverGreen | No Metal acceleration in the Recovery EFI. Exact Yoga VBT, panel power sequence, and brightness path remain unverified; see `WHATEVERXE-EXPERIMENT.md` |
| Intel AX211 `8086:51F0` Wi-Fi | Tahoe AirportItlwm | User reported Wi-Fi working in Recovery; keep this build for the current install path | Bundle `IOPCIMatch` includes `0x51F08086`; observed working on the Yoga |
| AX211 Bluetooth | None | `IntelBluetoothFirmware`, `IntelBTPatcher`, `BlueToolFixup` are present in the repository; verify Tahoe compatibility and pairing later | Not included or tested in Recovery |
| Built-in keyboard and TrackPoint | VoodooPS2Controller plus keyboard and mouse plugins | Verify keyboard keys, TrackPoint buttons, and Fn keys separately | User confirmed the TrackPoint pointer works; other functions not fully tested |
| Synaptics SYNA8016 touchpad; Wacom WACF2200 touch/pen | None | VoodooI2C + VoodooI2CHID are candidates because Linux reports `PNP0C50`; derive and validate Yoga I2C/GPIO ACPI routing before enabling | Both devices are I2C-HID and neither driver is in the Recovery EFI; their absence explains missing touch input, not the observed post-handoff restart |
| Realtek ALC287 `10ec:0287` | None | Add a Tahoe-compatible audio path only after confirming AppleALC layout/codec support or another driver | Codec confirmed in Linux; no audio kext currently staged |
| Micron NVMe | No extra kext | macOS native NVMe path first; NVMeFix is available but optional and should be separately tested | Device model known; macOS behavior untested |
| USB-A/USB-C and installer media | `XHCI-unsupported` 0.9.2 has a personality matching the observed controller `8086:51ed`. `USBToolBox` plus generic `UTBDefault` is the upstream pre-map setup; neither supplies a Yoga-specific port map | Keep one recovery configuration at a time; generate and validate a Yoga-specific `UTBMap` before treating USB as mapped | Linux controller and connector paths are observed; macOS USB continuity is unverified. Correction: `UTBDefault` is a generic USBToolBox injector, not Dell-specific; upstream documents it for use before a custom map |
| Battery and power reporting | None | SMCBatteryManager is available; validate Lenovo EC/ACPI before enabling | No runtime test; Dell sensor plugins are not appropriate |
| IPU6 camera `8086:465d` | None | No verified macOS IPU6 driver identified | Linux-only camera fix does not establish macOS support |
| Fingerprint reader `06cb:00fc` | None | No native Touch ID path expected | No macOS driver identified |
| Thunderbolt/USB-C PCIe features | None | Inventory and validate separately after boot | PCIe topology and device behavior not fully captured |

## What is included now

The tracked Recovery template contains Lilu, VirtualSMC, WhateverGreen, Tahoe AirportItlwm, VoodooPS2Controller with its keyboard and mouse plugins, XHCI-unsupported, OpenRuntime, and OpenHfsPlus. The actual USB configuration inspected on 2026-10-29 differs: `USBToolBox` and `UTBDefault` were disabled while `XHCI-unsupported` was enabled; the latest boot arguments also contained `debug=0x14e` and `cpus=1`. This is a diagnostic state, not a validated final Yoga configuration. A prior saved config had USBToolBox and UTBDefault enabled and XHCI-unsupported disabled. Plist validation and kext file presence do not establish runtime compatibility.

For installation, missing touchpad, touchscreen, stylus, Bluetooth, audio, battery, camera, fingerprint, and GPU-acceleration drivers are not all prerequisites. AX211 Wi-Fi has been observed working in Recovery. The missing I2C kexts explain why the I2C touchpad and Wacom input are unavailable; they do not by themselves explain the post-handoff restart. The panic cause remains unknown because no panic report was found on the USB.

## Primary driver references

- [USBToolBox usage](https://github.com/USBToolBox/kext#usage): `UTBDefault` is a generic codeless injector for the pre-map stage; replace it with a generated machine-specific `UTBMap` after mapping.
- [VoodooI2C HID satellite documentation](https://github.com/VoodooI2C/VoodooI2C/blob/master/Documentation/Satellites.md): `VoodooI2CHID` targets I2C-HID devices advertising `PNP0C50`.
- [WhateverXe compatibility and requirements](https://github.com/b00t0x/WhateverXe): its `46A8` backend and experimental internal-eDP support are candidates, not proof that this Yoga panel works. The project requires Tahoe 26.7 or newer and does not allow WhateverGreen to load alongside it.
