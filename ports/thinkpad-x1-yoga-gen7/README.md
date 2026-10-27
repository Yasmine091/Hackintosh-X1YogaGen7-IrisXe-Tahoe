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

`tools/collect-linux-inventory.py` reads selected `/proc` and `/sys` entries and prints a report to stdout by default. It omits storage devices and partition tables, DMI serials/UUIDs, MAC addresses, and USB serial fields. It does not call sudo, install packages, mount filesystems, or change settings. It is intended to be run on the Yoga from Kubuntu, never on this main PC. Its optional `--output PATH` creates a new file and refuses to overwrite; use it only after explicitly choosing a removable-USB path. No report has been saved.

## Disk and installer boundary

The existing Kubuntu EFI and ext4 partitions, and swap, must remain untouched. The approximately 179 GiB unallocated area and the available 64 GB USB have not been used. No installer, partitioning, formatting, EFI generation, or drive operation has been performed. Any later USB write requires an explicit device identification and approval.

## First safe commit

Keep the first commit to this port folder: the evidence-labelled profile, this audit/plan, the graphics applicability matrix, and the read-only inventory tool. It must not modify the Dell EFI, root build/install scripts, or any disk.
