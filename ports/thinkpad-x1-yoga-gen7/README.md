# ThinkPad X1 Yoga Gen 7 port scaffold

**Status: Recovery reached its interface on the Yoga; the user reports that the TrackPoint and AX211 Wi-Fi work. A later installer boot restarted before Setup Assistant, and the saved OpenCore log does not contain the post-handoff panic/restart cause.** The Recovery EFI is not yet a proven completed installation. Development happens on the separate main PC. Raw Yoga ACPI/VBT evidence and generated SMBIOS values stay private and out of Git. Current boot findings are in [RECOVERY-EFI.md](RECOVERY-EFI.md).

## Repository audit

The Yoga port branch was started from revision 99631db20ad841bb5d5f3934e4ffa4dc09f92dee and is developed as yoga-gen7, tracking the user's origin/dev. The upstream Dell configuration remains unchanged. The maintained EFI and all confirmed results in this repository target a Dell XPS 13 Plus 9320 with a Raptor Lake i7-1360P.

The XPS EFI is not a Yoga template. It uses SMBIOS `MacBookPro16,2`, GPU spoofing and framebuffer properties, an XPS USB map, XPS I2C ACPI, and Dell-specific power/sensor configuration. In particular, `acpi/SSDT-XPS-I2C.dsl` hard-codes I2C0/TPL0 as touchscreen and I2C1/TPD0 as trackpad; target-side evidence confirms I2C0.TPD0 for the SYNA8016 touchpad and I2C1.TPL1 for the WACF2200 pen/touch device. The exact GPIO resources and Yoga USB map still need analysis before a complete acceleration EFI is assembled.

### Closest graphics evidence

The repository links a community report from a Dell Latitude 7430 with the **same i7-1265U and Iris Xe 46A8**. It ran Tahoe 26.7.1 build 25G241, spoofed the GPU as 9A49, and reported Metal 2 on a 1920×1080 LG eDP panel. After updating to NootedGreen v2, the reporter reported no hangs in tests covering Displays, Trackpad, Photo Booth, Preview, Photos, QuickTime, and display sleep/wake. Separate display artifacts remained for scaled modes and scaled images. This is strong evidence that the shared GPU stack is worth porting, but it is a community report from Dell firmware and a different panel, not proof for this Yoga. See [issue 2](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/2).

### Exact graphics build baseline

The checked-in scripts and patch notes require **Tahoe 26.7.1, build 25G241**, and Apple's Tiger Lake graphics bundle **16.0.32**. `install.sh` refuses another build unless `XE_FORCE=1` is set. The Metal patcher checks expected byte sequences at fixed offsets and aborts on a mismatch; the VA patch build additionally checks a full SHA-256. A forced build or a similar product version is not evidence that the patches fit.

Apple's Tahoe update page now also lists 26.7.2. Keep this port on the repository's 25G241 baseline until the build-specific patches are independently revalidated; do not silently move to the newest Tahoe. Apple says full-installer downloads depend on the downloader Mac's compatibility and currently available versions, so availability of 26.7.1 must be checked on a compatible Mac with Apple's installer list before relying on it. See [Apple Tahoe updates](https://support.apple.com/en-us/122868) and [Apple's installer instructions](https://support.apple.com/en-us/102662).

### Current graphics route

For this exact `8086:46A8` GPU, the port now vendors the official WhateverXe 0.6.1 plugin and matching AMFIPass Mod for a **separate post-install experiment**. WhateverXe's Alder Lake mobile internal-eDP implementation is still experimental and untested on this panel. Keep the existing WhateverGreen/`-igfxvesa` Recovery profile for installation; do not combine the two plugins. Requirements, artifact hashes, build gating, and the separate plist are documented in [WHATEVERXE-EXPERIMENT.md](WHATEVERXE-EXPERIMENT.md).

### Dependency and build audit

- `install.sh` pins NootedGreen source commit `95f81898be65cb9f7b3d370ca78054be4cc8a62` and downloads Lilu 1.7.2 for the build.
- The checked-in EFI reports runtime Lilu 1.7.3. The build/runtime version mismatch needs to be reconciled or explicitly justified before a reproducible Yoga build.
- The NootedGreen, HookCase, and VoodooGPIO build scripts clone MacKernelSDK at moving HEAD, so those builds are not fully reproducible. VoodooGPIO itself is checked out at `717ab2a`.
- `make-efi.sh` pins OpenCore 1.0.8 only for its `macserial` download. The tracked X64 `OpenCore.efi`, `OpenRuntime.efi`, and `BOOTx64.efi` hashes all differ from the official 1.0.8 release, so their exact version remains unknown. Use one explicitly pinned OpenCore release and its matching validator for the Yoga EFI; do not mix tracked binaries with an assumed 1.0.8 schema.
- The main PC is Ubuntu 26.04.1. It has Python, Clang, iasl and zsh, but no Apple `codesign`, `sw_vers`, `diskutil`, `ioreg`, or `ocvalidate`. The repository's macOS kext/Metal build scripts require Apple's SDK/frameworks and tools; they have not been run here. Static source, plist, JSON and ACPI work can continue on this PC.

## Port design

Keep two configurations separate and machine-specific:

1. **Recovery/installer:** no NootedGreen or GPU spoof/framebuffer injection; no XPS ACPI tables or USB map; a minimal platform support candidate. The user reports AX211 Wi-Fi working in Recovery; keep that kext for the current installer path and see [WIFI-RECOVERY.md](WIFI-RECOVERY.md).
2. **Experimental acceleration:** add the 9A49 presentation only after confirming the Yoga's PCI path; add the active EU/subslice and L3 topology only after reading the target's Linux fuse/topology report; add a Yoga-derived panel and ACPI setup; keep each experimental driver change independently switchable.

A Yoga Recovery config template and local builder are available in [RECOVERY-EFI.md](RECOVERY-EFI.md); see [KEXT-APPLICABILITY.md](KEXT-APPLICABILITY.md) for per-device coverage and omissions. The existing root `config-install.plist` is still XPS-only and must not be used for the Yoga.

## Evidence gates before an EFI

1. On the Yoga in Kubuntu, reconcile reported hardware against machine-type/BIOS, PCI, USB, I2C/HID, audio, eDP/EDID, i915 display state, and SSEU topology. Target-side inventory is complete; the manifest and findings are summarized in EVIDENCE-ANALYSIS.md.
2. The user has completed the firmware evidence export: 51 files are present and the manifest lists no missing captures. Raw files remain private and out of Git.
3. Derive the I2C/GPIO interrupts and a USB map from the Yoga itself. Keep the reported storage, Kubuntu EFI/ext4 partitions, and swap outside this porting work.
4. Keep using the separate Recovery profile for installation; user reports confirm its TrackPoint and Wi-Fi are usable, while its installer restart cause remains unlogged. See [RECOVERY-EFI.md](RECOVERY-EFI.md).
5. After installation, verify the exact macOS build, then test the separate WhateverXe profile and graphics package with a rollback path to Recovery.

## Prepared Linux inventory tool

`tools/collect-linux-inventory.py` reads selected `/proc`, `/sys`, and i915 debugfs entries and prints a report to stdout by default. It includes available `i915_display_info`, `i915_sseu_status`, DMC and eDP power-save diagnostics, plus VBT size/signature/hash. It omits storage devices and partition tables, DMI serials/UUIDs, MAC addresses, and USB serial fields. It does not invoke sudo, install packages, mount filesystems, or change settings. From Kubuntu on the Yoga, start with `python3 tools/collect-linux-inventory.py --confirm-x1-yoga-gen7`; if i915 debugfs entries say unreadable, rerun as `sudo python3 tools/collect-linux-inventory.py --confirm-x1-yoga-gen7`. It also checks that DMI says Lenovo. The default prints to the terminal and writes nothing. The optional `--output PATH` is not needed for sharing; if used, choose a removable-USB path. This tool has not been run on the main PC.

### USB connector capture: initial Linux evidence recorded

The inventory report lists devices attached during one Linux boot, but it does not map each external connector. The captures below record the initial path evidence; rerun the helper if checking USB-C plug orientation or collecting more connector evidence. Do not reuse the XPS USB map. On the Yoga, run this from the repository root:

```sh
python3 ports/thinkpad-x1-yoga-gen7/tools/collect-usb-port-map.py --confirm-x1-yoga-gen7
```

The user ran the helper with a Western Digital USB device (`1058:25A2`). A 5000 Mbit/s path was observed on both USB-A and both USB-C connectors; earlier captures also observed a 480 Mbit/s path on each connector. The WD device used the same observed path in both plug orientations on each USB-C port. Both USB-C ports are user-confirmed to charge the laptop. The helper reads sysfs only, omits serial numbers, requires no `sudo`, and writes no files. The observations are raw Linux paths, not an OpenCore USB map; Thunderbolt/USB4 PCIe topology still needs separate inspection. Detailed paths are in `EVIDENCE-ANALYSIS.md` and `profile.json`.

### Prepared firmware evidence exporter

`tools/export-linux-evidence.py` is for the Yoga running Kubuntu only. After mounting the external USB yourself, run it with `--confirm-x1-yoga-gen7` and an absolute path to a new folder on that USB, for example:

```sh
sudo python3 tools/export-linux-evidence.py \
  --confirm-x1-yoga-gen7 \
  --output-dir /absolute/path/on/usb/x1yoga-evidence
```

It exports raw ACPI tables, the i915 VBT (when available), and i915 display/topology diagnostics. Intel documents the VBT as platform-specific display configuration available from i915 debugfs at `/sys/kernel/debug/dri/<n>/i915_vbt` ([VBT docs](https://drm.pages.freedesktop.org/intel-docs/vbt.html)). The exporter checks Lenovo DMI vendor data and that the destination parent is on a USB-backed mounted filesystem, then anchors writes to that open directory. It does not mount or format the USB. The confirmation flag is an operator check and does not independently prove the exact Yoga model. The manifest records missing/unreadable items. Raw ACPI/VBT data can contain machine-specific firmware details: keep it private and out of Git. The user ran this on the Yoga; its manifest lists 51 evidence files and no missing captures. The raw export remains on USB and is not committed.

## Disk and installer boundary

The existing Kubuntu EFI and ext4 partitions, and swap, must remain untouched. The approximately 179 GiB unallocated area and all internal partitions remain untouched. The 64 GB USB contains the private evidence export, MSI.ROM, Recovery image, OpenCore EFI, and local config backups. No internal-drive, partition, or Kubuntu EFI operation has been performed.

## Change boundary

The Yoga port changes stay inside `ports/thinkpad-x1-yoga-gen7/`. The Dell EFI and root build/install scripts remain unchanged. Current USB experiments and private SMBIOS values are not committed; internal partitions and EFI remain untouched.
