# Recovery EFI candidate

**Status: Recovery previously reached its interface on the Yoga; the user reported working TrackPoint and Wi-Fi. A later Installer boot restarted after the macOS handoff.** The EFI was validated with the matching OpenCore 1.0.8 validator. Its generated SMBIOS values are intentionally absent from this repository. No internal SSD partition or Kubuntu EFI has been changed.

## Current boot diagnosis

The last copied log, `opencore-2026-10-29-152845.txt`, predates the latest USB config edit. It selects `\com.apple.installer\boot.efi`, passes `-v keepsyms=1 -igfxvesa debug=0x14e io=0x16 cpus=1`, and ends at `#[EB|LOG:EXITBS:START]`. This confirms OpenCore reached the macOS handoff; it does not contain the later panic or restart cause. No panic-named report was found on the USB. The exact Yoga USB map has not been generated or validated.

The Yoga firmware's `ProjSsdt` table also reported `AE_NOT_FOUND` for `\_SB.PC00.XHCI.RHUB.HS01` in an earlier boot. The captured DSDT creates `HS01` conditionally, while `ProjSsdt` references it directly. The user did not see this error in a later run; its relation to the installer restart is unknown. Do not copy Dell ACPI or suppress the table without an isolated test.

The original Yoga template omitted `NVRAM > Delete > boot-args`, so OpenCore kept an older `-v keepsyms=1 -igfxvesa` value and ignored newly requested debug options. The template now deletes that one Apple NVRAM variable before adding the configured value. On 2026-10-29 the USB config was updated: `UEFI > Output > Resolution=Max`, and the temporary `cpus=1` diagnostic was removed. A later direct edit serialized it as a binary plist; Python could read it, but OpenCore 1.0.8 `ocvalidate` rejected the live USB file with `OCS: Couldn't parse serialized file!`. The settings matched the valid candidate exactly, so the failure was the serialization format. The same settings have now been written back as XML, and `ocvalidate` reports no issues on the exact USB file. The USB's `OpenCore.efi` matches the pinned OpenCore 1.0.8 binary. Recovery still uses `-igfxvesa`, its Wi-Fi kext remains enabled, and its other kext toggles were preserved. `Resolution=Max` requests the largest firmware GOP mode for OpenCore/preboot; it does not force macOS's display mode. The USB is safely unmounted after the correction.

## What this configuration is for

This is a first boot and Wi-Fi test configuration for macOS Recovery. It deliberately runs without the experimental Iris Xe acceleration stack. `-igfxvesa` asks WhateverGreen to avoid Intel graphics acceleration for this stage; it does not guarantee the internal eDP panel will display. The user reports that the TrackPoint and Wi-Fi worked in Recovery; the native display mode and other input/network functions still need testing.

The product model is `MacBookPro16,2`, a Tahoe-supported Intel Mac model and the SMBIOS used in a community report for a Latitude 7430 with the same i7-1265U / Iris Xe 46A8. It is a compatibility identity choice, not a claim that the Yoga is that Mac. Apple lists the 13-inch 2020 four-Thunderbolt-port MacBook Pro as Tahoe-compatible: [Apple Tahoe compatibility](https://support.apple.com/en-la/122867).

## Private SMBIOS values

The tracked `config-recovery-template.plist` has empty serial, MLB, UUID, and ROM fields. The current private config was filled using the existing GenSMBIOS script in `Disco local/ultimate-macOS-KVM/GenSMBIOS`, with its local macserial 2.1.8; it wrote the result only into the private staged `EFI/OC/config.plist`. The repository builder can reuse that config with `--reuse-config`, or generate a new set from the pinned OpenCore 1.0.8 macserial. Keep the generated EFI private and reuse the same identity for future builds. The values are synthetic, not issued or validated by Apple, and Apple service acceptance is not guaranteed. Never copy identifiers from a real Mac or publish the generated config.

Apple Account sign-in is not needed to complete macOS installation or reach the desktop. Setup Assistant provides **Set Up Later** for Apple Account sign-in; defer it until boot and hardware are stable. [Apple setup guidance](https://support.apple.com/guide/imac/set-up-your-mac/apd831707cb3/mac).

## Included kexts

| Kext | Recovery purpose | Status on this Yoga |
|---|---|---|
| Lilu | Kext patch framework dependency | Required by the selected plugins; not runtime-tested |
| VirtualSMC | SMC emulation for macOS startup | Included; not runtime-tested |
| WhateverGreen | Handles `-igfxvesa` fallback behavior | Included; no GPU acceleration enabled |
| AirportItlwm Tahoe build | Native Wi-Fi candidate for AX211 `8086:51F0` | User reports Wi-Fi works in Recovery; exact PCI match is confirmed |
| VoodooPS2Controller + keyboard + mouse plugins | Internal PS/2 keyboard and TrackPoint pointer | User reports the TrackPoint pointer works; keyboard, buttons, and Fn keys are not fully tested |
| XHCI-unsupported | Alder Lake XHCI personality injection candidate | Matches Alder Lake IDs in its plist; exact Yoga PCI ID/USB behavior untested |

This is the minimal Recovery set, not the full laptop kext set. It leaves out NootedGreen and all GPU spoof/framebuffer properties; the XPS ACPI tables and USB map; I2C/GPIO/touchscreen/touchpad support; Bluetooth; audio; battery, sensors, and NVMe power-management extras. Touch input, audio, Bluetooth, USB port persistence, and GPU acceleration are not provided by this Recovery config.

The i7-1265U CPUID emulation bytes are copied as a **candidate** from the repository install config because a same-CPU community report used them. `ProvideCurrentCpuInfo` is enabled for the hybrid CPU. BIOS CFG-lock state and Yoga boot behavior remain unverified; no CPU power limits are copied.

## Rebuild on the main PC

From the repository root on Kubuntu, run:

```sh
python3 ports/thinkpad-x1-yoga-gen7/tools/build-recovery-efi.py \
  --output /tmp/x1-yoga-recovery-efi
```

The script downloads or accepts the official OpenCore 1.0.8 archive, checks its pinned SHA-256, copies only the required EFI binaries and pinned kext executables, generates private SMBIOS values, and runs `ocvalidate` from that same release. It refuses to overwrite an existing output. To retain an earlier identity when making another output, add:

```sh
--reuse-config /path/to/the/previous/EFI/OC/config.plist
```

The builder output contains an `EFI/` folder only. It includes OpenRuntime and OpenHfsPlus; OpenHfsPlus is needed by many Recovery images. The builder does not contain Apple's `BaseSystem.dmg`/chunklist, format or write a USB, or touch any laptop disk or firmware setting. The current USB was prepared separately and contains Recovery plus private evidence and MSI.ROM.

## Kubuntu and macOS picker

The candidate keeps OpenCore on the removable USB and leaves `LauncherOption=Disabled`, so it does not create a permanent OpenCore firmware boot entry or write files to Kubuntu's internal EFI. `RequestBootVarRouting` is enabled to isolate OS boot-variable changes for the multi-OS setup; the firmware picker behavior still needs testing. `ScanPolicy=0` permits discovery of the existing EFI System Partition and later APFS volumes. The template also has a `BlessOverride` for the common Kubuntu loader path `\EFI\ubuntu\grubx64.efi`; **verify that exact file on the Yoga before relying on it** with:

```sh
sudo find /boot/efi/EFI -maxdepth 3 -type f -iname '*.efi' -printf '%P\n'
```

If the path differs, change `Misc -> BlessOverride` to the reported GRUB path. Once macOS is installed into the separately selected unallocated space, OpenCore's APFS support can add it to the same picker. Until the picker is hardware-tested, the firmware's one-time boot menu remains the fallback for choosing Kubuntu directly. No internal EFI file is edited by this plan.

## Build-version gate

Apple released Tahoe 26.7.2 on 2026-10-26. This repository's graphics patch baseline remains Tahoe 26.7.1 build `25G241` with Apple Tiger Lake graphics bundle 16.0.32. A current Recovery download may offer a newer build; use it only to test OpenCore startup and AX211 Wi-Fi, then stop before installing until we either pin the matching 25G241 installer or revalidate/port the graphics patches to the newer build. [Apple Tahoe updates](https://support.apple.com/en-us/122868).

## Reproducibility and safety

- OpenCore source archive: `OpenCore-1.0.8-RELEASE.zip`, SHA-256 `2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b`.
- Kext executable or injector-plist hashes are embedded in the builder and are checked before staging.
- The output is not proven bootable by `ocvalidate`; that validator checks config structure only.
- No installer, ACPI override, GPU spoof, external drive write, partition operation, or internal EFI change is performed.
- Keep Kubuntu's EFI, ext4 partitions, swap, and the unallocated area untouched until a separate install plan identifies the exact target and is approved.
