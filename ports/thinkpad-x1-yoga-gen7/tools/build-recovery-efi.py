#!/usr/bin/env python3
"""Stage and validate a local-only X1 Yoga Gen 7 Recovery EFI candidate.

This does not create installer media or write to a USB/disk. The private
SMBIOS identity is generated into the staged config and is never printed.
Use --debug for a separate diagnostic EFI with OpenCore DEBUG binaries.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import plistlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path


OC_VERSION = "1.0.8"
OC_RELEASE_URL = (
    "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/"
    "OpenCore-1.0.8-RELEASE.zip"
)
OC_RELEASE_SHA256 = "2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b"
OC_DEBUG_URL = (
    "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/"
    "OpenCore-1.0.8-DEBUG.zip"
)
OC_DEBUG_SHA256 = "3f5f42b85703cf2c08e8dcd9245a52fb4326c9f4ef335c75b49f516cbbe131c6"
MODEL = "MacBookPro16,2"

KEXTS = {
    "Lilu.kext": {
        "Lilu": "e3f00df5aca98c70363489292514f088ae3b667417c9c5afdd33799ff09390bd",
    },
    "VirtualSMC.kext": {
        "VirtualSMC": "bf91e9542b86c20acaf210353a93742291c49328e2d14b03fa0fa4fc52b3b5ce",
    },
    "WhateverGreen.kext": {
        "WhateverGreen": "059967ba94fba6cbf3c2cdf40fb4277e00a2a42bc1aa250e632103acbc3efdd0",
    },
    "AirportItlwm.kext": {
        "AirportItlwm": "259bac9432bffa8bf9c73411d8ac8f4a854552375e9f60ba0870ea3151ed973c",
    },
    "VoodooPS2Controller.kext": {
        "VoodooPS2Controller": "be6f3aa9dc88954462e422df78d8d7d129cb91b8fd03c4018ef04cc9f472e8f0",
        "Contents/PlugIns/VoodooPS2Keyboard.kext/VoodooPS2Keyboard":
            "a1e4903278b2028da9fea8feeb911026fb029ed8164d947bd7481245ae86193b",
        "Contents/PlugIns/VoodooPS2Mouse.kext/VoodooPS2Mouse":
            "075be10067839c38366da4f8864a87506e0c5d0305f98e540cd30e6da9adacab",
    },
    "XHCI-unsupported.kext": {
        "Contents/Info.plist": "00fe5c096dbc349544260b205464c068b2a81ecf7541be4412ea7a752dd2cfd0",
    },
    "USBToolBox.kext": {
        "USBToolBox": "c5c8dc205a079ee3f90b7875fb5ff622e4f15d32f29cf519123dab2822c422b7",
    },
    "UTBMap.kext": {
        "Contents/Info.plist": "0ea75ff52b973326f2b8cc94a9dafbaf58e3ab5e96ea66b0f42a5c2000aaeaef",
    },
    "WhateverXe.kext": {
        "Contents/Info.plist": "3f8b06f4979a82b3ecf8faa4f6002333ed70cecbf87a897a495373f3cf6d3057",
        "Contents/MacOS/WhateverXe": "e92b65b0cce5964aacb0e7674a762fb8bd85dee5a931d15bd80b0edcafd1c39b",
    },
    "AMFIPass.kext": {
        "Contents/Info.plist": "eb3fda04c0e8c8ce0ef4cfc984dcfb771db6aee476d379bd4bc3b7a74a00e4e9",
        "Contents/MacOS/AMFIPass": "2d36aeca1740b258e6bb0b66844b5bfb59a0edb7cdd9ef78206689e5d223d8dc",
    },
}

ACPI_TABLES = {
    "SSDT-CPU-STA.aml": "ed4a1a63cbbbc963bb6c84fad8bca43f0924f9584d4b3805dae662a6b4317d68",
    "SSDT-PLUG-ALT.aml": "64331ae5c240031fd00f73ab31e1116cd4f6128c0fb6eb5788e801b1f23a2b18",
    "SSDT-RTCAWAC.aml": "665933431fb49e3bf9097207f4ebf9da213cd60f36bc6e5d04d61edb30f87d89",
}

EFI_FILES = {
    "X64/EFI/BOOT/BOOTx64.efi": "EFI/BOOT/BOOTx64.efi",
    "X64/EFI/OC/OpenCore.efi": "EFI/OC/OpenCore.efi",
    "X64/EFI/OC/Drivers/OpenRuntime.efi": "EFI/OC/Drivers/OpenRuntime.efi",
    "X64/EFI/OC/Drivers/OpenHfsPlus.efi": "EFI/OC/Drivers/OpenHfsPlus.efi",
    "Utilities/ocvalidate/ocvalidate.linux": None,
    "Utilities/macserial/macserial.linux": None,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def bundle_executable(bundle: Path) -> tuple[Path, dict]:
    info_path = bundle / "Contents/Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    rel = Path("Contents/MacOS") / info["CFBundleExecutable"]
    return bundle / rel, info


def generate_identity(macserial: Path) -> dict:
    result = subprocess.run(
        [str(macserial), "-m", MODEL, "-g", "-n", "1"],
        check=True,
        capture_output=True,
        text=True,
    )
    parts = [part.strip() for part in result.stdout.strip().split("|")]
    if len(parts) != 2 or not all(parts):
        raise RuntimeError("Pinned macserial returned an unexpected serial/MLB format")
    serial, mlb = parts
    return {
        "SystemProductName": MODEL,
        "SystemSerialNumber": serial,
        "MLB": mlb,
        "SystemUUID": str(uuid.uuid4()).upper(),
        "ROM": secrets.token_bytes(6),
    }


def read_identity(config_path: Path) -> dict:
    config = plistlib.loads(config_path.read_bytes())
    identity = config["PlatformInfo"]["Generic"]
    if identity.get("SystemProductName") != MODEL:
        raise ValueError(f"Identity source must use {MODEL}")
    fields = ("SystemSerialNumber", "MLB", "SystemUUID", "ROM")
    if any(not identity.get(field) for field in fields):
        raise ValueError("Identity source has incomplete SMBIOS values")
    if len(identity["ROM"]) != 6:
        raise ValueError("Identity source ROM must be exactly 6 bytes")
    uuid.UUID(identity["SystemUUID"])
    return {field: identity[field] for field in fields} | {"SystemProductName": MODEL}


def copy_release_file(archive: zipfile.ZipFile, source: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(archive.read(source))


def validate_payload(config: dict, staged: Path) -> None:
    oc = staged / "EFI/OC"
    for item in config["Kernel"]["Add"]:
        if not item["Enabled"]:
            continue
        bundle = oc / "Kexts" / item["BundlePath"]
        if not bundle.is_dir():
            raise RuntimeError(f"Enabled kext bundle is missing: {item['BundlePath']}")
        for key in ("ExecutablePath", "PlistPath"):
            relative = item[key]
            if relative and not (bundle / relative).is_file():
                raise RuntimeError(f"Missing {key} for enabled kext {item['BundlePath']}: {relative}")
    for item in config["UEFI"]["Drivers"]:
        if item["Enabled"] and not (oc / "Drivers" / item["Path"]).is_file():
            raise RuntimeError(f"Missing enabled UEFI driver: {item['Path']}")
    for item in config["ACPI"]["Add"]:
        if item["Enabled"] and not (oc / "ACPI" / item["Path"]).is_file():
            raise RuntimeError(f"Missing enabled ACPI table: {item['Path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new local staging directory")
    parser.add_argument(
        "--opencore-zip",
        type=Path,
        help="official OpenCore 1.0.8 archive matching the selected build type",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="stage the pinned OpenCore DEBUG build with DEBUG_INFO logging",
    )
    parser.add_argument("--repo-root", type=Path, help="repository root (normally auto-detected)")
    parser.add_argument("--template", type=Path, help="recovery plist template (normally from the Yoga port)")
    parser.add_argument("--reuse-config", type=Path, help="reuse private SMBIOS values from a prior config")
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        raise SystemExit("Run this staging helper on Linux; no USB or disk operations are performed.")

    script = Path(__file__).resolve()
    repo = args.repo_root.resolve() if args.repo_root else script.parents[3]
    port = repo / "ports/thinkpad-x1-yoga-gen7"
    template = args.template.expanduser().resolve() if args.template else port / "config-recovery-template.plist"
    kext_source = repo / "EFI/OC/Kexts"
    if not template.is_file() or not kext_source.is_dir():
        raise SystemExit("Could not locate the Yoga template and tracked kext source under repository root")

    output = args.output.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="x1yoga-recovery-", dir=output.parent) as tmp_name:
        tmp = Path(tmp_name)
        build_type = "DEBUG" if args.debug else "RELEASE"
        archive_url = OC_DEBUG_URL if args.debug else OC_RELEASE_URL
        expected_hash = OC_DEBUG_SHA256 if args.debug else OC_RELEASE_SHA256
        archive_path = args.opencore_zip.expanduser().resolve() if args.opencore_zip else tmp / "OpenCore.zip"
        if not args.opencore_zip:
            request = urllib.request.Request(archive_url, headers={"User-Agent": "x1-yoga-recovery-stager"})
            with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as out:
                shutil.copyfileobj(response, out)
        actual_hash = sha256(archive_path)
        if actual_hash != expected_hash:
            raise SystemExit(
                f"OpenCore archive SHA-256 mismatch ({actual_hash}); expected the pinned {OC_VERSION} {build_type} archive"
            )

        staged = tmp / "stage"
        (staged / "EFI/BOOT").mkdir(parents=True)
        (staged / "EFI/OC/Drivers").mkdir(parents=True)
        (staged / "EFI/OC/ACPI").mkdir(parents=True)
        (staged / "EFI/OC/Kexts").mkdir(parents=True)
        with zipfile.ZipFile(archive_path) as archive:
            for source, relative in EFI_FILES.items():
                destination = tmp / Path(source).name if relative is None else staged / relative
                copy_release_file(archive, source, destination)

        macserial = tmp / "macserial.linux"
        ocvalidate = tmp / "ocvalidate.linux"
        macserial.chmod(0o755)
        ocvalidate.chmod(0o755)

        identity = read_identity(args.reuse_config) if args.reuse_config else generate_identity(macserial)
        config = plistlib.loads(template.read_bytes())
        if args.debug:
            # Match OpenCore's documented DEBUG diagnostic mask: ERROR, WARN,
            # and INFO. Keep Target=67 from the template for file logging.
            config["Misc"]["Debug"]["DisplayLevel"] = 0x80000042
        generic = config["PlatformInfo"]["Generic"]
        generic.update(identity)
        config_path = staged / "EFI/OC/config.plist"
        config_path.write_bytes(plistlib.dumps(config, fmt=plistlib.FMT_XML, sort_keys=False))
        config_path.chmod(0o600)

        staged_kexts = staged / "EFI/OC/Kexts"
        kext_lines = []
        required_kexts = set()
        for item in config["Kernel"]["Add"]:
            # Keep the pinned XHCI injector in the staged EFI as a reversible
            # fallback even while its config entry is disabled for the native
            # Apple-driver A/B. Other disabled kexts remain omitted.
            if not item["Enabled"] and item["BundlePath"] != "XHCI-unsupported.kext":
                continue
            bundle = item["BundlePath"].split(".kext", 1)[0] + ".kext"
            required_kexts.add(Path(bundle).name)
        for name, expected_execs in KEXTS.items():
            if name not in required_kexts:
                continue
            candidates = (port / "Kexts" / name, kext_source / name)
            source = next((candidate for candidate in candidates if candidate.is_dir()), None)
            if source is None:
                raise SystemExit(f"Missing tracked kext: {name}")
            destination = staged_kexts / name
            shutil.copytree(source, destination)
            for relative, expected in expected_execs.items():
                if relative == "Contents/Info.plist":
                    info_path = destination / relative
                    info = plistlib.loads(info_path.read_bytes())
                    actual = sha256(info_path)
                elif relative == "Contents/PlugIns/VoodooPS2Keyboard.kext/VoodooPS2Keyboard":
                    plugin = destination / "Contents/PlugIns/VoodooPS2Keyboard.kext"
                    executable = plugin / "Contents/MacOS/VoodooPS2Keyboard"
                    info_path = plugin / "Contents/Info.plist"
                    info = plistlib.loads(info_path.read_bytes())
                elif relative == "Contents/PlugIns/VoodooPS2Mouse.kext/VoodooPS2Mouse":
                    plugin = destination / "Contents/PlugIns/VoodooPS2Mouse.kext"
                    executable = plugin / "Contents/MacOS/VoodooPS2Mouse"
                    info_path = plugin / "Contents/Info.plist"
                    info = plistlib.loads(info_path.read_bytes())
                else:
                    executable, info = bundle_executable(destination)
                if relative != "Contents/Info.plist":
                    actual = sha256(executable)
                if actual != expected:
                    raise SystemExit(f"Unexpected {name} payload for {info.get('CFBundleVersion')}: {actual}")
                kext_lines.append(f"{name} {info.get('CFBundleVersion')} {actual}")

        acpi_lines = []
        for name, expected in ACPI_TABLES.items():
            source = port / "ACPI" / name
            if not source.is_file():
                raise SystemExit(f"Missing Yoga ACPI table: {source}")
            actual = sha256(source)
            if actual != expected:
                raise SystemExit(f"Unexpected Yoga ACPI table payload {name}: {actual}")
            shutil.copy2(source, staged / "EFI/OC/ACPI" / name)
            acpi_lines.append(f"{name} {actual}")

        validate_payload(config, staged)
        check = subprocess.run([str(ocvalidate), str(config_path)], capture_output=True, text=True)
        if check.returncode != 0:
            raise SystemExit(check.stdout + check.stderr)
        print(check.stdout.strip())

        profile_name = (
            "WhateverXe experimental"
            if "WhateverXe.kext" in required_kexts
            else "Recovery"
        )
        manifest = [
            f"Local staging only; not a boot-tested {profile_name} EFI and not installer media.",
            f"OpenCore: {OC_VERSION} {build_type}; archive SHA-256: {actual_hash}",
            f"SMBIOS model: {MODEL}; a local serial/MLB/UUID/ROM set is in config.plist.",
            "Do not commit or publish this generated config. Apple service acceptance is not verified.",
            "Kext payload SHA-256 values:",
            *kext_lines,
            "Yoga ACPI table SHA-256 values:",
            *acpi_lines,
            f"config.plist SHA-256: {sha256(config_path)}",
            "No BaseSystem image, GPU spoof, NootedGreen, Bluetooth, audio, or I2C kexts included.",
            "The captured Yoga USB map and three target-derived ACPI tables are included; macOS runtime behavior is not proven by staging.",
            "This helper did not touch a USB, internal drive, partition table, or firmware settings.",
        ]
        (staged / "STAGING-README.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        os.replace(staged, output)

    print(f"Staged and validated {profile_name} EFI at: {output}")
    print("SMBIOS values were not printed. Keep this generated config private and reuse it for future builds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
