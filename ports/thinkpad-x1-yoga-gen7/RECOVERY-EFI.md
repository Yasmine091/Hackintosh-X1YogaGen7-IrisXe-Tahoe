# Recovery EFI candidate

**Status: Recovery previously reached its interface on the Yoga; the user reported working TrackPoint and Wi-Fi. A later Installer boot restarted after the macOS handoff.** The last inspected USB config passed the matching OpenCore 1.0.8 validator; this repo's synchronized templates have been plist-parsed but should be run through that validator before rebuilding. Generated SMBIOS values are intentionally absent from this repository. No internal SSD partition or Kubuntu EFI has been changed.

## Current boot diagnosis

Four panic-named files copied from the USB have the same SHA-256, so they are one report duplicated four times. The report is an early NULL-page fault on CPU 0 in `AppleUSBXHCIPCI::getAcpiPort` / `createPort` while the XHCI controller changes power state; its captured boot arguments include `cpus=1`. It predates the combined PCH + Thunderbolt `UTBMap`, so it does not prove that the current map fixes the panic. A read-only extraction of this USB's Tahoe 26.6.2 Recovery BaseSystem shows Apple's `AppleUSBXHCIPCI` has a generic `IOPCIClassMatch=0x0c033000`, which matches the Yoga XHCI class. The USB's RehabMan `XHCI-unsupported` 0.9.2 adds a higher-priority (`IOProbeScore=900`) exact `0x51ed8086` personality using `AppleUSBXHCISPT`; this may compete with the stock generic match. The Oct 30 USB A/B disables only this injector; `USBToolBox` and the captured Yoga `UTBMap` remain enabled. This is a test candidate, not a confirmed fix. The old panic is concrete XHCI evidence, not a CPU-topology panic.

The read-only USB audit found 49 OpenCore traces: 24 select the `\UUID\com.apple.installer\boot.efi` stage, 20 select a `\System\Library\CoreServices\boot.efi` system/recovery path, and five do not reach a recorded boot path. The installer attempts from 13:08 through 21:21 are therefore not mistaken Recovery selections. Most carry `-restore` and `auth-root-dmg=...x86_64SURamDisk.dmg`; the 13:08 and 21:03 attempts instead carry `lca-boot-mode=autoinstall-msu` and point to `macOS Install Data/BaseSystem.dmg`, confirming the staged automatic-install path was entered. Twenty-three of the 24 installer-path traces reach `#[EB|LOG:EXITBS:START]`; that proves OpenCore handed control onward, not that the installer completed or why the machine restarted afterward. The last two traces (21:37 and 21:38) select the system/recovery path, not the installer stage. The USB contains no new panic report after 19:28; all four panic-named files are duplicates of the earlier XHCI report. `AppleDebug` and `ApplePanic` were enabled in the inspected config, so the absence of a later panic file is evidence against a *captured* kernel panic, not proof that no crash or reset occurred.

The Yoga firmware's `ProjSsdt` table reported `AE_NOT_FOUND` for `\_SB.PC00.XHCI.RHUB.HS01` in an earlier boot. The captured DSDT creates `HS01` conditionally, while `ProjSsdt` references it directly. A later boot no longer showed that error. The last inspected USB config and both templates now delete only the exact `SSDT` with OEM table ID `ProjSsdt` and length 4731. This is a target-specific diagnostic change, not a proven cause of the restart. OpenCore ACPI deletion applies to any OS booted through that OpenCore config, including Kubuntu; use the firmware's direct Kubuntu entry if its ACPI behavior changes. The existing Kubuntu EFI itself remains untouched.

The inspected USB config is dated 2026-10-30 16:33 and parses as an OpenCore 1.0.8 XML plist. Its boot args are `-v keepsyms=1 -igfxvesa io=0x16`; `cpus=1`, `debug=0x14e`, and `-utboff` are absent. `NVRAM > Delete` includes `boot-args`, `UEFI > Output > Resolution=Max`, Wi-Fi is enabled, and `USBToolBox` plus the Yoga `UTBMap` are enabled. Compared with `config.plist.before-xhci-native-match-test`, its only change is `XHCI-unsupported.kext -> Enabled=false`. It also deletes the exact `ProjSsdt` table described above. Both templates now generate this XHCI A/B setting; the recovery builder still stages the pinned injector bundle so it can be re-enabled for rollback. A sanitized comparison against the recovery template found no non-private, non-comment config-value differences, and the kext load order matches. All three ACPI AML files on the USB match the Yoga repository files byte-for-byte. Eight of ten checked kext executables/metadata files also match; the USB's VoodooPS2 keyboard and mouse plugin executables differ from the repo despite both declaring version 2.3.8 and exposing the same strings. I left that pair unchanged pending source review. `Resolution=Max` requests the largest firmware GOP mode for OpenCore/preboot; it does not force macOS's display mode. At the latest check the USB was still mounted read-only with this same config and no backup from the attempted update; the latest saved boot trace is still Oct 29 22:38. The new candidate below has not been copied or booted.

## Next installer attempt

Keep the current CPU settings. They match the tested 2P+8E ThinkPad X1 Carbon Gen 11 stage-1 profile, and this Yoga has already reached Recovery with them. The saved Yoga panic is an XHCI `getAcpiPort` fault, not a CPU-topology panic.

Before another macOS Installer boot, use Recovery's **Utilities → Terminal** to capture the APFS volume state and installer log below. The USB's OpenCore log ends at kernel handoff and has no post-Oct 29 panic report, so it cannot explain the latest restart. Do not change CPU or graphics settings based on the final visible verbose line alone.

If an XHCI `getAcpiPort` panic recurs under this current config, the tracked `config-recovery-utbacpioff-template.plist` is an isolated USBToolBox experiment: it adds only `-utbacpioff` while preserving the current CPU spoof, Yoga map, and other config values. Capture the recurrence first; do not use the older combined EAX-only + USB argument candidate.

## Next evidence to collect (read-only)

The existing OpenCore traces end at the handoff to the macOS kernel and do not contain the installer log or restart cause. The new [`collect-installer-state.sh`](tools/collect-installer-state.sh) automates the read-only capture: stage a copy at the root of the external installer USB before booting, then in Recovery open **Utilities → Terminal** and run `sh '/Volumes/NO NAME/collect-installer-state.sh'` (replace `NO NAME` if `ls /Volumes` shows a different USB name). It refuses to write unless macOS identifies the script's volume as external, and saves a timestamped report beside itself on that USB. It gathers `diskutil list`, APFS volumes, Recovery/build information, likely installer logs and installer metadata; it does not read NVRAM or hardware serials. After running it, bring the USB back to the main PC and share the `yoga-installer-state-*.txt` report. If the script is not staged, the manual read-only commands below are the fallback. Before running the installer again, capture this report from Recovery:

```sh
sw_vers -productVersion
sw_vers -buildVersion
uname -a
diskutil list
diskutil apfs list
ls -la /Volumes
find /Volumes -maxdepth 7 -type f \( -iname 'install.log' -o -iname 'osinstallersetup.log' -o -iname 'InstallInfo.plist' -o -iname 'SystemVersion.plist' \) -print 2>/dev/null
```

If `find` returns an installer log, read its last 120 lines with `tail -n 120 '/exact/path/from/find'`. This determines whether the APFS target and staged installer data exist and exposes the installer's own failure point. These commands only inspect volumes; do not erase, repartition, or run the installer from Terminal.

The USB's Recovery image was also inspected read-only: `com.apple.recovery.boot/BaseSystem.dmg` contains `SystemVersion.plist` reporting macOS `26.6.2` build `25G83`. This identifies the Recovery environment only; it does **not** identify the separate installer build staged on the internal APFS volume. If `find` returns `InstallInfo.plist` or `SystemVersion.plist`, inspect it with `plutil -p '/exact/path/from/find'`.

## Installer media from the main PC

The current USB is an online Recovery installer. OpenCore's install guide supports creating online Recovery media on Linux; it says a complete offline installer must be assembled on macOS because Linux lacks the APFS/HFS tooling needed by that process. Since the user confirmed AX211 Wi-Fi worked in Recovery, rebuilding or repartitioning the current USB for an offline installer is not the next step. The recovery environment can download an installer, but its exact staged build still needs to be read from the target. Apple also notes that macOS installation can restart several times; restarts alone do not establish failure. Our logs already show the expected internal Installer boot path, so the next useful discriminator is the APFS state and install log, not another change to CPU or USB settings. [OpenCore online/offline installer guidance](https://dortania.github.io/OpenCore-Install-Guide/installer-guide/), [Apple reinstall guidance](https://support.apple.com/en-euro/102655).

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
| USBToolBox + Yoga `UTBMap` | PCH XHCI `8086:51ED` and Thunderbolt XHCI `8086:461E` connector map | Compiled from the Yoga's Linux path captures; macOS enumeration/persistence is not yet validated. An earlier duplicated panic report faults in `AppleUSBXHCIPCI::getAcpiPort`, before this combined map was installed |
| XHCI-unsupported | Old RehabMan 0.9.2 adds a specific `51ED` `AppleUSBXHCISPT` personality | Disabled in the Oct 30 A/B while the captured map and USBToolBox stay enabled. The recovery builder stages its pinned bundle as a rollback option. The Recovery BaseSystem's stock driver class-matches the controller; whether the injector caused the recorded panic is unproven |

This is the Recovery/installer set, not the full laptop kext set. It leaves out NootedGreen and GPU spoof/framebuffer properties; XPS ACPI and USB data; I2C/GPIO/touchscreen/touchpad support; Bluetooth; audio; battery, sensors, and NVMe power-management extras. The Yoga USB map is present, but its persistence has not been tested in macOS. Touch input, audio, Bluetooth, and GPU acceleration are not provided by this Recovery config.

The CPU settings are documented in [CPU-APPLICABILITY.md](CPU-APPLICABILITY.md). In brief: the Yoga config uses OpenCore's Alder Lake EAX spoof, `ProvideCurrentCpuInfo`, the EBX[23:16]=0x80 hybrid-topology workaround, the MSR-confirmed `AppleXcpmCfgLock=true`, and Yoga-derived `SSDT-PLUG-ALT` / `SSDT-CPU-STA`. A tested X1 Carbon Gen 11 with the same 2P+8E / 12-thread topology uses the same CPUID bytes and reports all 12 threads working; it is a Raptor Lake comparison, not the exact Alder Lake Yoga. The current USB also has `SetupVirtualMap=true`, `AppleDebug=true`, and `ApplePanic=true`. Keep the CPU profile while collecting evidence about the installer restart.

## Rebuild on the main PC

From the repository root on Kubuntu, run:

```sh
python3 ports/thinkpad-x1-yoga-gen7/tools/build-recovery-efi.py \
  --output /tmp/x1-yoga-recovery-efi
```

By default, the script uses the pinned OpenCore 1.0.8 RELEASE archive. For a separate diagnostic build, add `--debug`; this selects the separately pinned official DEBUG archive and sets `DisplayLevel` to `0x80000042` (ERROR, WARN, and INFO). The tracked Recovery template uses `Target=67` for file logging. OpenCore's own documentation says RELEASE builds omit DEBUG_INFO, so `Target=67` by itself does not provide the detailed trace needed here. A DEBUG build can be slower and should be used for a diagnostic boot, not as an assumption that the installer failure is fixed.

The script checks the selected archive's SHA-256, copies only the required EFI binaries and pinned kext executables, generates private SMBIOS values, and runs `ocvalidate` from that same archive. It refuses to overwrite an existing output. To retain an earlier identity when making another output, add:

```sh
--reuse-config /path/to/the/previous/EFI/OC/config.plist
```

For example, with this USB mounted on the main PC, create a local diagnostic EFI that keeps the existing USB identity:

```sh
python3 ports/thinkpad-x1-yoga-gen7/tools/build-recovery-efi.py \
  --output /tmp/x1-yoga-recovery-debug \
  --debug \
  --reuse-config /run/media/leisure/62AD-65F9/EFI/OC/config.plist
```

This only creates `/tmp/x1-yoga-recovery-debug`; it does not update the USB. Keep the current USB EFI as the rollback copy when deciding whether to stage the diagnostic build.

The builder output contains an `EFI/` folder only. It includes OpenRuntime and OpenHfsPlus; OpenHfsPlus is needed by many Recovery images. The builder does not contain Apple's `BaseSystem.dmg`/chunklist, format or write a USB, or touch any laptop disk or firmware setting. The current USB was prepared separately and contains Recovery plus private evidence and MSI.ROM.

## Kubuntu and macOS picker

The candidate keeps OpenCore on the removable USB and leaves `LauncherOption=Disabled`, so it does not create a permanent OpenCore firmware boot entry or write files to Kubuntu's internal EFI. `RequestBootVarRouting` is enabled to isolate OS boot-variable changes for the multi-OS setup; the firmware picker behavior still needs testing. `ScanPolicy=0` permits discovery of the existing EFI System Partition and later APFS volumes. The template also has a `BlessOverride` for the common Kubuntu loader path `\EFI\ubuntu\grubx64.efi`; **verify that exact file on the Yoga before relying on it** with:

```sh
sudo find /boot/efi/EFI -maxdepth 3 -type f -iname '*.efi' -printf '%P\n'
```

If the path differs, change `Misc -> BlessOverride` to the reported GRUB path. Once macOS is installed into the separately selected unallocated space, OpenCore's APFS support can add it to the same picker. Until the picker is hardware-tested, the firmware's one-time boot menu remains the fallback for choosing Kubuntu directly. No internal EFI file is edited by this plan.

## Build-version gate

Apple now lists Tahoe 26.7.2; this repository's graphics patch baseline remains 26.7.1 build `25G241` with Apple Tiger Lake graphics bundle 16.0.32. The USB Recovery BaseSystem itself is 26.6.2 build `25G83`; the staged installer build remains unknown. The saved panic logs report Darwin `25.6.0`, which does not distinguish these Tahoe builds. At the next Recovery Terminal session, capture `sw_vers -productVersion` and `sw_vers -buildVersion` and inspect any staged `InstallInfo.plist` before deciding whether to continue. Installing a newer build may still be fine for the temporary macOS system, but do not enable the version-sensitive Iris Xe/Metal patches until the installed Tahoe build is confirmed or the patches are revalidated. [Apple Tahoe updates](https://support.apple.com/en-us/122868).

## Reproducibility and safety

- OpenCore source archive: `OpenCore-1.0.8-RELEASE.zip`, SHA-256 `2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b`.
- Kext executable or injector-plist hashes are embedded in the builder and are checked before staging.
- The output is not proven bootable by `ocvalidate`; that validator checks config structure only.
- No installer, ACPI override, GPU spoof, external drive write, partition operation, or internal EFI change is performed.
- Keep Kubuntu's EFI, ext4 partitions, swap, and the unallocated area untouched until a separate install plan identifies the exact target and is approved.
