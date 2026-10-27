# ThinkPad X1 Yoga Gen 7 port scaffold

**Status: non-bootable research scaffold. No Yoga EFI, installer, or compatibility result exists yet.** This branch is being developed on the user's separate main PC; none of the target-laptop collection commands have been run in this session.

## Repository audit

The checkout is at revision `99631db20ad841bb5d5f3934e4ffa4dc09f92dee` on branch `yoga-gen7`. At that revision, `main` and `origin/main` pointed to the same commit. The maintained EFI and all confirmed results in this repository target a Dell XPS 13 Plus 9320 with a Raptor Lake i7-1360P.

The XPS EFI is not a Yoga template. It uses SMBIOS `MacBookPro16,2`, GPU spoofing and framebuffer properties, an XPS USB map, XPS I2C ACPI, and Dell-specific power/sensor configuration. In particular, `acpi/SSDT-XPS-I2C.dsl` hard-codes I2C0/TPL0 as touchscreen and I2C1/TPD0 as trackpad; the Yoga's reported Linux enumeration is the opposite device assignment, with different HIDs. The Yoga must get its own ACPI and USB evidence before any EFI is assembled.

### Closest graphics evidence

The repository links a community report from a Dell Latitude 7430 with the **same i7-1265U and Iris Xe 46A8**. It ran Tahoe 26.7.1 build 25G241, spoofed the GPU as 9A49, and reported Metal 2 on a 1920×1080 LG eDP panel. After updating to NootedGreen v2, the reporter reported no hangs in tests covering Displays, Trackpad, Photo Booth, Preview, Photos, QuickTime, and display sleep/wake. Separate display artifacts remained for scaled modes and scaled images. This is strong evidence that the shared GPU stack is worth porting, but it is a community report from Dell firmware and a different panel, not proof for this Yoga. See [issue 2](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/2).

### Exact graphics build baseline

The checked-in scripts and patch notes require **Tahoe 26.7.1, build 25G241**, and Apple's Tiger Lake graphics bundle **16.0.32**. `install.sh` refuses another build unless `XE_FORCE=1` is set. The Metal patcher checks expected byte sequences at fixed offsets and aborts on a mismatch; the VA patch build additionally checks a full SHA-256. A forced build or a similar product version is not evidence that the patches fit.

Apple's Tahoe update page now also lists 26.7.2. Keep this port on the repository's 25G241 baseline until the build-specific patches are independently revalidated; do not silently move to the newest Tahoe. Apple says full-installer downloads depend on the downloader Mac's compatibility and currently available versions, so availability of 26.7.1 must be checked on a compatible Mac with Apple's installer list before relying on it. See [Apple Tahoe updates](https://support.apple.com/en-us/122868) and [Apple's installer instructions](https://support.apple.com/en-us/102662).

### Dependency and build audit

- `install.sh` pins NootedGreen source commit `95f81898be65cb9f7b3d370ca78054be4cc8a62` and downloads Lilu 1.7.2 for the build.
- The checked-in EFI reports runtime Lilu 1.7.3. The build/runtime version mismatch needs to be reconciled or explicitly justified before a reproducible Yoga build.
- The NootedGreen, HookCase, and VoodooGPIO build scripts clone MacKernelSDK at moving HEAD, so those builds are not fully reproducible. VoodooGPIO itself is checked out at `717ab2a`.
- `make-efi.sh` pins OpenCore 1.0.8 for its macserial download, but that does not by itself establish the version of the tracked OpenCore EFI binaries. The exact OpenCore version still needs verification.
- The main PC is Ubuntu 26.04.1. It has Python, Clang, iasl and zsh, but no Apple `codesign`, `sw_vers`, `diskutil`, `ioreg`, or `ocvalidate`. The repository's macOS kext/Metal build scripts require Apple's SDK/frameworks and tools; they have not been run here. Static source, plist, JSON and ACPI work can continue on this PC.

## Port design

Keep two configurations separate and machine-specific:

1. **Recovery/installer:** no NootedGreen or GPU spoof/framebuffer injection; no XPS ACPI tables or USB map; only the minimum verified platform support needed to reach recovery or the installer. Do not depend on AX211 Wi-Fi for Recovery.
2. **Experimental acceleration:** add the 9A49 presentation only after confirming the Yoga's PCI path; add the active EU/subslice and L3 topology only after reading the target's Linux fuse/topology report; add a Yoga-derived panel and ACPI setup; keep each experimental driver change independently switchable.

No configuration is generated yet. The existing `config-install.plist` is still an XPS config and retains the 9A49 GPU spoof and XPS ACPI/USB settings, so it is not a Yoga recovery configuration.

## Evidence gates before an EFI

1. On the Yoga in Kubuntu, reconcile reported hardware against machine-type/BIOS, PCI, USB, I2C/HID, audio, eDP/EDID, and i915 topology evidence. The prepared inventory tool is for the Yoga only; it was not run on the main PC.
2. Obtain the Yoga's ACPI tables and VBT through a reviewed, read-only capture path. The inventory tool records ACPI table headers only; it does not export AML or VBT data. Keep raw firmware dumps private and out of Git.
3. Derive the I2C/GPIO interrupts and a USB map from the Yoga itself. Keep the reported storage, Kubuntu EFI/ext4 partitions, and swap outside this porting work.
4. Build a Yoga recovery config and validate it with the validator matching the actual OpenCore binary version.
5. Only then make an isolated acceleration config, keep the exact 25G241/16.0.32 build gates, and define a rollback path to the USB recovery config.

## Prepared Linux inventory tool

`tools/collect-linux-inventory.py` reads selected `/proc`, `/sys`, and i915 debugfs entries and prints a report to stdout by default. It includes available `i915_display_info`, `i915_sseu_status`, DMC and eDP power-save diagnostics, plus VBT size/signature/hash. It omits storage devices and partition tables, DMI serials/UUIDs, MAC addresses, and USB serial fields. It does not invoke sudo, install packages, mount filesystems, or change settings. From Kubuntu on the Yoga, start with `python3 tools/collect-linux-inventory.py --confirm-x1-yoga-gen7`; if i915 debugfs entries say unreadable, rerun as `sudo python3 tools/collect-linux-inventory.py --confirm-x1-yoga-gen7`. It also checks that DMI says Lenovo. The default prints to the terminal and writes nothing. The optional `--output PATH` is not needed for sharing; if used, choose a removable-USB path. This tool has not been run on the main PC.

### Prepared firmware evidence exporter

`tools/export-linux-evidence.py` is for the Yoga running Kubuntu only. After mounting the external USB yourself, run it with `--confirm-x1-yoga-gen7` and an absolute path to a new folder on that USB, for example:

```sh
sudo python3 tools/export-linux-evidence.py \
  --confirm-x1-yoga-gen7 \
  --output-dir /absolute/path/on/usb/x1yoga-evidence
```

It exports raw ACPI tables, the i915 VBT (when available), and i915 display/topology diagnostics. Intel documents the VBT as platform-specific display configuration available from i915 debugfs at `/sys/kernel/debug/dri/<n>/i915_vbt` ([VBT docs](https://drm.pages.freedesktop.org/intel-docs/vbt.html)). The exporter checks Lenovo DMI vendor data and that the destination parent is on a USB-backed mounted filesystem, then anchors writes to that open directory. It does not mount or format the USB. The confirmation flag is an operator check and does not independently prove the exact Yoga model. The manifest records missing/unreadable items. Raw ACPI/VBT data can contain machine-specific firmware details: keep it private and out of Git. This tool has not been run.

## Disk and installer boundary

The existing Kubuntu EFI and ext4 partitions, and swap, must remain untouched. The approximately 179 GiB unallocated area and the available 64 GB USB have not been used. No installer, partitioning, formatting, EFI generation, or drive operation has been performed. Any later USB write requires an explicit device identification and approval.

## Change boundary

The initial commits stay inside `ports/thinkpad-x1-yoga-gen7/`. The Dell EFI and root build/install scripts remain unchanged. No installer, partitioning, formatting, EFI generation, or drive operation has been performed.
