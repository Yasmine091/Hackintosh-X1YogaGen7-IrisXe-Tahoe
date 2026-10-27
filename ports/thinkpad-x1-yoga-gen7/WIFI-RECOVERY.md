# Wi-Fi-only macOS Recovery path

**Status: candidate identified; not configured or tested on the ThinkPad.** No Ethernet adapter is available, so the installer path must be tested over the laptop's Intel AX211 Wi-Fi before installation.

## Evidence

- The Yoga inventory identifies an Intel AX211, PCI ID `8086:51F0`.
- The upstream OpenIntelWireless compatibility list includes Intel Wi-Fi 6 AX211. Its current official stable release is not a Tahoe build; do not use that release for Tahoe. [Hardware compatibility](https://openintelwireless.github.io/itlwm/Compat.html) · [official releases](https://github.com/OpenIntelWireless/itlwm/releases)
- The `laobamac/itlwm` fork publishes a separate x86_64 `AirportItlwm-Tahoe` build for macOS 26 and says hardware support follows the upstream device table, while requiring validation for each adapter. Its current `v2.4.0-alpha` release is explicitly a development build requiring hardware validation; the release asset is labeled `738d4c6`. [Tahoe README](https://github.com/laobamac/itlwm/blob/main/README.md) · [v2.4.0-alpha release](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha)
- OpenCore's guide says `AirportItlwm` can work in Recovery through `IO80211Family` integration; plain `itlwm` requires HeliPort and does not work in Recovery. The guide also calls for a valid `SecureBootModel` for the native AirportItlwm path. This general guidance does **not** prove that the Tahoe alpha works in this Yoga's Recovery environment. [OpenCore Wi-Fi guidance](https://dortania.github.io/OpenCore-Install-Guide/ktext.html#intel)

## Candidate setup and gates

1. Use only the Tahoe-specific `AirportItlwm` build. Do not load `itlwm.kext` at the same time, and do not reuse the repo's Dell Wi-Fi configuration. The existing stable OpenIntelWireless release is not the Tahoe build.
2. The pinned candidate asset is `AirportItlwm-Tahoe-v2.4.0-RELEASE-alpha-738d4c6.zip`, SHA-256 `25680aa39ddd79b205141875b261bdcc28bea150d13f27787b3c215555daa00f`. On the main Kubuntu PC, run `bash ports/thinkpad-x1-yoga-gen7/tools/download-tahoe-airportitlwm.sh DESTINATION_DIR` with a normal folder on the PC, not the USB. It downloads only this ZIP and verifies that hash; it does not extract or install it. Before adding a downloaded kext, inspect its `Info.plist` and binary architecture, and confirm its kernel range covers the chosen Tahoe Recovery build. Do not commit the third-party binary or Wi-Fi credentials.
3. Build a separate, minimal Yoga Recovery EFI. Keep GPU spoofing, NootedGreen, Dell ACPI, Dell USB mapping, and Dell SMBIOS data out of it. Validate the EFI with the validator matching its OpenCore binaries.
4. Boot Recovery and verify that the Wi-Fi picker sees the access point and completes association. The candidate fork documents WPA2-Personal and WPA2/WPA3 transition networks with optional PMF; it does not claim WPA3-only or mandatory-PMF support.
5. Record the macOS version/build shown by the installer before installing. The graphics work in this repository is pinned to Tahoe 26.7.1 build `25G241`; stop if Recovery offers a different build until the graphics patches have been revalidated for it.

**Current result:** Not tested. A supported device entry plus a Tahoe build makes Wi-Fi-only Recovery plausible, not confirmed. If Recovery cannot associate, stop before installing; an offline installer or a compatible wired adapter will be needed as fallback.

## Safety boundary

This document does not authorize formatting the evidence/MSI-ROM USB or writing to the laptop's internal SSD. Kubuntu partitions, swap, and EFI remain untouched. First boot and Wi-Fi validation must use the external USB; any later macOS install must target only the unallocated space after the exact disk layout is rechecked.
