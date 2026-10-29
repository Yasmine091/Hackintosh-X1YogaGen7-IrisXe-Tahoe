# WhateverXe post-install graphics experiment

**Candidate:** WhateverXe 0.6.1 with WhateverXe Graphics 0.3.2 for Intel Iris Xe `8086:46A8`. This is the strongest current software lead for this GPU, but not a proven Yoga configuration. WhateverXe recognizes Alder Lake-P/U and its 0.6.1 release adds experimental internal eDP support; the project's eDP path is explicitly not hardware-tested. Do not use this profile to boot Recovery or run the installer.

## Hardware fit and open risks

The Yoga profile reports 96 available EUs, a built-in AUO 1920×1200 eDP panel, two lanes at 270 MHz, 24-bpp, DPCD 1.4, and a captured 9 KiB VBT. The active panel/link block has not yet been decoded. Linux reported PSR2 enabled for this panel; WhateverXe's current eDP implementation excludes PSR and supports only a single firmware-described Combo A/B panel using PPS0 and PCH PWM. We do not yet know that this firmware/panel matches those conditions. A matching GPU ID is not proof that eDP will light, stay stable, or expose 1920×1200.

Do not add a fake `device-id`, framebuffer personality, stolen-memory value, `AAPL,GfxYTile`, or copied Dell/XPS display properties. WhateverXe selects `46A8` and topology from the physical device. DVMT is unknown; only apply the project's 60 MiB workaround if the Yoga's actual firmware setting is confirmed as 60 MiB. `SSDT-PNLF` is a separate brightness-control requirement and is not included until its ACPI path is verified.

## Pinned artifacts and prerequisites

| Component | Pinned artifact | SHA-256 / status |
|---|---|---|
| WhateverXe OpenCore plugin | [0.6.1 RELEASE ZIP](https://github.com/b00t0x/WhateverXe/releases/tag/0.6.1) | `46c8cd684461db7f84a971e7479770c423f73d52d45addfb48242176b9eb04fc` |
| WhateverXe Graphics installer | [0.3.2 package](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.3.2) | `7ac6c7149248c483efbd93555294d587a93d81392421f3af8a4f5b1b5fcc0101` |
| AMFIPass Mod | Archive at WhateverXe-Graphics commit `b4d3889` | `71f41de42e355d2a83e6f093ef34a5b24d0a9c9a9085830b2317f1b874f56250` |

The WhateverXe and AMFIPass kext bundles in this port were extracted from those official, pinned archives; their executable hashes are checked by the local EFI builder. The signed graphics package contains Apple/Intel-derived driver payloads, so it is not stored in this Git repository. Download/install it only on the Yoga after macOS is installed and booting.

Required together:

- Lilu, then `WhateverXe.kext`, then the linked `AMFIPass.kext` Mod.
- WhateverGreen **disabled**. Never load WhateverGreen and WhateverXe together.
- `csr-active-config=03080000` (`0x803`), which weakens SIP. This is present only in the separate experimental template; it does not change the Recovery EFI or firmware by itself.
- Boot arguments `-allow3d -disablegfxfirmware`.
- Tahoe 26.7 or newer. The current Graphics 0.3.2 package lists build `25G241` as its Tahoe target. Check the installed version/build with `sw_vers -productVersion` and `sw_vers -buildVersion`; do not install the package on a different build unless its release notes explicitly cover it.

The package installs signed graphics components under `/Library` and rebuilds AuxKC; on Tahoe it disables `CoreMedia / AllowOnePassMetalScaling`. It does not patch the System volume or change EFI/SIP. The package container is unsigned and not notarized, so verify the official release checksum before opening it. The linked AMFIPass Mod replaces an upstream AMFIPass build; do not load both. `amfi=0x80` and `ipc_control_port_options=0` are not required by this package.

## Separate template and safe staging

`config-whateverxe-postinstall-template.plist` is a distinct post-install profile. It disables WhateverGreen, enables the pinned WhateverXe and AMFIPass bundles, adds the required SIP value and boot arguments, keeps `UEFI > Output > Resolution` at `Max`, and adds no guessed GPU properties. It must not replace `config.plist` on the recovery USB while macOS installation is still in progress.

After macOS is installed and the target build is confirmed, stage a separate local EFI using the same private SMBIOS values as Recovery:

```sh
python3 ports/thinkpad-x1-yoga-gen7/tools/build-recovery-efi.py \
  --template ports/thinkpad-x1-yoga-gen7/config-whateverxe-postinstall-template.plist \
  --reuse-config /path/to/private/recovery/EFI/OC/config.plist \
  --output /tmp/x1-yoga-whateverxe-efi
```

This only creates `/tmp/x1-yoga-whateverxe-efi/EFI`; it does not write a USB or install the graphics package. Validate and keep the Recovery EFI intact. On the installed Yoga, boot the WEX EFI, install the checksum-verified Graphics package using macOS Installer, and reboot through OpenCore. For a failure, return to the saved Recovery EFI/config; remove the Graphics package only with its upstream uninstall script, then reboot.

## Resolution and success criteria

The Recovery USB initially forced OpenCore's preboot console to `1024x768`. On 2026-10-29 its config was changed to `Resolution=Max` and read back from the stick; the next Yoga boot will show whether firmware offers a larger GOP mode. That setting does not set macOS's display mode. Recovery retains `-igfxvesa` and is unaccelerated. Native 1920×1200, Metal, brightness, sleep/wake, and stability remain untested until the installed system boots with matching WhateverXe and Graphics versions.

Sources: [WhateverXe compatibility/configuration](https://github.com/b00t0x/WhateverXe), [0.6.1 release notes](https://github.com/b00t0x/WhateverXe/releases/tag/0.6.1), [Graphics requirements and package](https://github.com/b00t0x/WhateverXe-Graphics), [Graphics 0.3.2 release](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.3.2).
