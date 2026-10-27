# Wi-Fi-only macOS Recovery path

**Status: the Tahoe kext statically matches the AX211; Recovery networking is not configured or tested on this ThinkPad.** The target has no Ethernet port, so Recovery Wi-Fi is a required experiment unless we prepare a verified offline installer.

## Evidence

- The Yoga inventory identifies Intel AX211 PCI `8086:51F0`.
- The repository already contains the pinned Tahoe `AirportItlwm.kext`. Its executable is byte-identical to the pinned `v2.4.0-alpha` asset (binary SHA-256 `259bac9432bffa8bf9c73411d8ac8f4a854552375e9f60ba0870ea3151ed973c`), and its `IOPCIMatch` includes `0x51F08086`. This confirms the driver's static match, not successful initialization or connection on the Yoga.
- Upstream's device table includes AX211. The `laobamac/itlwm` fork targets Tahoe 26.x x86_64, but says compatibility still needs per-adapter validation. Its `v2.4.0-alpha` is a development build. [Hardware compatibility](https://openintelwireless.github.io/itlwm/Compat.html) · [Tahoe README](https://github.com/laobamac/itlwm/blob/main/README.md) · [v2.4.0-alpha release](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha)
- OpenCore's general guide says AirportItlwm can work in Recovery and needs a valid `SecureBootModel`; plain `itlwm` requires HeliPort and does not work in Recovery. This does not establish Recovery behavior for the Tahoe alpha on this Yoga. [OpenCore Wi-Fi guidance](https://dortania.github.io/OpenCore-Install-Guide/ktext.html#intel)

## Recovery configuration gates

1. Use a separate Yoga Recovery EFI. Do not reuse either Dell config: `config.plist` enables AirportItlwm for Darwin 25.x but contains XPS settings and `SecureBootModel=Disabled`; `config-install.plist` enables plain `itlwm`, which is not a Recovery path.
2. Resolve the Recovery-specific SecureBootModel setting and validate it against the chosen OpenCore build. The XPS Tahoe config's disabled setting is known to work for that installed system, while generic OpenCore Wi-Fi guidance calls for a valid model in Recovery. Tahoe OTA guidance also uses a disabled setting. Keep Recovery and installed-system configs separate and test the Recovery setting on USB.
3. Do not load `itlwm.kext` and `AirportItlwm.kext` together. Do not add GPU spoofing, NootedGreen, XPS ACPI, Dell USB mapping, or XPS SMBIOS data to the Yoga Recovery EFI.
4. Boot Recovery and verify the Wi-Fi picker sees the access point and completes association. The Tahoe fork documents WPA2-Personal and WPA2/WPA3 transition networks with optional PMF; it does not support WPA3-only or mandatory PMF.
5. Record the installer version/build before installation. The graphics patches in this repository target Tahoe 26.7.1 build `25G241`; do not install a different build until those patches are revalidated for it.

A full installer for the pinned build could avoid depending on Recovery Wi-Fi, but Linux-side boot-media creation still needs a reviewed and validated method. A generic Recovery download may install a different build.

**Current result:** AX211 device matching is confirmed from the bundled kext metadata. macOS boot, Recovery association, and Wi-Fi stability on this Yoga remain untested. If Recovery cannot connect, stop before installing; use a validated offline installer or obtain a compatible wired adapter.

## Safety boundary

No Wi-Fi credentials or downloaded third-party binaries are committed by this document. It does not authorize formatting the evidence/MSI-ROM USB or writing to the laptop's internal SSD. Kubuntu partitions, swap, and EFI must remain untouched; initial testing uses the external USB only.
